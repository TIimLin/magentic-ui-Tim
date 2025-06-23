from __future__ import annotations

# pyright: ignore-all

"""AWS Bedrock Claude 3 ChatCompletionClient implementation.

This module defines a *BedrockClaudeChatCompletionClient* compatible with the
*autogen* framework. It wraps the Amazon Bedrock Runtime `invoke_model`
endpoint for the Anthropic Claude family (default: *claude-sonnet-4-20250514*).

Notes
-----
• Requires *boto3* (>= 1.34) and valid AWS credentials with the
  `bedrock:InvokeModel` permission.
• The client mirrors the behaviour of OpenAI-like chat completion clients so it
  can serve as a drop-in replacement in Magentic-UI.
"""

from typing import Any, Dict, Iterable, List, Optional, Sequence
import json

try:
    import boto3  # type: ignore
except ImportError:  # pragma: no cover – boto3 may be absent in minimal env
    boto3 = None  # type: ignore

# Attempt to import ChatCompletionClient using autogen>=0.5.7 path first
try:
    from autogen_core.models._model_client import ChatCompletionClient  # type: ignore
except ImportError:  # pragma: no cover
    try:
        from autogen_core.model_client import ChatCompletionClient  # type: ignore
    except ImportError:  # pragma: no cover
        ChatCompletionClient = object  # type: ignore

# Import Component mixin for Autogen registry
try:
    from autogen_core._component_config import Component  # type: ignore
except ImportError:  # pragma: no cover
    Component = object  # type: ignore

# Lightweight fallback for pydantic
try:
    from pydantic import BaseModel as _BaseModel, Field as _Field  # type: ignore

    class _DummyModel(_BaseModel):
        pass

    BaseModel: type = _BaseModel  # type: ignore
    Field = _Field  # type: ignore
except ImportError:  # pragma: no cover

    class BaseModel:  # type: ignore
        def model_json_schema(self):
            return {}

    def Field(*_args: Any, **_kwargs: Any):  # type: ignore
        return None

# ---------------------------------------------------------------------------
# Configuration model
# ---------------------------------------------------------------------------


class _BedrockClaudeConfig(BaseModel):  # type: ignore[misc]
    """Pydantic schema for client configuration."""

    model_id: str = Field(
        # Use the *inference-profile* identifier for Claude Sonnet 4
        default="us.anthropic.claude-sonnet-4-20250514-v1:0",
        description="Full model ID recognisable by Bedrock Runtime.",
    )
    aws_region: str = Field(default="us-west-2", description="AWS region.")
    temperature: float = Field(default=0.0, ge=0.0, le=1.0)
    max_tokens: int = Field(default=1024, ge=1)


__all__ = ["BedrockClaudeChatCompletionClient"]

# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _convert_messages(messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Ensure *messages* follow Anthropic format (role/content)."""

    converted: List[Dict[str, str]] = []
    for m in messages:
        # Accept dicts or autogen Message-like objects
        if isinstance(m, dict):
            role, content = m.get("role", "user"), m.get("content", "")
        else:
            role, content = getattr(m, "role", "user"), getattr(m, "content", str(m))
        # Claude expects string (or list of content parts) – convert lists to str
        if isinstance(content, list):
            content = " ".join(str(p) for p in content)
        converted.append({"role": role, "content": content})
    return converted


# ---------------------------------------------------------------------------
# ChatCompletionClient implementation
# ---------------------------------------------------------------------------


# Make it a proper Autogen component by inheriting Component

