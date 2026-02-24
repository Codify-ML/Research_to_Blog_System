from __future__ import annotations

import argparse
import os
import re
import sys

from dotenv import dotenv_values
from openai import OpenAI

OPENAI_KEY_PATTERN = re.compile(r"sk-[A-Za-z0-9_-]+")


def _sanitize(text: str) -> str:
    return OPENAI_KEY_PATTERN.sub("sk-REDACTED", text)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Simple OpenAI connectivity and key check"
    )
    parser.add_argument(
        "--api-key",
        help=(
            "OpenAI API key to use explicitly. "
            "If omitted, OPENAI_API_KEY from environment is used."
        ),
    )
    parser.add_argument(
        "--from-dotenv",
        action="store_true",
        help="Load OPENAI_API_KEY from .env file before shell env fallback.",
    )
    parser.add_argument(
        "--model",
        default="gpt-4.1-mini",
        help="Model name to use (default: gpt-4.1-mini)",
    )
    parser.add_argument(
        "--prompt",
        default="Reply with: OPENAI_DEBUG_OK",
        help="Prompt text to send",
    )
    parser.add_argument(
        "--max-output-chars",
        type=int,
        default=500,
        help="Maximum output characters to print",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    api_key = args.api_key
    if not api_key and args.from_dotenv:
        values = dotenv_values(".env")
        api_key = str(values.get("OPENAI_API_KEY", "") or "")
    if not api_key:
        api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        print(
            (
                "ERROR: No API key provided. "
                "Pass --api-key or set OPENAI_API_KEY."
            ),
            file=sys.stderr,
        )
        return 2

    client = OpenAI(api_key=api_key)

    try:
        response = client.responses.create(
            model=args.model,
            input=args.prompt,
        )
        text = (response.output_text or "").strip()
        if not text:
            text = "<empty output>"
        print("OpenAI request succeeded")
        print(f"Model: {args.model}")
        print("Response:")
        print(text[: args.max_output_chars])
        return 0
    except Exception as exc:  # pragma: no cover
        print("OpenAI request failed", file=sys.stderr)
        print(_sanitize(str(exc)), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
