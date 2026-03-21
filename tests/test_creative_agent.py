from app.agents.creative_agent import CreativeAgent
from app.services.llm_client import LLMClient


def test_creative_agent_suggest_theme():
    agent = CreativeAgent(LLMClient())
    out = agent.suggest_theme("Alex & Sam")
    assert isinstance(out, str)
    assert len(out) > 0

