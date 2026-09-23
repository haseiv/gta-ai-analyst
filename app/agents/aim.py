from app.agents.base import BaseAgent
from app.ai.prompts import AIM_PROMPT
from app.ai.schemas import AgentResult, PipelinePayload


class AimAgent(BaseAgent):
    category = "Aim"
    prompt = AIM_PROMPT

    async def run(self, payload: PipelinePayload) -> AgentResult:
        # Crosshair tracking is not implemented in the MVP.
        return AgentResult(
            category=self.category,
            status="insufficient_data",
            findings=[],
            notes="Aim analysis requires crosshair tracking, which is not available yet.",
        )
