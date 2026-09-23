from __future__ import annotations

from app.agents.aim import AimAgent
from app.agents.awareness import AwarenessAgent
from app.agents.combat import CombatAgent
from app.agents.critic import CriticAgent
from app.agents.head_coach import HeadCoachAgent
from app.agents.movement import MovementAgent
from app.agents.positioning import PositioningAgent
from app.ai.base import AIProviderError, BaseAIProvider
from app.ai.schemas import AgentResult, CoachReport, CriticResult, PipelinePayload
from app.learning.knowledge import CoachKnowledgeBase
from app.utils.logging import get_logger

logger = get_logger(__name__)


class AgentOrchestrator:
    def __init__(self, provider: BaseAIProvider, knowledge: CoachKnowledgeBase | None = None) -> None:
        self.provider = provider
        self.specialists = [
            MovementAgent(provider, knowledge),
            PositioningAgent(provider, knowledge),
            AwarenessAgent(provider, knowledge),
            CombatAgent(provider, knowledge),
            AimAgent(provider, knowledge),
        ]
        self.head_coach = HeadCoachAgent(provider)
        self.critic = CriticAgent(provider)

    async def run(self, payload: PipelinePayload) -> dict:
        specialist_results: list[AgentResult] = []
        for agent in self.specialists:
            logger.info("agent analysis category=%s analysis_id=%s", agent.category, payload.analysis_id)
            result = await agent.run(payload)
            specialist_results.append(result)

        coach = await self.head_coach.run(payload, specialist_results)
        critic = await self.critic.run(payload, specialist_results, coach)
        logger.info(
            "critic result analysis_id=%s approved=%s issues=%s",
            payload.analysis_id,
            critic.approved,
            len(critic.issues),
        )
        if not critic.approved:
            logger.info("head coach revision analysis_id=%s", payload.analysis_id)
            coach = await self.head_coach.run(payload, specialist_results, critic)
        return {
            "specialists": [item.model_dump() for item in specialist_results],
            "coach": coach.model_dump(),
            "critic": critic.model_dump(),
            "ai_available": True,
        }

    @staticmethod
    def fallback(error: AIProviderError | None = None) -> dict:
        note = "Computer Vision анализ завершён, AI Coach временно недоступен."
        return {
            "specialists": [],
            "coach": CoachReport(summary=note, recommendations=[]).model_dump(),
            "critic": CriticResult(approved=False, issues=[note]).model_dump(),
            "ai_available": False,
        }
