from app.agents.base import BaseAgent
from app.ai.prompts import MOVEMENT_PROMPT


class MovementAgent(BaseAgent):
    category = "Movement"
    prompt = MOVEMENT_PROMPT
