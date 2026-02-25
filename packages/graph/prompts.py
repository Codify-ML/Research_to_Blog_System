from __future__ import annotations

RESEARCHER_SYSTEM_PROMPT = """
You are the Researcher agent in a multi-agent blog system.

Mission:
- Produce factual, concise research notes that ground downstream writing.
- Prefer stable facts from internal knowledge when they are sufficient.
- Use web evidence only when the topic is time-sensitive, uncertain, or
  likely to require current references.

Output contract:
- Return depth-appropriate concise bullet points.
- Keep each bullet self-contained and factual.
- Avoid speculation, hype, and unsupported claims.
- If certainty is low, state uncertainty explicitly.
- End each bullet with citation metadata in this exact format:
  [source: <domain/publisher>; url: <https://... or n/a>;
  date: <YYYY-MM-DD or unknown>]
""".strip()

WRITER_SYSTEM_PROMPT = """
You are the Writer agent in a multi-agent blog system.

Mission:
- Draft a clear, practical, and structured blog post from the provided
  research notes and editor feedback.

Writing guidelines:
- Stay faithful to provided research notes.
- Use clear sectioning and concrete explanations.
- Resolve all editor feedback in the current revision.
- Do not invent facts not present in research notes.
""".strip()

EDITOR_SYSTEM_PROMPT = """
You are the Editor agent in a multi-agent blog system.

Mission:
- Evaluate the draft for factual grounding, clarity, completeness, and
  actionable value for the target reader.

Evaluation rubric:
- Grounding: claims align with provided research notes.
- Structure: logical flow, readable sections, concise language.
- Coverage: addresses topic scope with sufficient depth.
- Actionability: gives practical takeaways where appropriate.

Output contract:
- Return strict JSON only with keys:
  - is_approved: boolean
  - feedback: list of actionable revision items
  - strengths: list of notable strengths
  - weaknesses: list of notable weaknesses
- Always provide strengths and weaknesses.
- Feedback should be constructive and specific. If approved, include only
  optional improvement items.
""".strip()


def build_researcher_user_prompt(
    *,
    topic: str,
    reference_date: str,
    freshness_critical: bool,
    freshness_window_days: int | None,
    web_search_enabled: bool,
    max_sources: int,
    content_format: str,
    length_preference: str,
    research_depth: str,
) -> str:
    notes_min, notes_max = _research_note_range(
        content_format=content_format,
        length_preference=length_preference,
        research_depth=research_depth,
    )
    prompt = (
        "Topic:\n"
        f"{topic}\n\n"
        f"Reference date (UTC): {reference_date}\n\n"
        f"Target content format: {content_format}\n"
        f"Requested length: {length_preference}\n\n"
        f"Research depth: {research_depth}\n\n"
        "Task:\n"
        "- Generate concise, factual research notes.\n"
        f"- Return {notes_min} to {notes_max} bullet points.\n"
        "- Prioritize correctness and source quality.\n"
        f"- Use at most {max_sources} distinct sources.\n"
        "- Every bullet must include citation metadata using this format:\n"
        "  [source: <domain/publisher>; "
        "url: <https://... or n/a>; "
        "date: <YYYY-MM-DD or unknown>]\n"
        "- If no reliable citation exists for a claim, omit the claim.\n"
        f"- {_research_depth_guidance(research_depth)}\n"
    )

    if freshness_critical:
        window = freshness_window_days or 30
        prompt += (
            "\nFreshness policy (critical):\n"
            "- Treat this as time-sensitive.\n"
            "- Prefer sources from the last "
            f"{window} day(s) when possible.\n"
            "- Prefix each bullet with [YYYY-MM-DD] using source date.\n"
            "- If best available evidence is older than this window, "
            "explicitly state staleness.\n"
        )
        if web_search_enabled:
            prompt += (
                "- Use the web search tool to verify current information.\n"
            )

    return prompt


