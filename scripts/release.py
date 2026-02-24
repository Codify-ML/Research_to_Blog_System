from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

SERVICES = ("api", "worker", "ui")


class CommandError(RuntimeError):
    """Raised when a shell command fails."""


@dataclass(slots=True)
class ReleaseConfig:
    aws_profile: str
    aws_region: str
    aws_account_id: str
    project_name: str
    cloud_env: str
    tf_workdir: str
    tf_var_file: str
    image_tag: str
    image_platform: str
    services: tuple[str, ...]
    auto_approve: bool
    run_smoke: bool
    smoke_llm_mode: str
    smoke_timeout_seconds: int
    smoke_poll_seconds: int

    @property
    def ecr_registry(self) -> str:
        return f"{self.aws_account_id}.dkr.ecr.{self.aws_region}.amazonaws.com"

    @property
    def name_prefix(self) -> str:
        return f"{self.project_name}-{self.cloud_env}"

    @property
    def ecs_cluster(self) -> str:
        return f"{self.name_prefix}-cluster"

    def image_uri(self, service: str) -> str:
        return (
            f"{self.ecr_registry}/{self.name_prefix}-{service}:"
            f"{self.image_tag}"
        )


def _clean_value(value: str | None, default: str) -> str:
    if value is None:
        return default
    raw = value.strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in {'"', "'"}:
        raw = raw[1:-1]
    if not raw:
        return default
    return raw


def _run(
    cmd: Sequence[str],
    *,
    env: dict[str, str] | None = None,
    capture: bool = False,
) -> str:
    print("+", " ".join(cmd))
    kwargs: dict[str, object] = {
        "env": env,
        "check": False,
        "text": True,
    }
    if capture:
        kwargs["stdout"] = subprocess.PIPE
        kwargs["stderr"] = subprocess.PIPE
    proc = subprocess.run(list(cmd), **kwargs)
    if proc.returncode != 0:
        stderr = getattr(proc, "stderr", "") or ""
        raise CommandError(
            f"Command failed ({proc.returncode}): {' '.join(cmd)}\n{stderr}"
        )
    if capture:
        return (proc.stdout or "").strip()
    return ""


def _require(command: str) -> None:
    if not shutil_which(command):
        raise CommandError(f"Required command is missing: {command}")


def shutil_which(command: str) -> str | None:
    path = os.environ.get("PATH", "")
    for folder in path.split(os.pathsep):
        candidate = Path(folder) / command
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _default_tag() -> str:
    stamp = datetime.now(tz=UTC).strftime("%Y%m%d%H%M%S")
    short_sha = "manual"
    try:
        short_sha = _run(
            ["git", "rev-parse", "--short=12", "HEAD"], capture=True
        )
    except Exception:
        pass
    return f"{stamp}-{short_sha}"


def _parse_services(raw: str) -> tuple[str, ...]:
    items = tuple(part.strip() for part in raw.split(",") if part.strip())
    if not items:
        return SERVICES
    invalid = [item for item in items if item not in SERVICES]
    if invalid:
        raise CommandError(
            f"Invalid service(s): {', '.join(invalid)}. "
            f"Valid: {', '.join(SERVICES)}."
        )
    return items


def _dotenv_lookup(key: str) -> str | None:
    env_file = _repo_root() / ".env"
    if not env_file.exists():
        return None
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        if name.strip() == key:
            return value.strip()
    return None


def _build_aws_env(config: ReleaseConfig) -> dict[str, str]:
    env = os.environ.copy()
    env["AWS_REGION"] = config.aws_region
    if config.aws_profile:
        env["AWS_PROFILE"] = config.aws_profile
    return env


