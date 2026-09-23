from app.agents.base import BaseAgent
from app.ai.prompts import POSITIONING_PROMPT


class PositioningAgent(BaseAgent):
    category = "Positioning"
    prompt = POSITIONING_PROMPT
