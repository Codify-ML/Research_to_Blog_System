from __future__ import annotations

import argparse
import os
import re
import secrets
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class BootstrapError(RuntimeError):
    """Raised when bootstrap execution fails."""


@dataclass(slots=True)
class BootstrapConfig:
    values: dict[str, str]
    repo_root: Path
    dry_run: bool

    def get(self, key: str, default: str = "") -> str:
        value = self.values.get(key, default).strip()
        return value if value else default

    def get_bool(self, key: str, default: bool) -> bool:
        raw = self.values.get(key, "")
        if not raw:
            return default
        return raw.strip().lower() in {"1", "true", "yes", "on"}

    def get_float(self, key: str, default: float) -> float:
        raw = self.values.get(key, "")
        if not raw:
            return default
        return float(raw)

    def get_int(self, key: str, default: int) -> int:
        raw = self.values.get(key, "")
        if not raw:
            return default
        return int(raw)


def _run(
    cmd: list[str],
    *,
    env: dict[str, str] | None = None,
    capture: bool = False,
    dry_run: bool = False,
) -> str:
    printable = _sanitize_cmd(cmd)
    print(f"+ {printable}")
    if dry_run:
        return ""
    kwargs: dict[str, Any] = {"check": False, "text": True, "env": env}
    if capture:
        kwargs["stdout"] = subprocess.PIPE
        kwargs["stderr"] = subprocess.PIPE
    proc = subprocess.run(cmd, **kwargs)
    if proc.returncode != 0:
        stderr = getattr(proc, "stderr", "") or ""
        raise BootstrapError(f"Command failed: {printable}\n{stderr}".strip())
    if capture:
        return (proc.stdout or "").strip()
    return ""


def _sanitize_cmd(cmd: list[str]) -> str:
    redacted_flags = {"--secret-string", "--body"}
    rendered: list[str] = []
    idx = 0
    while idx < len(cmd):
        token = cmd[idx]
        rendered.append(token)
        if token in redacted_flags and idx + 1 < len(cmd):
            rendered.append("***")
            idx += 2
            continue
        idx += 1
    return " ".join(rendered)


def _load_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        raise BootstrapError(f"Config file not found: {path}")
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if (
            len(value) >= 2
            and value[0] == value[-1]
            and value[0] in {'"', "'"}
        ):
            value = value[1:-1]
        values[key] = value
    return values


def _fail_if_placeholder(name: str, value: str) -> None:
    trimmed = value.strip().lower()
    bad_tokens = {
        "",
        "change-me",
        "changeme",
        "<value>",
        "<secret>",
        "<placeholder>",
    }
    if trimmed in bad_tokens or ("<" in value and ">" in value):
        raise BootstrapError(f"{name} is unset or contains placeholder text.")


def _require_keys(cfg: BootstrapConfig, keys: list[str]) -> None:
    for key in keys:
        _fail_if_placeholder(key, cfg.get(key))


def _validate_config(cfg: BootstrapConfig) -> None:
    if cfg.get_bool("APP_LANGFUSE_ENABLED", True):
        _require_keys(
            cfg,
            [
                "APP_LANGFUSE_HOST",
            ],
        )
        host = cfg.get("APP_LANGFUSE_HOST", "").lower()
        if any(
            x in host
            for x in ("host.docker.internal", "localhost", "127.0.0.1")
        ):
            raise BootstrapError(
                "APP_LANGFUSE_HOST points to a local endpoint. "
                "Use the cloud Langfuse URL for bootstrap."
            )
        if cfg.get("APP_LANGFUSE_ENVIRONMENT", "").strip().lower() == "local":
            raise BootstrapError(
                "APP_LANGFUSE_ENVIRONMENT cannot be 'local' "
                "for cloud bootstrap."
            )
    if cfg.get_bool("ENABLE_LANGFUSE_BOOTSTRAP_INIT", True):
        _require_keys(cfg, ["LANGFUSE_INIT_ORG_ID"])


def _aws_env(cfg: BootstrapConfig) -> dict[str, str]:
    env = os.environ.copy()
    region = cfg.get("AWS_REGION", "us-west-2")
    profile = cfg.get("AWS_PROFILE", "")
    env["AWS_REGION"] = region
    if profile:
        env["AWS_PROFILE"] = profile
    return env


def _gh_env(cfg: BootstrapConfig) -> dict[str, str]:
    return os.environ.copy()