def build_writer_user_prompt(
    *,
    topic: str,
    research_notes: list[str],
    feedback: list[str],
    prior_draft: str,
    content_format: str,
    content_context: str,
    tone: str,
    length_preference: str,
) -> str:
    notes_block = "\n".join(f"- {item}" for item in research_notes) or "- none"
    feedback_block = "\n".join(f"- {item}" for item in feedback) or "- none"
    prior = prior_draft or "- none"
    context_block = content_context or "- none"
    length_guide = {
        "short": "Keep it concise (~250-450 words).",
        "balanced": "Target a balanced depth (~500-900 words).",
        "long": "Provide deeper coverage (~1000-1500 words).",
    }.get(length_preference, "Keep a balanced and readable length.")

    return (
        f"Topic: {topic}\n\n"
        f"Target format: {content_format}\n"
        f"Desired tone: {tone}\n"
        f"Length preference: {length_preference}\n"
        f"Additional context:\n{context_block}\n\n"
        f"Research Notes:\n{notes_block}\n\n"
        f"Feedback to Address:\n{feedback_block}\n\n"
        f"Prior Draft:\n{prior}\n\n"
        "Task:\n"
        "- Produce an improved blog draft.\n"
        "- Keep it concise, structured, and factual.\n"
        f"- {length_guide}\n"
        f"{_format_specific_writer_guidance(content_format)}"
    )


def build_editor_user_prompt(
    *,
    topic: str,
    draft: str,
    research_notes: list[str],
    revision_count: int,
    content_format: str,
    tone: str,
    length_preference: str,
) -> str:
    notes_block = "\n".join(f"- {item}" for item in research_notes) or "- none"
    return (
        f"Topic: {topic}\n"
        f"Revision Count: {revision_count}\n\n"
        f"Target format: {content_format}\n"
        f"Desired tone: {tone}\n"
        f"Length preference: {length_preference}\n\n"
        f"Research Notes:\n{notes_block}\n\n"
        f"Draft:\n{draft}\n"
    )


def compose_prompt(*, system_prompt: str, user_prompt: str) -> str:
    return (
        f"<SYSTEM>\n{system_prompt}\n</SYSTEM>\n\n"
        f"<USER>\n{user_prompt}\n</USER>"
    )


def _research_note_range(
    *,
    content_format: str,
    length_preference: str,
    research_depth: str,
) -> tuple[int, int]:
    lowered = content_format.lower()
    depth = research_depth.lower()

    base_by_depth: dict[str, tuple[int, int]] = {
        "light": (4, 7),
        "standard": (7, 11),
        "deep": (10, 14),
    }
    default_base = base_by_depth.get(depth, base_by_depth["standard"])

    if length_preference == "short":
        base = (max(3, default_base[0] - 2), max(5, default_base[1] - 2))
    elif length_preference == "long":
        base = (default_base[0] + 2, default_base[1] + 2)
    else:
        base = default_base

    if "linkedin" in lowered:
        # Shorter social formats need fewer research bullets.
        return (max(4, base[0] - 2), max(6, base[1] - 2))
    return base


def _research_depth_guidance(research_depth: str) -> str:
    guidance = {
        "light": (
            "Cover essentials only: key definitions, core facts, and one "
            "practical implication."
        ),
        "standard": (
            "Balance breadth and depth: include core facts, risks, and "
            "practical implementation notes."
        ),
        "deep": (
            "Provide deeper coverage: include nuanced tradeoffs, caveats, "
            "counterpoints, and edge cases."
        ),
    }
    return guidance.get(
        research_depth.lower(),
        guidance["standard"],
    )


def _format_specific_writer_guidance(content_format: str) -> str:
    lowered = content_format.lower()
    if "linkedin" in lowered:
        return (
            "- For LinkedIn-style posts, use light formatting and optional "
            "emoji (0-3), only when it improves readability.\n"
        )
    return ""
