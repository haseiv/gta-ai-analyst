from app.agents.base import BaseAgent
from app.ai.prompts import AWARENESS_PROMPT


class AwarenessAgent(BaseAgent):
    category = "Awareness"
    prompt = AWARENESS_PROMPT
