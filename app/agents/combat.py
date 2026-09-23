from app.agents.base import BaseAgent
from app.ai.prompts import COMBAT_PROMPT


class CombatAgent(BaseAgent):
    category = "Combat"
    prompt = COMBAT_PROMPT
