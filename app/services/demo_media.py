from __future__ import annotations

from typing import Any, Dict, Optional

from app.services.model_router import ModelRouter


def create_teaser_video_from_plan(
    router: ModelRouter,
    final_plan: Dict[str, Any],
    output_path: Optional[str] = None,
):
    """Optional demo utility: generate a short wedding concept teaser.

    This is not required for the main demo flow. It turns a consolidated plan
    into a concise prompt for the video model (`veo-3.1-generate-preview`).
    """
    theme = final_plan.get("theme")
    schedule = final_plan.get("schedule", {})
    budget = final_plan.get("budget", {})

    # Lightweight prompt engineering for a teaser concept
    prompt = (
        "Create a tasteful 10–15s wedding teaser montage: "
        f"theme: {theme}. Key moments: ceremony {schedule.get('ceremony')}, "
        f"reception {schedule.get('reception')}. Budget: {budget.get('currency','USD')} "
        f"{budget.get('estimated_total','')}. Include elegant transitions and warm lighting."
    )
    return router.generate_video(prompt, output_path=output_path)

