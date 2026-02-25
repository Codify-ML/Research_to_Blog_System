from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from openai import OpenAI

from packages.core.observability import get_observability, update_span
from packages.core.settings import Settings

ToolHandler = Callable[[dict[str, Any]], Any]


class LLMClient(Protocol):
    def complete(
        self,
        *,
        prompt: str,
        model: str,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        function_handlers: dict[str, ToolHandler] | None = None,
    ) -> str:
        """Return a completion string for the given prompt and model."""

    def get_last_tool_usage(self) -> list[str]:
        """Return tool usage detected for the most recent completion."""


@dataclass(slots=True)
class MockLLMClient:
    observability: object | None = None
    capture_content: bool = False
    _last_tool_usage: list[str] | None = None

    def complete(
        self,
        *,
        prompt: str,
        model: str,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        function_handlers: dict[str, ToolHandler] | None = None,
    ) -> str:
        del tool_choice
        del function_handlers
        tool_hint = "no-tools" if not tools else f"tools={len(tools)}"
        response_text = (
            f"[MOCK:{model}] "
            f"Deterministic response ({tool_hint}) "
            f"for prompt hash length={len(prompt)}"
        )
        self._last_tool_usage = []
        obs = self.observability
        if obs is None:
            obs = get_observability()
        with obs.span(
            name="llm.complete",
            input_payload=(
                {"prompt": prompt}
                if self.capture_content
                else None
            ),
            metadata={
                "model": model,
                "tools_requested": len(tools or []),
                "mock_mode": True,
            },
        ) as span:
            update_span(
                span,
                output_payload=(
                    {"output": response_text}
                    if self.capture_content
                    else None
                ),
                metadata={"tools_used": [], "mock_mode": True},
            )
        return response_text

    def get_last_tool_usage(self) -> list[str]:
        return list(self._last_tool_usage or [])