def _ensure_secret_exists(cfg: BootstrapConfig, secret_id: str) -> None:
    env = _aws_env(cfg)
    describe = [
        "aws",
        "secretsmanager",
        "describe-secret",
        "--secret-id",
        secret_id,
    ]
    try:
        _run(describe, env=env, capture=True, dry_run=cfg.dry_run)
        return
    except BootstrapError:
        create = [
            "aws",
            "secretsmanager",
            "create-secret",
            "--name",
            secret_id,
            "--secret-string",
            "bootstrap-pending",
        ]
        _run(create, env=env, dry_run=cfg.dry_run)


def _put_secret(
    cfg: BootstrapConfig, secret_id: str, secret_value: str
) -> None:
    _ensure_secret_exists(cfg, secret_id)
    if not cfg.dry_run:
        current_cmd = [
            "aws",
            "secretsmanager",
            "get-secret-value",
            "--secret-id",
            secret_id,
            "--query",
            "SecretString",
            "--output",
            "text",
        ]
        current = _run(
            current_cmd, env=_aws_env(cfg), capture=True, dry_run=False
        )
        if current == secret_value:
            print(f"= unchanged {secret_id}")
            return
    cmd = [
        "aws",
        "secretsmanager",
        "put-secret-value",
        "--secret-id",
        secret_id,
        "--secret-string",
        secret_value,
    ]
    _run(cmd, env=_aws_env(cfg), dry_run=cfg.dry_run)


def _get_secret_value(cfg: BootstrapConfig, secret_id: str) -> str:
    cmd = [
        "aws",
        "secretsmanager",
        "get-secret-value",
        "--secret-id",
        secret_id,
        "--query",
        "SecretString",
        "--output",
        "text",
    ]
    try:
        return _run(cmd, env=_aws_env(cfg), capture=True, dry_run=cfg.dry_run)
    except BootstrapError:
        return ""


def _validate_langfuse_key_format(public_key: str, secret_key: str) -> None:
    if len(public_key.strip()) < 12:
        raise BootstrapError(
            "LANGFUSE_PUBLIC_KEY appears invalid (too short)."
        )
    if len(secret_key.strip()) < 16:
        raise BootstrapError(
            "LANGFUSE_SECRET_KEY appears invalid (too short)."
        )


def _resolve_langfuse_project_keys(
    cfg: BootstrapConfig, app_prefix: str, langfuse_prefix: str
) -> tuple[str, str]:
    public_key = cfg.get("LANGFUSE_PUBLIC_KEY", "")
    secret_key = cfg.get("LANGFUSE_SECRET_KEY", "")

    if not public_key:
        public_key = _get_secret_value(
            cfg, f"{app_prefix}/langfuse_public_key"
        )
    if not secret_key:
        secret_key = _get_secret_value(
            cfg, f"{app_prefix}/langfuse_secret_key"
        )

    if not public_key:
        public_key = _get_secret_value(
            cfg, f"{langfuse_prefix}/init_project_public_key"
        )
    if not secret_key:
        secret_key = _get_secret_value(
            cfg, f"{langfuse_prefix}/init_project_secret_key"
        )

    if not public_key:
        public_key = f"lf_pk_{secrets.token_hex(16)}"
        print("~ generated LANGFUSE_PUBLIC_KEY")
    if not secret_key:
        secret_key = f"lf_sk_{secrets.token_hex(32)}"
        print("~ generated LANGFUSE_SECRET_KEY")

    _validate_langfuse_key_format(public_key, secret_key)
    return public_key, secret_key


def _set_gh_variable(
    cfg: BootstrapConfig,
    *,
    env_name: str,
    name: str,
    value: str,
    repo: str,
) -> None:
    cmd = [
        "gh",
        "variable",
        "set",
        name,
        "--env",
        env_name,
        "--body",
        value,
        "--repo",
        repo,
    ]
    _run(cmd, env=_gh_env(cfg), dry_run=cfg.dry_run)


def _set_gh_secret(
    cfg: BootstrapConfig,
    *,
    env_name: str,
    name: str,
    value: str,
    repo: str,
) -> None:
    cmd = [
        "gh",
        "secret",
        "set",
        name,
        "--env",
        env_name,
        "--body",
        value,
        "--repo",
        repo,
    ]
    _run(cmd, env=_gh_env(cfg), dry_run=cfg.dry_run)


def _format_tfvars_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    raw = str(value).replace('"', '\\"')
    return f'"{raw}"'


