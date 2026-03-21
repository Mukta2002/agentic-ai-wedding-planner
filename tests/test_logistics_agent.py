from app.agents.logistics_agent import LogisticsAgent


def test_logistics_agent_plan_schedule():
    agent = LogisticsAgent()
    schedule = agent.plan_schedule(guest_count=10)
    assert isinstance(schedule, dict)
    assert "ceremony" in schedule and "reception" in schedule

