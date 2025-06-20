# pyright: ignore-all
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence, Mapping

try:
    import google.generativeai as genai  # type: ignore
except ImportError:  # pragma: no cover – linting in minimal env
    genai = None  # type: ignore

try:
    # autogen-core>=0.5.7 keeps ChatCompletionClient in private module _model_client
    from autogen_core.models._model_client import ChatCompletionClient  # type: ignore
except ImportError:
    # Prior versions may expose it differently; attempt legacy path.
    try:
        from autogen_core.model_client import ChatCompletionClient  # type: ignore
    except ImportError:  # pragma: no cover – allow type check without autogen being installed
        ChatCompletionClient = object  # type: ignore

# Provide lightweight fallbacks for optional dependencies to keep type checkers happy.
try:
    from pydantic import BaseModel as _BaseModel, Field as _Field  # type: ignore

    class _DummyModel(_BaseModel):
        """Markerbase to satisfy isinstance checks."""

    BaseModel: type = _BaseModel  # type: ignore
    Field = _Field  # type: ignore
except ImportError:  # pragma: no cover – pydantic not installed in minimal env

    class BaseModel:  # type: ignore
        """Fallback no-op BaseModel when pydantic is absent."""

        def model_json_schema(self):  # noqa: D401 – mimic pydantic
            return {}

    def Field(  # type: ignore
        default: Any = None,
        description: str | None = None,
        **_: Any,
    ) -> Any:  # noqa: D401 – return default value for linter
        return default

# -- autogen-core component mixin -------------------------------------------
try:
    from autogen_core._component_config import Component  # type: ignore
except ImportError:  # pragma: no cover
    Component = object  # type: ignore


# ----------------------------- Config model --------------------------------

# We already attempted to import BaseModel earlier (fallback provided)


class _GeminiClientConfig(BaseModel):  # type: ignore[misc]
    model: str = "gemini-2.5-flash"
    api_key: Optional[str] = None
    temperature: float = 0.0
    max_output_tokens: int = 1024


__all__ = ["GeminiChatCompletionClient"]


# pyright: ignore-all

def _convert_messages_to_prompt(messages: List[Dict[str, str]]) -> str:
    """Flatten the OpenAI-style messages into a single prompt.

    Gemini SDK currently accepts a single prompt string (or list of parts). Here we follow
    a simple rule: concatenate role + colon + content, separated by newlines.
    """

    # Always instruct the model to mirror the user's language to prevent English-only replies
    lines: List[str] = [
        # System-level guidance – formulated in Chinese to prioritize Chinese replies.
        "system: 請以與使用者輸入相同的語言作答，若使用者使用中文則回答請完全使用中文。若非中文則對應使用者語言。",
    ]
    for m in messages:
        if isinstance(m, dict):
            role = m.get("role", "user")
            content = m.get("content", "")
        else:
            # Assume autogen LLMMessage-like object
            role = getattr(m, "role", m.__class__.__name__.lower())
            content = getattr(m, "content", str(m))
        # If content is list (e.g. multimodal) cast to str
        if isinstance(content, list):
            content = " ".join(str(part) for part in content)
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