def _set_tfvar(path: Path, key: str, value: Any) -> None:
    if path.exists():
        lines = path.read_text(encoding="utf-8").splitlines()
    else:
        lines = []
    pattern = re.compile(rf"^\s*{re.escape(key)}\s*=")
    replacement = f"{key} = {_format_tfvars_value(value)}"
    updated = False
    for idx, line in enumerate(lines):
        if pattern.match(line):
            lines[idx] = replacement
            updated = True
            break
    if not updated:
        if lines and lines[-1].strip():
            lines.append("")
        lines.append(replacement)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _ensure_tfvars(cfg: BootstrapConfig) -> None:
    project = cfg.get("PROJECT_NAME", "vc-blog-agent")
    env_name = cfg.get("CLOUD_ENV", "dev")
    zone_name = cfg.get("ROUTE53_ZONE_NAME", "dev.vc-projects-ds.com")
    zone_id = cfg.get("ROUTE53_ZONE_ID", "Z03707592Y0NKCCWRSSFL")
    app_dns_prefix = cfg.get("APP_DNS_PREFIX", "blog-agent")
    api_dns_label = cfg.get("API_DNS_LABEL", "api")
    ui_dns_label = cfg.get("UI_DNS_LABEL", "ui")
    langfuse_dns_label = cfg.get("LANGFUSE_DNS_LABEL", "langfuse")
    cognito_prefix = cfg.get("COGNITO_DOMAIN_PREFIX", "vc-blog-agent-dev-auth")

    langfuse_host = cfg.get(
        "APP_LANGFUSE_HOST",
        f"https://{langfuse_dns_label}.{app_dns_prefix}.{zone_name}",
    )

    dev_tfvars = cfg.repo_root / "infra/terraform/envs/dev/terraform.tfvars"
    obs_tfvars = (
        cfg.repo_root
        / "infra/terraform/envs/observability-dev/terraform.tfvars"
    )

    if cfg.dry_run:
        print(f"+ render {dev_tfvars}")
        print(f"+ render {obs_tfvars}")
        return

    dev_values: dict[str, Any] = {
        "aws_region": cfg.get("AWS_REGION", "us-west-2"),
        "aws_profile": cfg.get("AWS_PROFILE", "personal-aws-dev"),
        "project_name": project,
        "environment": env_name,
        "route53_zone_name": zone_name,
        "route53_zone_id": zone_id,
        "app_dns_prefix": app_dns_prefix,
        "api_dns_label": api_dns_label,
        "ui_dns_label": ui_dns_label,
        "cognito_domain_prefix": cognito_prefix,
        "enable_https": cfg.get_bool("ENABLE_HTTPS", True),
        "enable_ui_auth": cfg.get_bool("ENABLE_UI_AUTH", True),
        "api_auth_enabled": cfg.get_bool("API_AUTH_ENABLED", True),
        "langfuse_enabled": cfg.get_bool("APP_LANGFUSE_ENABLED", True),
        "langfuse_host": langfuse_host,
        "langfuse_environment": cfg.get(
            "APP_LANGFUSE_ENVIRONMENT",
            env_name,
        ),
        "langfuse_sample_rate": cfg.get_float(
            "APP_LANGFUSE_SAMPLE_RATE",
            1.0,
        ),
        "langfuse_capture_content": cfg.get_bool(
            "APP_LANGFUSE_CAPTURE_CONTENT",
            False,
        ),
        "langfuse_trace_health_endpoints": cfg.get_bool(
            "APP_LANGFUSE_TRACE_HEALTH_ENDPOINTS",
            False,
        ),
    }
    for key, value in dev_values.items():
        _set_tfvar(dev_tfvars, key, value)

    obs_values: dict[str, Any] = {
        "aws_region": cfg.get("AWS_REGION", "us-west-2"),
        "aws_profile": cfg.get("AWS_PROFILE", "personal-aws-dev"),
        "project_name": project,
        "environment": env_name,
        "route53_zone_name": zone_name,
        "route53_zone_id": zone_id,
        "app_dns_prefix": app_dns_prefix,
        "langfuse_dns_label": langfuse_dns_label,
        "enable_langfuse_compute": cfg.get_bool(
            "ENABLE_LANGFUSE_COMPUTE",
            True,
        ),
        "enable_langfuse_auth": cfg.get_bool("ENABLE_LANGFUSE_AUTH", True),
        "enable_https": cfg.get_bool("ENABLE_HTTPS", True),
        "langfuse_auth_disable_signup": cfg.get_bool(
            "LANGFUSE_AUTH_DISABLE_SIGNUP",
            True,
        ),
        "enable_langfuse_bootstrap_init": cfg.get_bool(
            "ENABLE_LANGFUSE_BOOTSTRAP_INIT",
            True,
        ),
        "langfuse_init_project_name": cfg.get(
            "LANGFUSE_INIT_PROJECT_NAME",
            f"{project}-observability",
        ),
        "langfuse_init_project_id": cfg.get("LANGFUSE_INIT_PROJECT_ID", ""),
        "langfuse_init_org_id": cfg.get("LANGFUSE_INIT_ORG_ID", ""),
        "langfuse_telemetry_enabled": cfg.get_bool(
            "LANGFUSE_TELEMETRY_ENABLED",
            False,
        ),
    }
    for key, value in obs_values.items():
        _set_tfvar(obs_tfvars, key, value)


