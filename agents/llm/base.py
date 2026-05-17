from abc import ABC, abstractmethod
from typing import TypeVar, Type
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMMessage(BaseModel):
    role: str   # "user" | "assistant"
    content: str


class BaseLLMProvider(ABC):
    """Unified interface for all LLM providers.

    Switch providers by changing LLM_PROVIDER and LLM_MODEL in .env.
    All agents call only these two methods — provider details stay here.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str: ...

    @property
    @abstractmethod
    def model_name(self) -> str: ...

    @abstractmethod
    async def chat(self, system: str, user: str) -> str:
        """Plain text completion."""
        ...

    @abstractmethod
    async def chat_structured(
        self,
        system: str,
        user: str,
        response_model: Type[T],
    ) -> T:
        """Structured completion — returns a validated Pydantic model instance."""
        ...

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(model={self.model_name})"
