from __future__ import annotations

import asyncio
import json
from typing import TypeVar

import aiohttp
from pydantic import BaseModel, ValidationError

from app.ai.base import AIProviderError, BaseAIProvider
from app.utils.logging import get_logger

T = TypeVar("T", bound=BaseModel)
logger = get_logger(__name__)


class HTTPAIProvider(BaseAIProvider):
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: float = 45.0,
        max_retries: int = 2,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self._session: aiohttp.ClientSession | None = None

    def available(self) -> bool:
        return bool(self.base_url and self.api_key and self.model)

    async def _session_get(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def close(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()

    async def analyze(self, prompt: str, system: str | None = None) -> str:
        payload = await self._request(prompt, system)
        return payload

    async def generate_structured(self, prompt: str, schema: type[T], system: str | None = None) -> T:
        raw = await self._request(prompt, system, json_object=True)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise AIProviderError("AI provider returned invalid JSON") from exc
        try:
            return schema.model_validate(data)
        except ValidationError as exc:
            raise AIProviderError("AI JSON failed schema validation") from exc

    async def _request(self, prompt: str, system: str | None, json_object: bool = False) -> str:
        if not self.available():
            raise AIProviderError("AI provider is not configured")

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        body: dict = {"model": self.model, "messages": messages, "temperature": 0.2}
        if json_object:
            body["response_format"] = {"type": "json_object"}

        url = f"{self.base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                session = await self._session_get()
                async with session.post(url, json=body, headers=headers) as response:
                    text = await response.text()
                    if response.status >= 400:
                        raise AIProviderError(f"AI provider HTTP {response.status}")
                    payload = json.loads(text)
                    content = payload["choices"][0]["message"]["content"]
                    if not content:
                        raise AIProviderError("AI provider returned an empty response")
                    return content
            except (TimeoutError, aiohttp.ClientError, KeyError, json.JSONDecodeError, AIProviderError) as exc:
                last_error = exc
                logger.warning("AI provider request failed on attempt %s", attempt + 1)
                if attempt < self.max_retries:
                    await asyncio.sleep(1.5 * (attempt + 1))
        raise AIProviderError("AI provider is unavailable") from last_error
