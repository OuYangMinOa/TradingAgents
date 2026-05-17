from __future__ import annotations

import importlib.resources
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, TypeVar

import structlog
from pydantic import BaseModel

from llm.base import BaseLLMProvider

T = TypeVar("T", bound=BaseModel)

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


class BaseAgent(ABC):
    """Base class for all analyst and orchestrator agents.

    Subclasses implement `analyze()` and call `self.llm.chat_structured()`
    with the appropriate Pydantic response model. They never touch provider
    internals — switching LLM_PROVIDER in .env is sufficient.
    """

    def __init__(self, llm: BaseLLMProvider) -> None:
        self.llm = llm
        self.log = structlog.get_logger(self.__class__.__name__)

    @abstractmethod
    async def analyze(self, **kwargs: Any) -> BaseModel:
        """Run the agent analysis and return a Pydantic report."""
        ...

    def load_prompt(self, name: str) -> str:
        """Load system prompt from prompts/<name>.txt"""
        path = PROMPTS_DIR / f"{name}.txt"
        if not path.exists():
            raise FileNotFoundError(f"Prompt file not found: {path}")
        return path.read_text(encoding="utf-8").strip()

    def _log_call(self, stock_id: str) -> None:
        self.log.info(
            "analyzing",
            stock_id=stock_id,
            provider=self.llm.provider_name,
            model=self.llm.model_name,
        )