def _build_tf_env(config: ReleaseConfig) -> dict[str, str]:
    env = _build_aws_env(config)
    if "TF_VAR_aws_profile" not in env:
        # In CI this remains empty (OIDC creds), while local runs can pass
        # a profile via --aws-profile / AWS_PROFILE.
        env["TF_VAR_aws_profile"] = config.aws_profile

    if not env.get("TF_VAR_api_auth_key"):
        candidate = env.get("API_AUTH_KEY")
        if not candidate:
            key_file = _repo_root() / ".run" / "cloud_api_auth_key.txt"
            if key_file.exists():
                candidate = key_file.read_text(encoding="utf-8").strip()
        if candidate:
            env["TF_VAR_api_auth_key"] = candidate

    if not env.get("TF_VAR_openai_api_key"):
        candidate = env.get("OPENAI_API_KEY") or _dotenv_lookup(
            "OPENAI_API_KEY"
        )
        if candidate:
            env["TF_VAR_openai_api_key"] = candidate

    return env


def _ensure_aws_account(config: ReleaseConfig) -> ReleaseConfig:
    if config.aws_account_id:
        return config
    account_id = _run(
        [
            "aws",
            "sts",
            "get-caller-identity",
            "--query",
            "Account",
            "--output",
            "text",
        ],
        env=_build_aws_env(config),
        capture=True,
    )
    return ReleaseConfig(
        aws_profile=config.aws_profile,
        aws_region=config.aws_region,
        aws_account_id=account_id,
        project_name=config.project_name,
        cloud_env=config.cloud_env,
        tf_workdir=config.tf_workdir,
        tf_var_file=config.tf_var_file,
        image_tag=config.image_tag,
        image_platform=config.image_platform,
        services=config.services,
        auto_approve=config.auto_approve,
        run_smoke=config.run_smoke,
        smoke_llm_mode=config.smoke_llm_mode,
        smoke_timeout_seconds=config.smoke_timeout_seconds,
        smoke_poll_seconds=config.smoke_poll_seconds,
    )