class GeminiChatCompletionClient(ChatCompletionClient, Component):  # type: ignore[misc]
    """Google Gemini implementation of an autogen *ChatCompletionClient*.

    Notes
    -----
    • Requires `google-generativeai` package.<https://pypi.org/project/google-generativeai/>
    • Supports both non-streaming and streaming (`stream=True`) generations.
    • Exposes `model`, `api_key`, `temperature`, `max_output_tokens` kwargs in *config*.
    """

    # --- Component metadata (for autogen component registry) -----------------
    component_type: str = "chat_completion_client"
    """Used by autogen to distinguish component categories."""

    # NOTE: autogen expects these two class attributes
    display_name: str = "Google Gemini ChatCompletionClient"
    description: str = "Chat completion client powered by Google Gemini models."

    # Required by Component
    component_config_schema = _GeminiClientConfig

    @classmethod
    def _from_config(cls, config: Dict[str, Any]) -> "GeminiChatCompletionClient":  # type: ignore[override]
        """Factory used by autogen *ComponentFromConfig* mixin."""
        if isinstance(config, dict):
            cfg = _GeminiClientConfig(**config)
        else:  # Already a pydantic model
            cfg = _GeminiClientConfig.model_validate(config)  # type: ignore[arg-type]

        return cls(
            model=cfg.model,
            api_key=cfg.api_key,
            temperature=cfg.temperature,
            max_output_tokens=cfg.max_output_tokens,
        )

    # For ComponentToConfig mixin (inherited via ComponentBase) ----------------

    def _to_config(self) -> _GeminiClientConfig:  # type: ignore[override]
        return _GeminiClientConfig(
            model=self._model_name,
            api_key=None,  # Do not serialize secret
            temperature=self._temperature,
            max_output_tokens=self._max_output_tokens,
        )

    # -------------------------------------------------------------------------

    def __init__(
        self,
        *,
        model: str = "gemini-2.0-flash",
        api_key: Optional[str] = None,
        temperature: float = 0.0,
        max_output_tokens: int = 1024,
    ) -> None:
        """Initialize Gemini client with explicit parameters."""

        self._model_name = model
        self._temperature = temperature
        self._max_output_tokens = max_output_tokens

        if genai is None:
            raise RuntimeError(
                "google-generativeai package not installed. Run `pip install google-generativeai`."
            )

        genai.configure(api_key=api_key)  # type: ignore[call-arg]

        # Reuse model instance to cut down on HTTP overhead.
        self._model = genai.GenerativeModel(self._model_name)  # type: ignore[arg-type]

    # -------------------------------------------------------------------------
    # autogen_core API
    # -------------------------------------------------------------------------

    async def acreate_chat_completion(
        self,
        messages: List[Dict[str, str]],
        stream: bool = False,
        **kwargs: Any,
    ) -> Any:  # noqa: ANN401 – autogen returns flexible dict/iterable
        """Async version used by autogen."""
        # google-generativeai SDK currently sync only, so just wrap in thread-pool.
        import asyncio

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, lambda: self.create_chat_completion(messages, stream=stream, **kwargs)
        )

    def create_chat_completion(
        self,
        messages: List[Dict[str, str]],
        stream: bool = False,
        **kwargs: Any,
    ) -> Any:  # noqa: ANN401
        prompt = _convert_messages_to_prompt(messages)
        generation_kwargs = {
            "temperature": kwargs.get("temperature", self._temperature),
            "max_output_tokens": kwargs.get("max_output_tokens", self._max_output_tokens),
        }

        if stream:
            # Return an iterator of chunks compatible with autogen streaming format
            gemini_stream: Iterable[Any] = self._model.generate_content(prompt, stream=True, **generation_kwargs)  # type: ignore[arg-type]
            for chunk in gemini_stream:
                yield {
                    "choices": [
                        {
                            "delta": {"content": chunk.text},
                            "index": 0,
                            "finish_reason": None,
                        }
                    ]
                }
            # Indicate end of stream
            yield {
                "choices": [
                    {
                        "delta": {},
                        "index": 0,
                        "finish_reason": "stop",
                    }
                ]
            }
        else:
            response = self._model.generate_content(prompt, **generation_kwargs)  # type: ignore[arg-type]
            return {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": response.text,
                        },
                        "finish_reason": response.candidates[0].finish_reason if response.candidates else "stop",
                    }
                ]
            }

    # -------------------------------------------------------------------------
    # Utility – token counting (rough heuristic)
    # -------------------------------------------------------------------------

    def count_tokens(
        self,
        messages: "Sequence[Any] | str",
        *,
        tools: "Sequence[Any]" = (),  # noqa: D401 – keep signature parity
    ) -> int:  # type: ignore[override]
        """Rudimentary token estimator.

        • If *messages* is a string – count tokens in string.
        • If it is a sequence (list) of dicts/objects – flatten using _convert_messages_to_prompt.
        """

        if not messages:
            return 0

        if isinstance(messages, str):
            text = messages
        else:
            # Assume sequence of message dicts (role/content)
            try:
                text = _convert_messages_to_prompt(list(messages))  # type: ignore[arg-type]
            except Exception:
                text = str(messages)

        try:
            import tiktoken  # type: ignore

            enc = tiktoken.get_encoding("cl100k_base")
            return len(enc.encode(text))
        except Exception:  # pragma: no cover – best-effort fall-back
            return len(text.split())

    # ---------------------------------------------------------------------
    # Fulfilling abstract requirements of ChatCompletionClient
    # ---------------------------------------------------------------------

    async def create(
        self,
        messages: "Sequence[Any]",  # type: ignore[type-var]
        *,
        tools: "Sequence[Any]" = (),
        json_output: Optional[bool | type[Any]] = None,  # noqa: D401
        extra_create_args: "Mapping[str, Any]" = {},
        cancellation_token: Optional[Any] = None,
    ) -> "Any":
        """Single-turn chat completion."""
        # Current implementation ignores tools/json_output.
        prompt = _convert_messages_to_prompt(list(messages))
        response = self._model.generate_content(prompt, **extra_create_args)  # type: ignore[arg-type]
        content = response.text

        prompt_tokens = self.count_tokens(prompt)
        completion_tokens = self.count_tokens(content)

        from autogen_core.models import CreateResult, RequestUsage, FinishReasons

        usage = RequestUsage(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens)

        self._update_usage(usage)

        return CreateResult(
            finish_reason="stop",  # type: ignore[arg-type]
            content=content,
            usage=usage,
            cached=False,
        )

    async def close(self) -> None:  # noqa: D401
        # google-generativeai does not expose explicit close method
        return None

    def actual_usage(self):  # type: ignore[override]
        return self._actual_usage  # type: ignore[attr-defined]

    def total_usage(self):  # type: ignore[override]
        return self._total_usage  # type: ignore[attr-defined]

    def remaining_tokens(self, messages, *, tools=()):  # type: ignore[override]
        token_limit = 8192
        return token_limit - self.count_tokens(messages)  # type: ignore[arg-type]

    # Streaming: simple implementation that yields once then result
    async def create_stream(
        self,
        messages: "Sequence[Any]",  # type: ignore[type-var]
        *,
        tools: "Sequence[Any]" = (),
        json_output: Optional[bool | type[Any]] = None,
        extra_create_args: "Mapping[str, Any]" = {},
        cancellation_token: Optional[Any] = None,
    ):
        result = await self.create(
            messages,
            tools=tools,
            json_output=json_output,
            extra_create_args=extra_create_args,
            cancellation_token=cancellation_token,
        )
        if isinstance(result.content, str):
            yield result.content
        yield result

    # ------------------------------------------------------------------
    # internal helpers
    # ------------------------------------------------------------------

    def _update_usage(self, delta):  # type: ignore[override]
        if not hasattr(self, "_actual_usage"):
            from autogen_core.models import RequestUsage
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

    # Capabilities / model_info ------------------------------------------------

    @property
    def capabilities(self):  # type: ignore[override]
        from autogen_core.models import ModelCapabilities  # type: ignore

        return {
            "vision": False,
            "function_calling": False,
            "json_output": False,
            "family": "UNKNOWN",
            "structured_output": False,
            "multiple_system_messages": False,
        }  # type: ignore[return-value]

    @property
    def model_info(self):  # type: ignore[override]
        return self.capabilities  # type: ignore[return-value] 