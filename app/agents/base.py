from __future__ import annotations

import json

from app.ai.base import AIProviderError, BaseAIProvider
from app.ai.prompts import SYSTEM_RULES
from app.ai.schemas import AgentResult, PipelinePayload
from app.learning.knowledge import CoachKnowledgeBase
from app.utils.logging import get_logger

logger = get_logger(__name__)


class BaseAgent:
    category = "general"
    prompt = ""

    def __init__(self, provider: BaseAIProvider, knowledge: CoachKnowledgeBase | None = None) -> None:
        self.provider = provider
        self.knowledge = knowledge

    async def run(self, payload: PipelinePayload) -> AgentResult:
        examples = []
        if self.knowledge is not None:
            examples = self.knowledge.retrieve(self.category)
        prompt = self._build_prompt(payload, examples)
        try:
            return await self.provider.generate_structured(prompt, AgentResult, system=SYSTEM_RULES)
        except AIProviderError:
            logger.warning("Agent %s failed because AI provider is unavailable", self.category)
            raise

    def _build_prompt(self, payload: PipelinePayload, examples: list[dict]) -> str:
        compact = {
            "analysis_id": payload.analysis_id,
            "duration": payload.duration,
            "metrics": payload.metrics,
            "scores": payload.scores,
            "events": payload.events[:80],
            "tracks": payload.tracks[:40],
            "limitations": payload.limitations,
            "human_examples": examples,
        }
        return (
            f"{self.prompt}\n"
            f"Return JSON matching AgentResult: category, status, findings[], notes.\n"
            f"Set category to {self.category}.\n"
            f"DATA:\n{json.dumps(compact, ensure_ascii=False)}"
        )
