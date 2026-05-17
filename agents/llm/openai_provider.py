from typing import Type, TypeVar

import instructor
import structlog
from openai import AsyncOpenAI
from pydantic import BaseModel
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from .base import BaseLLMProvider

T = TypeVar("T", bound=BaseModel)
log = structlog.get_logger("llm.openai")


class OpenAIProvider(BaseLLMProvider):
    """OpenAI provider using instructor for structured output."""

    def __init__(self, api_key: str, model: str = "gpt-4o") -> None:
        raw = AsyncOpenAI(api_key=api_key)
        self._raw_client = raw
        self._instructor_client = instructor.from_openai(raw)
        self._model = model

    @property
    def provider_name(self) -> str:
        return "openai"

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
        log.debug("openai.chat", model=self._model)
        response = await self._raw_client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return response.choices[0].message.content

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
        log.debug("openai.chat_structured", model=self._model, schema=response_model.__name__)
        result = await self._instructor_client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_model=response_model,
        )
        return result
