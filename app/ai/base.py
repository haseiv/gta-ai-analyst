from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class AIProviderError(RuntimeError):
    pass


class BaseAIProvider(ABC):
    @abstractmethod
    async def analyze(self, prompt: str, system: str | None = None) -> str:
        raise NotImplementedError

    @abstractmethod
    async def generate_structured(self, prompt: str, schema: type[T], system: str | None = None) -> T:
        raise NotImplementedError

    async def close(self) -> None:
        return None