def _ecr_login(config: ReleaseConfig) -> None:
    password = _run(
        ["aws", "ecr", "get-login-password"],
        env=_build_aws_env(config),
        capture=True,
    )
    print(
        "+ docker login --username AWS --password-stdin", config.ecr_registry
    )
    proc = subprocess.run(
        [
            "docker",
            "login",
            "--username",
            "AWS",
            "--password-stdin",
            config.ecr_registry,
        ],
        input=password,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise CommandError("ECR docker login failed.")


def _docker_build(config: ReleaseConfig) -> None:
    dockerfiles = {
        "api": "docker/api.Dockerfile",
        "worker": "docker/worker.Dockerfile",
        "ui": "docker/ui.Dockerfile",
    }
    for service in config.services:
        _run(
            [
                "docker",
                "build",
                "--platform",
                config.image_platform,
                "-f",
                dockerfiles[service],
                "-t",
                config.image_uri(service),
                ".",
            ]
        )


def _docker_push(config: ReleaseConfig) -> None:
    for service in config.services:
        _run(["docker", "push", config.image_uri(service)])


def _terraform(config: ReleaseConfig, command: str) -> None:
    tf_var_path = Path(config.tf_workdir) / config.tf_var_file
    tf_cmd = [
        "terraform",
        f"-chdir={config.tf_workdir}",
        command,
        f"-var=image_tag={config.image_tag}",
    ]
    if command in {"plan", "apply"}:
        tf_cmd.append("-lock-timeout=5m")
    if config.tf_var_file:
        if tf_var_path.exists():
            tf_cmd.insert(3, f"-var-file={config.tf_var_file}")
        else:
            print(
                "note: skipping -var-file because it was not found: "
                f"{tf_var_path}"
            )
    if command == "apply" and config.auto_approve:
        tf_cmd.append("-auto-approve")
    _run(tf_cmd, env=_build_tf_env(config))


def _terraform_output(config: ReleaseConfig, name: str) -> str:
    return _run(
        ["terraform", f"-chdir={config.tf_workdir}", "output", "-raw", name],
        env=_build_aws_env(config),
        capture=True,
    )


def _wait_ecs_stable(config: ReleaseConfig, services: Sequence[str]) -> None:
    names = [f"{config.name_prefix}-{service}" for service in services]
    _run(
        [
            "aws",
            "ecs",
            "wait",
            "services-stable",
            "--cluster",
            config.ecs_cluster,
            "--services",
            *names,
        ],
        env=_build_aws_env(config),
    )


def _cloud_smoke(config: ReleaseConfig) -> None:
    key_file = _repo_root() / ".run" / "cloud_api_auth_key.txt"
    file_key = ""
    if key_file.exists():
        file_key = key_file.read_text(encoding="utf-8").strip()
    api_key = (
        os.environ.get("API_AUTH_KEY")
        or os.environ.get("TF_VAR_api_auth_key")
        or file_key
    )
    if not api_key:
        raise CommandError("API auth key is required for smoke test.")

    api_url = _terraform_output(config, "api_url").rstrip("/")

    def call(method: str, path: str, payload: dict[str, object] | None = None):
        data = None
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{api_url}{path}",
            data=data,
            method=method,
            headers={
                "content-type": "application/json",
                "x-api-key": api_key,
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, json.loads(body)

    status, start = call(
        "POST",
        "/generate",
        {
            "topic": "release smoke check",
            "llm_mode": config.smoke_llm_mode,
        },
    )
    if status != 200:
        raise CommandError(f"Smoke generate call failed: {status}")
    job_id = str(start.get("job_id", ""))
    if not job_id:
        raise CommandError("Smoke test did not return job_id.")

    deadline = time.time() + config.smoke_timeout_seconds
    terminal = {"COMPLETED", "FAILED", "ESCALATED"}
    while time.time() < deadline:
        _, payload = call("GET", f"/status/{job_id}")
        job_status = str(payload.get("status", ""))
        print(f"smoke status={job_status} job_id={job_id}")
        if job_status in terminal:
            if job_status != "COMPLETED":
                raise CommandError(
                    f"Smoke job failed with status={job_status}"
                )
            return
        time.sleep(config.smoke_poll_seconds)

    raise CommandError("Smoke test timed out.")


def _build_config(args: argparse.Namespace) -> ReleaseConfig:
    aws_region = _clean_value(
        args.aws_region or os.environ.get("AWS_REGION"),
        "us-west-2",
    )
    aws_profile = _clean_value(
        args.aws_profile or os.environ.get("AWS_PROFILE"),
        "",
    )
    aws_account_id = _clean_value(
        args.aws_account_id or os.environ.get("AWS_ACCOUNT_ID"),
        "",
    )
    project_name = _clean_value(
        args.project_name or os.environ.get("PROJECT_NAME"),
        "vc-blog-agent",
    )
    cloud_env = _clean_value(
        args.cloud_env or os.environ.get("CLOUD_ENV"),
        "dev",
    )
    tf_workdir = _clean_value(
        args.tf_workdir or os.environ.get("TF_WORKDIR"),
        "infra/terraform/envs/dev",
    )
    tf_var_file = _clean_value(args.tf_var_file, "terraform.tfvars")
    image_platform = _clean_value(
        args.image_platform or os.environ.get("IMAGE_PLATFORM"),
        "linux/amd64",
    )
    image_tag = _clean_value(
        args.image_tag or os.environ.get("IMAGE_TAG"),
        _default_tag(),
    )
    services = _parse_services(args.services)

    config = ReleaseConfig(
        aws_profile=aws_profile,
        aws_region=aws_region,
        aws_account_id=aws_account_id,
        project_name=project_name,
        cloud_env=cloud_env,
        tf_workdir=tf_workdir,
        tf_var_file=tf_var_file,
        image_tag=image_tag,
        image_platform=image_platform,
        services=services,
        auto_approve=not args.no_auto_approve,
        run_smoke=not args.skip_smoke,
        smoke_llm_mode=args.smoke_llm_mode,
        smoke_timeout_seconds=args.smoke_timeout_seconds,
        smoke_poll_seconds=args.smoke_poll_seconds,
    )
    return _ensure_aws_account(config)


def _print_summary(config: ReleaseConfig) -> None:
    print("release config:")
    print(f"  aws_profile: {config.aws_profile}")
    print(f"  aws_region: {config.aws_region}")
    print(f"  aws_account_id: {config.aws_account_id}")
    print(f"  project_name: {config.project_name}")
    print(f"  cloud_env: {config.cloud_env}")
    print(f"  tf_workdir: {config.tf_workdir}")
    print(f"  image_tag: {config.image_tag}")
    print(f"  image_platform: {config.image_platform}")
    print(f"  services: {','.join(config.services)}")


def _execute(args: argparse.Namespace) -> None:
    required_commands: dict[str, tuple[str, ...]] = {
        "build": ("docker",),
        "push": ("aws", "docker"),
        "build-push": ("aws", "docker"),
        "plan": ("aws", "terraform"),
        "apply": ("aws", "terraform"),
        "smoke": ("aws",),
        "deploy": ("aws", "docker", "terraform"),
    }
    for command in required_commands[args.command]:
        _require(command)
    config = _build_config(args)
    _print_summary(config)

    if args.command in {"plan", "apply", "deploy"}:
        expected = ",".join(SERVICES)
        actual = ",".join(config.services)
        if config.services != SERVICES:
            raise CommandError(
                f"{args.command} requires all services ({expected}) because "
                "Terraform applies a shared image_tag across API/worker/UI. "
                f"Current services={actual}."
            )

    if args.command == "build":
        _docker_build(config)
        return
    if args.command == "push":
        _ecr_login(config)
        _docker_push(config)
        return
    if args.command == "build-push":
        _ecr_login(config)
        _docker_build(config)
        _docker_push(config)
        return
    if args.command == "plan":
        _terraform(config, "plan")
        return
    if args.command == "apply":
        _terraform(config, "apply")
        return
    if args.command == "smoke":
        _cloud_smoke(config)
        return
    if args.command == "deploy":
        _ecr_login(config)
        _docker_build(config)
        _docker_push(config)
        _terraform(config, "apply")
        _wait_ecs_stable(config, ("api", "worker", "ui"))
        if config.run_smoke:
            _cloud_smoke(config)
        return
    raise CommandError(f"Unknown command: {args.command}")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Unified build/deploy workflow for cloud releases."
    )
    parser.add_argument(
        "command",
        choices=(
            "build",
            "push",
            "build-push",
            "plan",
            "apply",
            "smoke",
            "deploy",
        ),
        help="Action to execute.",
    )
    parser.add_argument(
        "--services",
        default="api,worker,ui",
        help="Comma-separated service list (api,worker,ui).",
    )
    parser.add_argument("--image-tag", default="", help="Immutable image tag.")
    parser.add_argument("--aws-profile", default="", help="AWS profile name.")
    parser.add_argument("--aws-region", default="", help="AWS region.")
    parser.add_argument("--aws-account-id", default="", help="AWS account ID.")
    parser.add_argument("--project-name", default="", help="Project prefix.")
    parser.add_argument("--cloud-env", default="", help="Cloud environment.")
    parser.add_argument(
        "--tf-workdir",
        default="",
        help="Terraform working directory.",
    )
    parser.add_argument(
        "--tf-var-file",
        default="terraform.tfvars",
        help="Terraform var file name inside tf-workdir.",
    )
    parser.add_argument(
        "--image-platform",
        default="",
        help="Docker build platform (e.g. linux/amd64).",
    )
    parser.add_argument(
        "--no-auto-approve",
        action="store_true",
        help="Disable -auto-approve for terraform apply.",
    )
    parser.add_argument(
        "--skip-smoke",
        action="store_true",
        help="Skip smoke test in deploy command.",
    )
    parser.add_argument(
        "--smoke-llm-mode",
        choices=("mock", "openai"),
        default="mock",
        help="LLM mode for smoke validation.",
    )
    parser.add_argument(
        "--smoke-timeout-seconds",
        type=int,
        default=240,
        help="Smoke test timeout in seconds.",
    )
    parser.add_argument(
        "--smoke-poll-seconds",
        type=int,
        default=2,
        help="Smoke polling interval in seconds.",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        _execute(args)
        return 0
    except (
        CommandError,
        urllib.error.HTTPError,
        urllib.error.URLError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
