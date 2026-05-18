import asyncio
import json
from typing import Type, TypeVar

import structlog
from google import genai
from google.genai import types
from pydantic import BaseModel
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from .base import BaseLLMProvider

T = TypeVar("T", bound=BaseModel)
log = structlog.get_logger("llm.gemini")

# Class-level semaphore: at most 4 concurrent Gemini calls.
# Each call takes ~2-4 s → ≈ 8-12 RPM, safely under the 15 RPM free-tier limit.
# Created lazily (first async call) so it always binds to the running event loop.
_call_sem: asyncio.Semaphore | None = None


def _semaphore() -> asyncio.Semaphore:
    global _call_sem
    if _call_sem is None:
        _call_sem = asyncio.Semaphore(4)
    return _call_sem


class GeminiProvider(BaseLLMProvider):
    """Google Gemini provider using the google-genai SDK."""

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash") -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model

    @property
    def provider_name(self) -> str:
        return "gemini"

    @property
    def model_name(self) -> str:
        return self._model

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=4, max=60),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    async def chat(self, system: str, user: str) -> str:
        log.debug("gemini.chat", model=self._model)
        async with _semaphore():
            response = await self._client.aio.models.generate_content(
                model=self._model,
                contents=user,
                config=types.GenerateContentConfig(system_instruction=system),
            )
        return response.text

    async def chat_structured(
        self,
        system: str,
        user: str,
        response_model: Type[T],
    ) -> T:
        """Call Gemini with structured output.

        First tries native response_schema mode; falls back to plain JSON prompt
        if the schema contains types Gemini doesn't support (e.g. additionalProperties).
        """
        try:
            return await self._chat_structured_schema(system, user, response_model)
        except Exception as exc:
            msg = str(exc)
            if "additionalProperties" in msg or "prefixItems" in msg or "INVALID_ARGUMENT" in msg:
                log.warning(
                    "gemini schema rejected, falling back to prompt-JSON",
                    model=response_model.__name__,
                    error=msg[:120],
                )
                return await self._chat_structured_prompt(system, user, response_model)
            raise

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=4, max=60),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    async def _chat_structured_schema(
        self,
        system: str,
        user: str,
        response_model: Type[T],
    ) -> T:
        log.debug("gemini.structured_schema", model=self._model, schema=response_model.__name__)
        async with _semaphore():
            response = await self._client.aio.models.generate_content(
                model=self._model,
                contents=user,
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    response_mime_type="application/json",
                    response_schema=response_model,
                ),
            )
        return _parse(response.text, response_model)

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=4, max=60),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    async def _chat_structured_prompt(
        self,
        system: str,
        user: str,
        response_model: Type[T],
    ) -> T:
        """Fallback: ask Gemini to return JSON matching the schema via prompt."""
        schema_str = json.dumps(response_model.model_json_schema(), ensure_ascii=False, indent=2)
        augmented_system = (
            f"{system}\n\n"
            f"請以純 JSON 格式回覆，符合以下 schema（不要加 markdown code block）：\n{schema_str}"
        )
        log.debug("gemini.structured_prompt", model=self._model, schema=response_model.__name__)
        async with _semaphore():
            response = await self._client.aio.models.generate_content(
                model=self._model,
                contents=user,
                config=types.GenerateContentConfig(
                    system_instruction=augmented_system,
                    response_mime_type="application/json",
                ),
            )
        return _parse(response.text, response_model)


def _parse(text: str, response_model: Type[T]) -> T:
    try:
        return response_model.model_validate_json(text)
    except Exception:
        cleaned = text.strip().removeprefix("```json").removesuffix("```").strip()
        return response_model.model_validate(json.loads(cleaned))
