from __future__ import annotations

from typing import Optional

from app.prompts.financial_prompts import BUDGET_PROMPT
from app.models.schemas import WeddingProfile, BudgetBreakdown


class FinancialAgent:
    """Financial logic remains deterministic; LLMs explain or narrate.

    - All budget math and catering calculations are computed in Python.
    - Text generation (gemini-2.5-flash) is used for explanation/summary.
    - Optional TTS can narrate a spoken summary using the TTS model.
    """

    def __init__(self, router: Optional[object] = None) -> None:
        self.router = router

    def estimate_budget(self, profile: WeddingProfile) -> BudgetBreakdown:
        """Produce a deterministic, structured budget breakdown.

        - Accepts a full WeddingProfile.
        - Uses deterministic Python math for category allocations.
        - Applies a Goa destination wedding heuristic when applicable.
        """
        destination = (profile.destination or "").strip().lower()
        total_budget = float(max(0.0, profile.budget))
        guest_count = int(max(0, profile.guest_count))

        # Currency heuristic: assume INR for Goa, else USD fallback
        currency = "INR" if "goa" in destination else "USD"

        # Goa destination wedding heuristic (percent split)
        # Percentages chosen within requested ranges
        venue_pct = 0.22
        catering_pct_nominal = 0.26  # nominal target, but we anchor catering by per-guest
        decor_pct = 0.12
        accommodation_pct = 0.18
        photography_pct = 0.07
        entertainment_pct = 0.06
        misc_pct = 0.09

        if "goa" in destination:
            # Per-guest catering heuristic for Goa (deterministic)
            per_guest_catering = 2800.0  # INR per guest (blended average across events)
        else:
            # Generic fallback per-guest estimate (arbitrary but deterministic)
            per_guest_catering = 100.0

        # Category computations
        catering_cost = float(guest_count) * float(per_guest_catering)
        venue_cost = total_budget * venue_pct
        decor_cost = total_budget * decor_pct
        accommodation_cost = total_budget * accommodation_pct
        photography_cost = total_budget * photography_pct
        entertainment_cost = total_budget * entertainment_pct
        misc_cost = total_budget * misc_pct

        total_estimated = (
            venue_cost
            + catering_cost
            + decor_cost
            + accommodation_cost
            + photography_cost
            + entertainment_cost
            + misc_cost
        )
        remaining_balance = total_budget - total_estimated

        # Build a concise, human-friendly summary. Optionally polish with the text model.
        per_guest_estimate = (total_estimated / guest_count) if guest_count else 0.0
        within = "within" if remaining_balance >= 0 else "over"
        summary_seed = (
            f"Total budget: {currency} {total_budget:,.0f}. "
            f"Estimated per guest: {currency} {per_guest_estimate:,.0f}. "
            f"Plan is {within} budget by {currency} {abs(remaining_balance):,.0f}. "
            f"Using a Goa destination split: venue ~22%, catering anchored to per‑guest (~{currency} {per_guest_catering:,.0f}), "
            f"decor ~12%, accommodation ~18%, photography ~7%, entertainment ~6%, misc ~9%."
        )

        budget_summary = self._polish_summary(summary_seed)

        return BudgetBreakdown(
            total_budget=total_budget,
            currency=currency,
            guest_count=guest_count,
            venue_cost=venue_cost,
            catering_cost=catering_cost,
            decor_cost=decor_cost,
            accommodation_cost=accommodation_cost,
            photography_cost=photography_cost,
            entertainment_cost=entertainment_cost,
            misc_cost=misc_cost,
            total_estimated=total_estimated,
            remaining_balance=remaining_balance,
            budget_summary=budget_summary,
        )

    def explain_budget(self, breakdown: BudgetBreakdown) -> str:
        """Optionally generate a human-friendly explanation using the text model.

        Not required for core logic; returns deterministic summary if router is unavailable.
        """
        if not self.router or not hasattr(self.router, "generate_text"):
            return breakdown.budget_summary

        prompt = (
            BUDGET_PROMPT
            + "\n\nPlease rewrite the following wedding budget summary to be concise, clear, and warm: \n"
            + breakdown.budget_summary
        )
        try:
            return self.router.generate_text(prompt)
        except Exception:
            return breakdown.budget_summary

    def _polish_summary(self, seed_text: str) -> str:
        """Polish a summary using the text model if available; else return seed."""
        if not self.router or not hasattr(self.router, "generate_text"):
            return seed_text
        try:
            prompt = (
                BUDGET_PROMPT
                + "\n\nCraft a brief, friendly, and polished budget note from: \n"
                + seed_text
            )
            text = self.router.generate_text(prompt)
            return text or seed_text
        except Exception:
            return seed_text

    # Optional media capability
    def audio_summary(self, text: str, output_path: str | None = None):
        """Generate a spoken audio summary of the budget using TTS.

        Routes to `gemini-2.5-flash-preview-tts`. Safe to skip.
        """
        if not self.router or not hasattr(self.router, "generate_speech"):
            raise RuntimeError("TTS not available on provided router.")
        return self.router.generate_speech(text, output_path=output_path)