def _sync_aws_secrets(cfg: BootstrapConfig) -> None:
    project = cfg.get("PROJECT_NAME", "vc-blog-agent")
    env_name = cfg.get("CLOUD_ENV", "dev")
    app_prefix = f"{project}/{env_name}"
    langfuse_prefix = f"{app_prefix}/langfuse"

    required = [
        "OPENAI_API_KEY",
        "API_AUTH_KEY",
        "LANGFUSE_DATABASE_URL",
        "LANGFUSE_REDIS_URL",
        "LANGFUSE_INIT_USER_EMAIL",
        "LANGFUSE_INIT_USER_NAME",
        "LANGFUSE_INIT_USER_PASSWORD",
    ]
    _require_keys(cfg, required)

    salt = cfg.get("LANGFUSE_SALT", secrets.token_hex(16))
    encryption_key = cfg.get("LANGFUSE_ENCRYPTION_KEY", secrets.token_hex(32))
    nextauth_secret = cfg.get(
        "LANGFUSE_NEXTAUTH_SECRET", secrets.token_hex(32)
    )
    clickhouse_user = cfg.get("LANGFUSE_CLICKHOUSE_USER", "default")
    clickhouse_password = cfg.get("LANGFUSE_CLICKHOUSE_PASSWORD", "langfuse")
    clickhouse_host = cfg.get(
        "LANGFUSE_CLICKHOUSE_HOST",
        f"clickhouse.{project}-{env_name}.internal",
    )
    clickhouse_url = cfg.get(
        "LANGFUSE_CLICKHOUSE_URL",
        (
            "http://"
            f"{clickhouse_user}:{clickhouse_password}@"
            f"{clickhouse_host}:8123"
        ),
    )
    clickhouse_migration_url = cfg.get(
        "LANGFUSE_CLICKHOUSE_MIGRATION_URL",
        (
            "clickhouse://"
            f"{clickhouse_user}:{clickhouse_password}@"
            f"{clickhouse_host}:9000"
        ),
    )
    langfuse_public_key, langfuse_secret_key = _resolve_langfuse_project_keys(
        cfg, app_prefix, langfuse_prefix
    )

    pairs = {
        f"{app_prefix}/openai_api_key": cfg.get("OPENAI_API_KEY"),
        f"{app_prefix}/api_auth_key": cfg.get("API_AUTH_KEY"),
        f"{app_prefix}/langfuse_public_key": langfuse_public_key,
        f"{app_prefix}/langfuse_secret_key": langfuse_secret_key,
        f"{langfuse_prefix}/database_url": cfg.get("LANGFUSE_DATABASE_URL"),
        f"{langfuse_prefix}/redis_connection_string": cfg.get(
            "LANGFUSE_REDIS_URL"
        ),
        f"{langfuse_prefix}/salt": salt,
        f"{langfuse_prefix}/encryption_key": encryption_key,
        f"{langfuse_prefix}/nextauth_secret": nextauth_secret,
        f"{langfuse_prefix}/clickhouse_url": clickhouse_url,
        f"{langfuse_prefix}/clickhouse_migration_url": (
            clickhouse_migration_url
        ),
        f"{langfuse_prefix}/init_user_email": cfg.get(
            "LANGFUSE_INIT_USER_EMAIL"
        ),
        f"{langfuse_prefix}/init_user_name": cfg.get(
            "LANGFUSE_INIT_USER_NAME"
        ),
        f"{langfuse_prefix}/init_user_password": cfg.get(
            "LANGFUSE_INIT_USER_PASSWORD"
        ),
        f"{langfuse_prefix}/init_project_public_key": langfuse_public_key,
        f"{langfuse_prefix}/init_project_secret_key": langfuse_secret_key,
    }

    for secret_name, secret_value in pairs.items():
        _fail_if_placeholder(secret_name, secret_value)
        _put_secret(cfg, secret_name, secret_value)