@dataclass(slots=True)
class OpenAILLMClient:
    api_key: str
    max_tool_rounds: int = 3
    observability: object | None = None
    capture_content: bool = False
    _last_tool_usage: list[str] | None = None

    def complete(
        self,
        *,
        prompt: str,
        model: str,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        function_handlers: dict[str, ToolHandler] | None = None,
    ) -> str:
        client = OpenAI(api_key=self.api_key)
        usage: set[str] = set()
        self._last_tool_usage = []
        obs = self.observability
        if obs is None:
            obs = get_observability()
        with obs.span(
            name="llm.complete",
            input_payload=(
                {"prompt": prompt}
                if self.capture_content
                else None
            ),
            metadata={
                "model": model,
                "tools_requested": len(tools or []),
            },
        ) as span:
            request: dict[str, Any] = {
                "model": model,
                "input": prompt,
            }
            if tools:
                request["tools"] = tools
            if tool_choice is not None:
                request["tool_choice"] = tool_choice

            active_tools = tools
            try:
                response = client.responses.create(**request)
            except Exception:
                fallback_tools = self._fallback_web_search_tools(tools)
                if not fallback_tools:
                    raise
                request["tools"] = fallback_tools
                response = client.responses.create(**request)
                active_tools = fallback_tools

            self._collect_tool_usage(response, usage)
            if active_tools and function_handlers:
                response = self._resolve_function_calls(
                    client=client,
                    response=response,
                    model=model,
                    tools=active_tools,
                    tool_choice=tool_choice,
                    function_handlers=function_handlers,
                    usage=usage,
                )

            output_text = self._extract_output_text(response)
            self._last_tool_usage = sorted(usage)
            update_span(
                span,
                output_payload=(
                    {"output": output_text}
                    if self.capture_content
                    else None
                ),
                metadata={
                    "tools_used": self._last_tool_usage,
                },
            )
            return output_text

    def _resolve_function_calls(
        self,
        *,
        client: OpenAI,
        response: Any,
        model: str,
        tools: list[dict[str, Any]],
        tool_choice: str | dict[str, Any] | None,
        function_handlers: dict[str, ToolHandler],
        usage: set[str],
    ) -> Any:
        rounds = 0
        current_response = response

        while rounds < self.max_tool_rounds:
            function_calls = self._extract_function_calls(current_response)
            if not function_calls:
                return current_response

            outputs = []
            for call in function_calls:
                usage.add(f"function:{call['name']}")
                outputs.append(
                    {
                        "type": "function_call_output",
                        "call_id": call["call_id"],
                        "output": json.dumps(
                            self._run_function_handler(
                                name=call["name"],
                                arguments=call["arguments"],
                                function_handlers=function_handlers,
                            )
                        ),
                    }
                )

            request: dict[str, Any] = {
                "model": model,
                "input": outputs,
                "tools": tools,
            }
            if tool_choice is not None:
                request["tool_choice"] = tool_choice

            previous_response_id = getattr(current_response, "id", None)
            if previous_response_id:
                request["previous_response_id"] = previous_response_id

            current_response = client.responses.create(**request)
            self._collect_tool_usage(current_response, usage)
            rounds += 1

        return current_response

    def _extract_function_calls(self, response: Any) -> list[dict[str, Any]]:
        calls: list[dict[str, Any]] = []
        items = getattr(response, "output", None) or []
        for item in items:
            if isinstance(item, dict):
                item_type = item.get("type")
                name = item.get("name")
                arguments = item.get("arguments")
                call_id = item.get("call_id") or item.get("id")
            else:
                item_type = getattr(item, "type", None)
                name = getattr(item, "name", None)
                arguments = getattr(item, "arguments", None)
                call_id = getattr(item, "call_id", None) or getattr(
                    item, "id", None
                )

            if item_type != "function_call" or not name or not call_id:
                continue

            parsed_arguments: dict[str, Any] = {}
            if isinstance(arguments, dict):
                parsed_arguments = arguments
            elif isinstance(arguments, str) and arguments.strip():
                try:
                    parsed_arguments = json.loads(arguments)
                except json.JSONDecodeError:
                    parsed_arguments = {}

            calls.append(
                {
                    "call_id": str(call_id),
                    "name": str(name),
                    "arguments": parsed_arguments,
                }
            )
        return calls

    def _run_function_handler(
        self,
        *,
        name: str,
        arguments: dict[str, Any],
        function_handlers: dict[str, ToolHandler],
    ) -> dict[str, Any]:
        handler = function_handlers.get(name)
        if handler is None:
            return {
                "ok": False,
                "error": f"No function handler registered for '{name}'.",
            }
        try:
            result = handler(arguments)
            return {"ok": True, "result": result}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def _extract_output_text(self, response: Any) -> str:
        output_text = getattr(response, "output_text", "")
        if output_text:
            return output_text.strip()

        # Fallback for SDK response variants with nested content.
        try:
            chunks: list[str] = []
            for item in response.output:  # type: ignore[attr-defined]
                for content in item.content:
                    text = getattr(content, "text", None)
                    if text:
                        chunks.append(text)
            return "\n".join(chunks).strip()
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(
                "OpenAI response did not contain parsable text output."
            ) from exc

    def _collect_tool_usage(self, response: Any, usage: set[str]) -> None:
        items = getattr(response, "output", None) or []
        for item in items:
            if isinstance(item, dict):
                item_type = str(item.get("type", ""))
                name = item.get("name")
            else:
                item_type = str(getattr(item, "type", ""))
                name = getattr(item, "name", None)

            if item_type.startswith("web_search"):
                usage.add("web_search")
            if item_type == "function_call" and name:
                usage.add(f"function:{name}")

    def _fallback_web_search_tools(
        self,
        tools: list[dict[str, Any]] | None,
    ) -> list[dict[str, Any]] | None:
        if not tools:
            return None

        has_web_search = any(
            str(tool.get("type", "")).startswith("web_search")
            for tool in tools
        )
        if not has_web_search:
            return None

        fallback_tools: list[dict[str, Any]] = []
        for tool in tools:
            item = dict(tool)
            tool_type = str(item.get("type", ""))
            if tool_type == "web_search":
                item["type"] = "web_search_preview"
            fallback_tools.append(item)
        return fallback_tools

    def get_last_tool_usage(self) -> list[str]:
        return list(self._last_tool_usage or [])


def get_llm_client(settings: Settings) -> LLMClient:
    if settings.use_mock_llm:
        return MockLLMClient(
            observability=get_observability(settings),
            capture_content=settings.langfuse_capture_content,
        )
    if not settings.openai_api_key:
        raise ValueError(
            "OPENAI_API_KEY is required when USE_MOCK_LLM is false."
        )
    return OpenAILLMClient(
        api_key=settings.openai_api_key,
        observability=get_observability(settings),
        capture_content=settings.langfuse_capture_content,
    )
