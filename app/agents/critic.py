from __future__ import annotations

import json

from app.ai.base import BaseAIProvider
from app.ai.prompts import CRITIC_PROMPT, SYSTEM_RULES
from app.ai.schemas import AgentResult, CoachReport, CriticResult, PipelinePayload


class CriticAgent:
    def __init__(self, provider: BaseAIProvider) -> None:
        self.provider = provider

    async def run(
        self,
        payload: PipelinePayload,
        specialist_results: list[AgentResult],
        coach: CoachReport,
    ) -> CriticResult:
        body = {
            "events": payload.events[:80],
            "metrics": payload.metrics,
            "specialist_results": [item.model_dump() for item in specialist_results],
            "coach_report": coach.model_dump(),
        }
        prompt = (
            f"{CRITIC_PROMPT}\n"
            "Return JSON matching CriticResult.\n"
            f"DATA:\n{json.dumps(body, ensure_ascii=False)}"
        )
        return await self.provider.generate_structured(prompt, CriticResult, system=SYSTEM_RULES)