def _sync_github(cfg: BootstrapConfig) -> None:
    env_name = cfg.get("GITHUB_ENVIRONMENT", "dev")
    repo = cfg.get("GITHUB_REPO", "")
    if not repo:
        if cfg.dry_run:
            repo = "owner/repo"
        else:
            repo = _run(
                [
                    "gh",
                    "repo",
                    "view",
                    "--json",
                    "nameWithOwner",
                    "-q",
                    ".nameWithOwner",
                ],
                capture=True,
                dry_run=cfg.dry_run,
            )
    if not repo:
        raise BootstrapError("Unable to resolve GITHUB_REPO for gh commands.")

    account_id = cfg.get("AWS_ACCOUNT_ID", "")
    if not account_id:
        if cfg.dry_run:
            account_id = "123456789012"
        else:
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
                env=_aws_env(cfg),
                capture=True,
                dry_run=cfg.dry_run,
            )

    tf_workdir = cfg.get("TF_WORKDIR", "infra/terraform/envs/dev")
    variables = {
        "AWS_REGION": cfg.get("AWS_REGION", "us-west-2"),
        "AWS_ACCOUNT_ID": account_id,
        "PROJECT_NAME": cfg.get("PROJECT_NAME", "vc-blog-agent"),
        "CLOUD_ENV": cfg.get("CLOUD_ENV", "dev"),
        "TF_WORKDIR": tf_workdir,
        "IMAGE_PLATFORM": cfg.get("IMAGE_PLATFORM", "linux/amd64"),
    }
    for key, value in variables.items():
        _set_gh_variable(
            cfg,
            env_name=env_name,
            name=key,
            value=value,
            repo=repo,
        )

    secret_pairs = {
        "OPENAI_API_KEY": cfg.get("OPENAI_API_KEY"),
        "API_AUTH_KEY": cfg.get("API_AUTH_KEY"),
        "AWS_ROLE_TO_ASSUME": cfg.get("AWS_ROLE_TO_ASSUME"),
    }
    for key, value in secret_pairs.items():
        _fail_if_placeholder(key, value)
        _set_gh_secret(
            cfg,
            env_name=env_name,
            name=key,
            value=value,
            repo=repo,
        )

    external_id = cfg.get("AWS_ROLE_EXTERNAL_ID", "")
    if external_id:
        _set_gh_secret(
            cfg,
            env_name=env_name,
            name="AWS_ROLE_EXTERNAL_ID",
            value=external_id,
            repo=repo,
        )


def _terraform_sequence(cfg: BootstrapConfig, apply: bool) -> None:
    obs_dir = cfg.repo_root / "infra/terraform/envs/observability-dev"
    dev_dir = cfg.repo_root / "infra/terraform/envs/dev"
    env = _aws_env(cfg)

    plan_or_apply = "apply" if apply else "plan"
    extra = ["-auto-approve"] if apply else []

    for tf_dir in (obs_dir, dev_dir):
        _run(
            [
                "terraform",
                f"-chdir={tf_dir}",
                "init",
                "-reconfigure",
                "-backend-config=backend.hcl",
            ],
            env=env,
            dry_run=cfg.dry_run,
        )
        _run(
            [
                "terraform",
                f"-chdir={tf_dir}",
                plan_or_apply,
                "-var-file=terraform.tfvars",
                *extra,
            ],
            env=env,
            dry_run=cfg.dry_run,
        )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Bootstrap AWS Secrets, GitHub env vars/secrets, and Terraform "
            "tfvars from one environment file."
        )
    )
    parser.add_argument(
        "--config-file",
        default="ops/dev.bootstrap.env",
        help="Path to key=value config file.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print actions without writing state.",
    )
    parser.add_argument(
        "--skip-aws-secrets",
        action="store_true",
        help="Skip AWS Secrets Manager sync.",
    )
    parser.add_argument(
        "--skip-github",
        action="store_true",
        help="Skip GitHub environment vars/secrets sync.",
    )
    parser.add_argument(
        "--skip-tfvars",
        action="store_true",
        help="Skip terraform.tfvars rendering.",
    )
    parser.add_argument(
        "--terraform-plan",
        action="store_true",
        help="Run terraform init+plan for observability-dev and dev.",
    )
    parser.add_argument(
        "--terraform-apply",
        action="store_true",
        help="Run terraform init+apply for observability-dev and dev.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    values = _load_env_file((repo_root / args.config_file).resolve())
    cfg = BootstrapConfig(
        values=values,
        repo_root=repo_root,
        dry_run=args.dry_run,
    )
    _validate_config(cfg)

    if not args.skip_tfvars:
        _ensure_tfvars(cfg)

    if not args.skip_aws_secrets:
        _sync_aws_secrets(cfg)

    if not args.skip_github:
        _sync_github(cfg)

    if args.terraform_apply:
        _terraform_sequence(cfg, apply=True)
    elif args.terraform_plan:
        _terraform_sequence(cfg, apply=False)

    print("Bootstrap completed.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BootstrapError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