class BedrockClaudeChatCompletionClient(ChatCompletionClient, Component):  # type: ignore[misc]
    """Anthropic Claude 3 implementation for autogen chat completion."""

    # Metadata required by autogen's component registry
    component_type: str = "chat_completion_client"
    display_name: str = "AWS Bedrock Claude 3 ChatCompletionClient"
    description: str = "Chat completion client powered by Claude 3 via Amazon Bedrock Runtime."
    component_config_schema = _BedrockClaudeConfig

    # ---------------------------------------------------------------------
    # Factory helpers (ComponentFromConfig / ComponentToConfig)
    # ---------------------------------------------------------------------

    @classmethod
    def _from_config(cls, config: Dict[str, Any]):  # type: ignore[override]
        if isinstance(config, dict):
            cfg = _BedrockClaudeConfig(**config)
        else:
            cfg = _BedrockClaudeConfig.model_validate(config)  # type: ignore[arg-type]
        return cls(
            model_id=cfg.model_id,
            aws_region=cfg.aws_region,
            temperature=cfg.temperature,
            max_tokens=cfg.max_tokens,
        )

    def _to_config(self) -> _BedrockClaudeConfig:  # type: ignore[override]
        return _BedrockClaudeConfig(
            model_id=self._model_id,
            aws_region=self._aws_region,
            temperature=self._temperature,
            max_tokens=self._max_tokens,
        )

    # ---------------------------------------------------------------------
    # Initialiser
    # ---------------------------------------------------------------------

    def __init__(
        self,
        *,
        model_id: str = "us.anthropic.claude-sonnet-4-20250514-v1:0",
        aws_region: str = "us-west-2",
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> None:
        if boto3 is None:
            raise RuntimeError("boto3 package not installed. Run `pip install boto3`." )

        self._model_id = model_id
        self._aws_region = aws_region
        self._temperature = temperature
        self._max_tokens = max_tokens

        # Create Bedrock Runtime client once
        self._client = boto3.client("bedrock-runtime", region_name=self._aws_region)  # type: ignore[arg-type]

    # ---------------------------------------------------------------------
    # Core Chat Completion logic
    # ---------------------------------------------------------------------

    def create_chat_completion(
        self,
        messages: List[Dict[str, str]],
        stream: bool = False,
        **kwargs: Any,
    ) -> Any:  # noqa: ANN401 – autogen returns flexible dict
        if stream:
            raise NotImplementedError("Streaming not yet supported for Bedrock Claude 3 in this client.")

        # Build request payload
        payload: Dict[str, Any] = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": kwargs.get("max_tokens", self._max_tokens),
            "temperature": kwargs.get("temperature", self._temperature),
            "messages": _convert_messages(messages),
        }

        response = self._client.invoke_model(
            modelId=self._model_id,
            body=json.dumps(payload).encode(),
            contentType="application/json",
            accept="application/json",
        )
        body_str: str = response["body"].read().decode()
        body_json: Dict[str, Any] = json.loads(body_str)

        assistant_text: str = body_json["content"][0]["text"]
        finish_reason: str = body_json.get("stop_reason", "stop")

        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": assistant_text,
                    },
                    "finish_reason": finish_reason,
                }
            ]
        }

    # Async wrapper using loop.run_in_executor – boto3 is sync
    async def acreate_chat_completion(self, messages: List[Dict[str, str]], stream: bool = False, **kwargs: Any):  # type: ignore[override]
        import asyncio

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: self.create_chat_completion(messages, stream=stream, **kwargs))

    # ---------------------------------------------------------------------
    # (Optional) token counting – simple heuristic (4 char / token)
    # ---------------------------------------------------------------------

    def count_tokens(self, messages: Sequence[Any] | str, *, tools: Sequence[Any] = ()) -> int:  # type: ignore[override]
        if isinstance(messages, str):
            return max(1, len(messages) // 4)
        flat = "\n".join(m.get("content", "") if isinstance(m, dict) else str(m) for m in messages)  # type: ignore[arg-type]
        return max(1, len(flat) // 4) 

    # ---------------------------------------------------------------------
    # autogen_core abstract-method fulfilment
    # ---------------------------------------------------------------------

    async def create(
        self,
        messages: "Sequence[Any]",  # type: ignore[type-var]
        *,
        tools: "Sequence[Any]" = (),
        json_output: Optional[bool | type[Any]] = None,  # noqa: D401 – unused
        extra_create_args: "Mapping[str, Any]" = {},
        cancellation_token: Optional[Any] = None,  # noqa: D401 – unused
    ) -> "Any":
        """Single-turn chat completion for Autogen high-level API."""

        import asyncio

        # When caller requests JSON-only output, prepend a strict system message.
        msg_seq = list(messages)
        if json_output:
            json_sys = {
                "role": "system",
                "content": "You are a system that must output *only* valid JSON. Do not include any additional text.",
            }
            msg_seq = [json_sys, *msg_seq]

        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.create_chat_completion(msg_seq, **extra_create_args),
        )

        from autogen_core.models import CreateResult, RequestUsage  # type: ignore

        content = response["choices"][0]["message"]["content"]  # type: ignore[index]

        usage = RequestUsage(
            prompt_tokens=self.count_tokens(messages),  # type: ignore[arg-type]
            completion_tokens=self.count_tokens(content),
        )

        self._update_usage(usage)

        return CreateResult(  # type: ignore[return-value] – dynamic import
            finish_reason="stop",  # Claude returns stop reason earlier
            content=content,
            usage=usage,
            cached=False,
        )

    async def close(self) -> None:  # noqa: D401 – nothing to close
        return None

    def actual_usage(self):  # type: ignore[override]
        return getattr(self, "_actual_usage", None)

    def total_usage(self):  # type: ignore[override]
        return getattr(self, "_total_usage", None)

    def remaining_tokens(self, messages, *, tools=()):  # type: ignore[override]
        token_limit = 200_000  # Bedrock limit upper-bound
        return token_limit - self.count_tokens(messages)  # type: ignore[arg-type]

    async def create_stream(
        self,
        messages: "Sequence[Any]",  # type: ignore[type-var]
        *,
        tools: "Sequence[Any]" = (),
        json_output: Optional[bool | type[Any]] = None,
        extra_create_args: "Mapping[str, Any]" = {},
        cancellation_token: Optional[Any] = None,  # noqa: D401 – unused
    ):
        """Very simple streaming: yield once then result."""
        result = await self.create(messages, tools=tools, json_output=json_output, extra_create_args=extra_create_args)
        if isinstance(result.content, str):
            yield result.content
        yield result

    # internal helper for usage bookkeeping
    def _update_usage(self, delta):  # type: ignore[override]
        if not hasattr(self, "_actual_usage"):
            from autogen_core.models import RequestUsage  # type: ignore

            self._actual_usage = RequestUsage(prompt_tokens=0, completion_tokens=0)  # type: ignore[attr-defined]
            self._total_usage = RequestUsage(prompt_tokens=0, completion_tokens=0)  # type: ignore[attr-defined]

        self._actual_usage = type(delta)(
            prompt_tokens=self._actual_usage.prompt_tokens + delta.prompt_tokens,  # type: ignore[attr-defined]
            completion_tokens=self._actual_usage.completion_tokens + delta.completion_tokens,  # type: ignore[attr-defined]
        )
        self._total_usage = type(delta)(
            prompt_tokens=self._total_usage.prompt_tokens + delta.prompt_tokens,  # type: ignore[attr-defined]
            completion_tokens=self._total_usage.completion_tokens + delta.completion_tokens,  # type: ignore[attr-defined]
        )

    # Capabilities / model_info -------------------------------------------

    @property
    def capabilities(self):  # type: ignore[override]
        # Minimal capabilities declaration
        return {
            "vision": False,
            "function_calling": False,
            "json_output": False,
            "family": "ANTHROPIC",
            "structured_output": False,
            "multiple_system_messages": False,
        }

    @property
    def model_info(self):  # type: ignore[override]
        return self.capabilities 