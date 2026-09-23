from __future__ import annotations

import json

from app.ai.base import BaseAIProvider
from app.ai.prompts import HEAD_COACH_PROMPT, SYSTEM_RULES
from app.ai.schemas import AgentResult, CoachReport, CriticResult, PipelinePayload


class HeadCoachAgent:
    def __init__(self, provider: BaseAIProvider) -> None:
        self.provider = provider

    async def run(
        self,
        payload: PipelinePayload,
        specialist_results: list[AgentResult],
        critic_notes: CriticResult | None = None,
    ) -> CoachReport:
        body = {
            "cv_limitations": payload.limitations,
            "scores": payload.scores,
            "specialist_results": [item.model_dump() for item in specialist_results],
            "critic_notes": critic_notes.model_dump() if critic_notes else None,
        }
        prompt = (
            f"{HEAD_COACH_PROMPT}\n"
            "Return JSON matching CoachReport.\n"
            f"DATA:\n{json.dumps(body, ensure_ascii=False)}"
        )
        return await self.provider.generate_structured(prompt, CoachReport, system=SYSTEM_RULES)
