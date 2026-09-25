from __future__ import annotations

from app.agents.aim import AimAgent
from app.agents.awareness import AwarenessAgent
from app.agents.combat import CombatAgent
from app.agents.critic import CriticAgent
from app.agents.head_coach import HeadCoachAgent
from app.agents.movement import MovementAgent
from app.agents.positioning import PositioningAgent
from app.agents.local_coach import build_local_coach_report
from app.ai.base import AIProviderError, BaseAIProvider
from app.ai.provider import HTTPAIProvider
from app.ai.schemas import AgentResult, CoachReport, CriticResult, PipelinePayload
from app.learning.knowledge import CoachKnowledgeBase
from app.learning.profiles import CoachingProfileStore
from app.utils.logging import get_logger

logger = get_logger(__name__)


class AgentOrchestrator:
    def __init__(
        self,
        provider: BaseAIProvider,
        knowledge: CoachKnowledgeBase | None = None,
        profiles: CoachingProfileStore | None = None,
    ) -> None:
        self.provider = provider
        self.profiles = profiles
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
        if not (payload.metadata or {}).get("gameplay_analysis_available", True):
            logger.warning(
                "gameplay analysis unavailable analysis_id=%s; suppressing AI gameplay claims",
                payload.analysis_id,
            )
            hud = (payload.metadata or {}).get("hud_analysis") or {}
            profile = self.profiles.match(hud) if self.profiles is not None else None
            return build_local_coach_report(payload, profile=profile)
        if isinstance(self.provider, HTTPAIProvider) and not self.provider.available():
            logger.info("AI provider is not configured, using local coach text")
            return build_local_coach_report(payload)
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
    def fallback(payload: PipelinePayload | None = None, error: AIProviderError | None = None) -> dict:
        if payload is not None:
            return build_local_coach_report(payload)
        note = "Компьютерное зрение готово, ИИ-тренер временно недоступен."
        return {
            "specialists": [],
            "coach": CoachReport(summary=note, recommendations=[]).model_dump(),
            "critic": CriticResult(approved=False, issues=[note]).model_dump(),
            "ai_available": False,
        }
