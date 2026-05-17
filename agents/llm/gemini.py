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


class GeminiProvider(BaseLLMProvider):
    """Google Gemini provider using the google-genai SDK.

    Supports native Pydantic structured output via response_schema.
    Swap the model by changing LLM_MODEL in .env — no code changes needed.
    """

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
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    async def chat(self, system: str, user: str) -> str:
        log.debug("gemini.chat", model=self._model, system_len=len(system), user_len=len(user))
        response = await self._client.aio.models.generate_content(
            model=self._model,
            contents=user,
            config=types.GenerateContentConfig(
                system_instruction=system,
            ),
        )
        return response.text

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    async def chat_structured(
        self,
        system: str,
        user: str,
        response_model: Type[T],
    ) -> T:
        log.debug("gemini.chat_structured", model=self._model, schema=response_model.__name__)
        response = await self._client.aio.models.generate_content(
            model=self._model,
            contents=user,
            config=types.GenerateContentConfig(
                system_instruction=system,
                response_mime_type="application/json",
                response_schema=response_model,
            ),
        )
        try:
            return response_model.model_validate_json(response.text)
        except Exception:
            # Gemini sometimes wraps the JSON in markdown — strip it
            text = response.text.strip().removeprefix("```json").removesuffix("```").strip()
            return response_model.model_validate(json.loads(text))
