from typing import Type, TypeVar

import anthropic
import instructor
import structlog
from pydantic import BaseModel
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from .base import BaseLLMProvider

T = TypeVar("T", bound=BaseModel)
log = structlog.get_logger("llm.claude")


class ClaudeProvider(BaseLLMProvider):
    """Anthropic Claude provider.

    Uses `instructor` for structured output (tool-use mode).
    Swap the model by changing LLM_MODEL in .env — no code changes needed.
    """

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6") -> None:
        self._raw_client = anthropic.AsyncAnthropic(api_key=api_key)
        self._instructor_client = instructor.from_anthropic(
            self._raw_client,
            mode=instructor.Mode.ANTHROPIC_TOOLS,
        )
        self._model = model

    @property
    def provider_name(self) -> str:
        return "claude"

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
        log.debug("claude.chat", model=self._model)
        response = await self._raw_client.messages.create(
            model=self._model,
            max_tokens=4096,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return response.content[0].text

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
        log.debug("claude.chat_structured", model=self._model, schema=response_model.__name__)
        result = await self._instructor_client.messages.create(
            model=self._model,
            max_tokens=4096,
            system=system,
            messages=[{"role": "user", "content": user}],
            response_model=response_model,
        )
        return result
