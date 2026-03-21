from app.agents.financial_agent import FinancialAgent


def test_financial_agent_estimate_budget():
    agent = FinancialAgent()
    result = agent.estimate_budget(guest_count=5)
    assert isinstance(result, dict)
    assert "estimated_total" in result and result["estimated_total"] >= 0

