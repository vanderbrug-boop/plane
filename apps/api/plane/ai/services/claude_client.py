"""
Anthropic Claude API client wrapper.

Handles:
- API key management and initialization
- Structured output via tool use
- Token budgeting and usage tracking
- Streaming responses
- Audit logging of all AI interactions (21 CFR Part 11)
"""

import json
import logging
import time
from typing import Any

import anthropic

from ..models import AIUsageLog, AIWorkspaceConfig

logger = logging.getLogger(__name__)


class ClaudeClient:
    """Thin wrapper around the Anthropic SDK with budget and audit tracking."""

    def __init__(self, workspace_id: str, user_id: str = None):
        self.workspace_id = workspace_id
        self.user_id = user_id
        self.config = self._load_config()
        self.client = anthropic.Anthropic(api_key=self.config.api_key_encrypted)

    def _load_config(self) -> AIWorkspaceConfig:
        config, _ = AIWorkspaceConfig.objects.get_or_create(
            workspace_id=self.workspace_id,
            defaults={"model": "claude-sonnet-4-6"},
        )
        return config

    def _check_budget(self, estimated_tokens: int = 5000):
        if not self.config.has_budget(estimated_tokens):
            raise BudgetExceededError(
                f"Monthly token budget exhausted. "
                f"Used: {self.config.tokens_used_this_month}, "
                f"Budget: {self.config.monthly_token_budget}"
            )

    def _log_usage(self, feature: str, usage, request_summary: str, response_summary: str, duration_ms: int):
        input_tokens = getattr(usage, "input_tokens", 0)
        output_tokens = getattr(usage, "output_tokens", 0)

        AIUsageLog.objects.create(
            workspace_id=self.workspace_id,
            user_id=self.user_id,
            feature=feature,
            model=self.config.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            request_summary=request_summary,
            response_summary=response_summary[:500],
            duration_ms=duration_ms,
        )

        self.config.record_usage(input_tokens, output_tokens)

    def complete(
        self,
        feature: str,
        system: str,
        messages: list[dict],
        tools: list[dict] = None,
        max_tokens: int = 4096,
        request_summary: str = "",
    ) -> dict[str, Any]:
        """
        Send a completion request to Claude.

        Args:
            feature: Feature name for usage tracking (e.g., 'nl_query', 'enrollment_forecast')
            system: System prompt
            messages: Conversation messages
            tools: Tool definitions for structured output
            max_tokens: Maximum response tokens
            request_summary: Brief description for audit log (no PII)

        Returns:
            dict with keys: content, tool_calls, usage, stop_reason
        """
        self._check_budget(max_tokens)
        start = time.monotonic()

        kwargs = {
            "model": self.config.model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools

        response = self.client.messages.create(**kwargs)

        duration_ms = int((time.monotonic() - start) * 1000)

        # Extract content
        text_content = ""
        tool_calls = []
        for block in response.content:
            if block.type == "text":
                text_content += block.text
            elif block.type == "tool_use":
                tool_calls.append({
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                })

        response_summary = text_content[:200] if text_content else f"{len(tool_calls)} tool call(s)"

        self._log_usage(
            feature=feature,
            usage=response.usage,
            request_summary=request_summary,
            response_summary=response_summary,
            duration_ms=duration_ms,
        )

        return {
            "content": text_content,
            "tool_calls": tool_calls,
            "usage": {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
            "stop_reason": response.stop_reason,
        }

    def complete_with_tools(
        self,
        feature: str,
        system: str,
        messages: list[dict],
        tools: list[dict],
        tool_handlers: dict,
        max_turns: int = 5,
        max_tokens: int = 4096,
        request_summary: str = "",
    ) -> dict[str, Any]:
        """
        Multi-turn tool use loop. Claude calls tools, we execute them,
        feed results back until Claude produces a final text response.

        Args:
            tool_handlers: Dict mapping tool name -> callable(input) -> result
            max_turns: Maximum number of tool-use turns to prevent runaway loops
        """
        self._check_budget(max_tokens * max_turns)

        conversation = list(messages)
        all_tool_calls = []

        for turn in range(max_turns):
            result = self.complete(
                feature=feature,
                system=system,
                messages=conversation,
                tools=tools,
                max_tokens=max_tokens,
                request_summary=f"{request_summary} (turn {turn + 1})",
            )

            if not result["tool_calls"]:
                # Claude finished — return final text
                result["all_tool_calls"] = all_tool_calls
                return result

            # Build assistant message with tool calls
            assistant_content = []
            if result["content"]:
                assistant_content.append({"type": "text", "text": result["content"]})
            for tc in result["tool_calls"]:
                assistant_content.append({
                    "type": "tool_use",
                    "id": tc["id"],
                    "name": tc["name"],
                    "input": tc["input"],
                })
            conversation.append({"role": "assistant", "content": assistant_content})

            # Execute tools and build tool results
            tool_results = []
            for tc in result["tool_calls"]:
                all_tool_calls.append(tc)
                handler = tool_handlers.get(tc["name"])
                if handler:
                    try:
                        tool_output = handler(tc["input"])
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tc["id"],
                            "content": json.dumps(tool_output) if not isinstance(tool_output, str) else tool_output,
                        })
                    except Exception as e:
                        logger.error(f"Tool {tc['name']} failed: {e}")
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tc["id"],
                            "content": f"Error: {str(e)}",
                            "is_error": True,
                        })
                else:
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tc["id"],
                        "content": f"Unknown tool: {tc['name']}",
                        "is_error": True,
                    })

            conversation.append({"role": "user", "content": tool_results})

        # Max turns reached
        return {
            "content": "Maximum tool-use turns reached.",
            "tool_calls": [],
            "all_tool_calls": all_tool_calls,
            "usage": {"input_tokens": 0, "output_tokens": 0},
            "stop_reason": "max_turns",
        }

    def stream(
        self,
        feature: str,
        system: str,
        messages: list[dict],
        max_tokens: int = 4096,
        request_summary: str = "",
    ):
        """
        Stream a response from Claude. Yields text chunks.
        Used for real-time display of long-form outputs (reports, summaries).
        """
        self._check_budget(max_tokens)
        start = time.monotonic()

        full_text = ""
        with self.client.messages.stream(
            model=self.config.model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
        ) as stream:
            for text in stream.text_stream:
                full_text += text
                yield text

        duration_ms = int((time.monotonic() - start) * 1000)
        usage = stream.get_final_message().usage

        self._log_usage(
            feature=feature,
            usage=usage,
            request_summary=request_summary,
            response_summary=full_text[:200],
            duration_ms=duration_ms,
        )


class BudgetExceededError(Exception):
    pass
