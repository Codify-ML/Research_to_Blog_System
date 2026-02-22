from __future__ import annotations

import json

from packages.core.llm_client import get_llm_client
from packages.core.retry import retry_with_backoff
from packages.core.settings import Settings
from packages.graph.nodes import (
    default_editor,
    default_research,
    default_writer,
)
from packages.graph.schemas import EditorDecision


def build_agent_functions(settings: Settings):
    if settings.use_mock_llm:
        return default_research, default_writer, default_editor

    client = get_llm_client(settings)

    def research_fn(topic: str) -> tuple[list[str], str]:
        def _run() -> str:
            prompt = (
                "Generate concise factual research notes for the topic. "
                "Return 5 to 8 bullet points.\n\n"
                f"Topic: {topic}"
            )
            return client.complete(
                prompt=prompt,
                model=settings.openai_model_researcher,
            )

        raw = retry_with_backoff(
            _run,
            max_attempts=settings.llm_max_retries,
            base_delay_seconds=settings.llm_base_backoff_seconds,
            max_delay_seconds=settings.llm_max_backoff_seconds,
        )
        notes = [line.strip("- ").strip() for line in raw.splitlines()]
        notes = [line for line in notes if line]
        if not notes:
            notes = ["No external notes returned by researcher model."]
        summary = notes[0][:200]
        return notes, summary

    def writer_fn(
        topic: str,
        research_notes: list[str],
        feedback: list[str],
        prior_draft: str,
    ) -> str:
        def _run() -> str:
            notes_block = "\n".join(f"- {item}" for item in research_notes)
            feedback_block = "\n".join(f"- {item}" for item in feedback)
            prompt = (
                "Write a concise blog draft using the research notes.\n"
                f"Topic: {topic}\n"
                f"Research Notes:\n{notes_block}\n"
                f"Feedback to Address:\n{feedback_block or '- none'}\n"
                f"Prior Draft:\n{prior_draft or '- none'}"
            )
            return client.complete(
                prompt=prompt,
                model=settings.openai_model_writer,
            )

        return retry_with_backoff(
            _run,
            max_attempts=settings.llm_max_retries,
            base_delay_seconds=settings.llm_base_backoff_seconds,
            max_delay_seconds=settings.llm_max_backoff_seconds,
        )

    def editor_fn(
        topic: str,
        draft: str,
        research_notes: list[str],
        revision_count: int,
    ) -> EditorDecision:
        def _run() -> str:
            notes_block = "\n".join(f"- {item}" for item in research_notes)
            prompt = (
                "Review the draft and return strict JSON only with keys "
                "is_approved (bool) and feedback (list[str]).\n"
                f"Topic: {topic}\n"
                f"Revision Count: {revision_count}\n"
                f"Research Notes:\n{notes_block}\n"
                f"Draft:\n{draft}"
            )
            return client.complete(
                prompt=prompt,
                model=settings.openai_model_editor,
            )

        raw = retry_with_backoff(
            _run,
            max_attempts=settings.llm_max_retries,
            base_delay_seconds=settings.llm_base_backoff_seconds,
            max_delay_seconds=settings.llm_max_backoff_seconds,
        )

        return _parse_editor_decision(raw)

    return research_fn, writer_fn, editor_fn


def _parse_editor_decision(raw: str) -> EditorDecision:
    text = raw.strip()

    # Try direct JSON parse first.
    try:
        payload = json.loads(text)
        return EditorDecision(**payload)
    except Exception:
        pass

    lowered = text.lower()
    reject_markers = ("reject", "revise", "not approved")
    if any(marker in lowered for marker in reject_markers):
        return EditorDecision(
            is_approved=False,
            feedback=[text[:240] or "Editor rejected the draft."],
        )

    return EditorDecision(is_approved=True, feedback=[])
