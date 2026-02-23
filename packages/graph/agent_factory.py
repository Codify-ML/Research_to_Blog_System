from __future__ import annotations

import json
from datetime import UTC, datetime

from packages.core.llm_client import get_llm_client
from packages.core.retry import retry_with_backoff
from packages.core.settings import Settings
from packages.graph.nodes import (
    default_editor,
    default_research,
    default_writer,
)
from packages.graph.prompts import (
    EDITOR_SYSTEM_PROMPT,
    RESEARCHER_SYSTEM_PROMPT,
    WRITER_SYSTEM_PROMPT,
    build_editor_user_prompt,
    build_researcher_user_prompt,
    build_writer_user_prompt,
    compose_prompt,
)
from packages.graph.research_tools import (
    freshness_window_days,
    get_research_function_handlers,
    get_research_function_tool_definitions,
    is_freshness_critical,
    should_use_web_search,
)
from packages.graph.schemas import EditorDecision


def build_agent_functions(settings: Settings):
    if settings.use_mock_llm:
        return default_research, default_writer, default_editor

    client = get_llm_client(settings)

    def research_fn(
        topic: str,
        max_sources: int,
        content_format: str,
        length_preference: str,
        research_depth: str,
    ) -> tuple[list[str], str, list[str]]:
        freshness_critical = is_freshness_critical(topic)
        use_web_search = (
            settings.research_web_search_enabled
            and should_use_web_search(topic)
        )
        tools: list[dict[str, object]] | None = None
        function_handlers = None
        tool_choice: str | dict[str, object] | None = None
        if use_web_search:
            tools = [{"type": "web_search"}]
            if settings.research_function_tools_enabled:
                tools.extend(get_research_function_tool_definitions())
                function_handlers = get_research_function_handlers()
            tool_choice = "required" if freshness_critical else "auto"

        def _run() -> str:
            user_prompt = build_researcher_user_prompt(
                topic=topic,
                reference_date=datetime.now(tz=UTC).date().isoformat(),
                freshness_critical=freshness_critical,
                freshness_window_days=(
                    freshness_window_days(topic)
                    if freshness_critical
                    else None
                ),
                web_search_enabled=use_web_search,
                max_sources=max(1, min(20, int(max_sources))),
                content_format=content_format,
                length_preference=length_preference,
                research_depth=research_depth,
            )
            prompt = compose_prompt(
                system_prompt=RESEARCHER_SYSTEM_PROMPT,
                user_prompt=user_prompt,
            )
            return client.complete(
                prompt=prompt,
                model=settings.openai_model_researcher,
                tools=tools,
                tool_choice=tool_choice,
                function_handlers=function_handlers,
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
        return notes, summary, client.get_last_tool_usage()

    def writer_fn(
        topic: str,
        research_notes: list[str],
        feedback: list[str],
        prior_draft: str,
        content_format: str,
        content_context: str,
        tone: str,
        length_preference: str,
    ) -> str:
        def _run() -> str:
            prompt = compose_prompt(
                system_prompt=WRITER_SYSTEM_PROMPT,
                user_prompt=build_writer_user_prompt(
                    topic=topic,
                    research_notes=research_notes,
                    feedback=feedback,
                    prior_draft=prior_draft,
                    content_format=content_format,
                    content_context=content_context,
                    tone=tone,
                    length_preference=length_preference,
                ),
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
        content_format: str,
        tone: str,
        length_preference: str,
    ) -> EditorDecision:
        def _run() -> str:
            prompt = compose_prompt(
                system_prompt=EDITOR_SYSTEM_PROMPT,
                user_prompt=build_editor_user_prompt(
                    topic=topic,
                    draft=draft,
                    research_notes=research_notes,
                    revision_count=revision_count,
                    content_format=content_format,
                    tone=tone,
                    length_preference=length_preference,
                ),
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
            strengths=["Draft has a recognizable core idea."],
            weaknesses=["Requires revisions for approval."],
        )

    return EditorDecision(
        is_approved=True,
        feedback=["Optional: tighten transitions between sections."],
        strengths=["Draft appears coherent and generally well-structured."],
        weaknesses=["Could further improve depth with one extra example."],
    )
