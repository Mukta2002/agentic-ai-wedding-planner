from __future__ import annotations

from typing import Any, Dict
from datetime import datetime

from app.models.schemas import (
    WeddingProfile,
    CreativePlan,
    LogisticsPlan,
    BudgetBreakdown,
    WeddingState,
)


class Orchestrator:
    def __init__(self, creative_agent, logistics_agent, financial_agent, storage, design_director_agent=None) -> None:
        self.creative = creative_agent
        self.logistics = logistics_agent
        self.financial = financial_agent
        self.storage = storage
        self.design = design_director_agent

    def run_demo(self, profile: WeddingProfile) -> WeddingState:
        """Run a demo that stitches agents together from a structured profile.

        Returns the final WeddingState object that has been fully updated.
        """
        couple_names = f"{profile.bride_name} & {profile.groom_name}"

        # Start from a single WeddingState instance and update it throughout
        state = WeddingState(
            profile=profile,
            creative=None,
            logistics=None,
            financial=None,
            state_status="profile_initialized",
            last_updated=datetime.utcnow().isoformat(),
        )

        # Run agents with graceful fallbacks (avoid crashing if models are unavailable)
        try:
            creative_plan = self.creative.generate_creative_plan(profile)
        except Exception:
            # Fallback to a minimal plan if the agent errors out
            creative_plan = CreativePlan(
                theme_name=f"Elegant Celebration for {couple_names}",
                theme_description=f"A refined, modern wedding honoring {couple_names} with warm details.",
                color_palette=["ivory", "sage", "gold"],
                hashtags=["#ElegantCelebration", "#ModernVows"],
                invitation_text=f"You are warmly invited to celebrate {couple_names}.",
                guest_style_guide="Dress code: formal or cocktail.",
                invite_design_prompt="Minimal serif typography, soft neutral palette, subtle floral emboss.",
            )

        # Ensure guests CSV is present/migrated before logistics planning
        try:
            tmp_state_for_csv = WeddingState(
                profile=profile,
                creative=None,
                logistics=None,
                financial=None,
                state_status="pre_logistics_csv",
                last_updated="",
            )
            self.storage.export_guests_csv(tmp_state_for_csv)
        except Exception:
            pass

        try:
            logistics_plan = self.logistics.plan_logistics(profile)
        except Exception:
            # Fallback to a minimal structured plan if the agent errors out
            confirmed = 0
            pending = int(profile.guest_count)
            declined = 0
            logistics_plan = LogisticsPlan(
                confirmed_guest_count=confirmed,
                pending_guest_count=pending,
                declined_guest_count=declined,
                catering_headcount=confirmed,
                room_allocation=[{"room_type": "double", "count": int(max(0, confirmed // 2))}],
                event_schedule=[
                    {"event": "Welcome Dinner", "date": profile.wedding_dates[0] if profile.wedding_dates else "2026-12-10", "time": "7:00 PM"},
                    {"event": "Wedding Ceremony", "date": profile.wedding_dates[1] if len(profile.wedding_dates) > 1 else (profile.wedding_dates[0] if profile.wedding_dates else "2026-12-11"), "time": "2:00 PM"},
                    {"event": "Reception", "date": profile.wedding_dates[1] if len(profile.wedding_dates) > 1 else (profile.wedding_dates[0] if profile.wedding_dates else "2026-12-11"), "time": "6:00 PM"},
                ],
                logistics_summary="A concise two-day flow with rooming based on confirmed RSVPs.",
            )

        try:
            budget_breakdown = self.financial.estimate_budget(profile)
        except Exception:
            # Deterministic fallback if agent errors out
            from app.models.schemas import BudgetBreakdown

            budget_breakdown = BudgetBreakdown(
                total_budget=float(profile.budget),
                currency="INR" if "goa" in (profile.destination or "").lower() else "USD",
                guest_count=int(profile.guest_count),
                venue_cost=float(profile.budget) * 0.22,
                catering_cost=float(profile.guest_count) * (2800.0 if "goa" in (profile.destination or "").lower() else 100.0),
                decor_cost=float(profile.budget) * 0.12,
                accommodation_cost=float(profile.budget) * 0.18,
                photography_cost=float(profile.budget) * 0.07,
                entertainment_cost=float(profile.budget) * 0.06,
                misc_cost=float(profile.budget) * 0.09,
                total_estimated=0.0,
                remaining_balance=0.0,
                budget_summary="A simple fallback budget breakdown.",
            )
            budget_breakdown.total_estimated = (
                budget_breakdown.venue_cost
                + budget_breakdown.catering_cost
                + budget_breakdown.decor_cost
                + budget_breakdown.accommodation_cost
                + budget_breakdown.photography_cost
                + budget_breakdown.entertainment_cost
                + budget_breakdown.misc_cost
            )
            budget_breakdown.remaining_balance = budget_breakdown.total_budget - budget_breakdown.total_estimated

        # Optionally generate the design direction spec after creative/logistics
        design_spec = None
        if self.design is not None:
            try:
                design_spec = self.design.generate_design_spec(profile, creative_plan, logistics_plan)
            except Exception:
                try:
                    # Best-effort fallback if the agent exposes a fallback method
                    if hasattr(self.design, "_fallback_spec"):
                        design_spec = self.design._fallback_spec(profile, creative_plan, logistics_plan)
                except Exception:
                    design_spec = None

        # Update the single structured state
        state.creative = creative_plan
        state.logistics = logistics_plan
        state.financial = budget_breakdown
        state.design_spec = design_spec
        state.state_status = "plans_generated"
        state.last_updated = datetime.utcnow().isoformat()

        # Return the same final state object that should be saved by the caller
        return state

    # ---- Update propagation helpers ----
    def update_guest_count(self, state: WeddingState | None, new_guest_count: int) -> WeddingState:
        """Update guest_count and propagate changes across dependent plans.

        - Loads the current WeddingState from disk if `state` is None.
        - Updates `state.profile.guest_count`.
        - Recomputes LogisticsAgent and FinancialAgent outputs deterministically.
        - Keeps CreativeAgent output unchanged unless explicitly requested.
        - Updates `state.state_status` and `last_updated`.
        - Persists the updated state via storage (which re-exports CSV artifacts).
        """
        current = state or self.storage.load_state()
        if current is None:
            raise ValueError("No existing WeddingState available to update.")

        # Update profile guest count
        try:
            new_gc = int(new_guest_count)
        except Exception:
            raise ValueError("new_guest_count must be an integer")

        current.profile.guest_count = max(0, new_gc)

        # Ensure CSV reflects new target row count before planning
        try:
            self.storage.export_guests_csv(current)
        except Exception:
            pass

        # Re-run dependent agents deterministically
        current.logistics = self.logistics.plan_logistics(current.profile)
        current.financial = self.financial.estimate_budget(current.profile)

        # Creative plan remains unchanged
        current.state_status = "updated_after_guest_change"
        current.last_updated = datetime.utcnow().isoformat()

        # Persist and re-export artifacts
        self.storage.save_state(current)
        return current

    def apply_guest_count_update(self, state: WeddingState | None, additional_guests: int) -> WeddingState:
        """Convenience wrapper to increment guest_count by a delta.

        Example: if 20 more guests confirmed, call with additional_guests=20.
        """
        current = state or self.storage.load_state()
        if current is None:
            raise ValueError("No existing WeddingState available to update.")

        try:
            delta = int(additional_guests)
        except Exception:
            raise ValueError("additional_guests must be an integer")

        new_gc = int(max(0, int(current.profile.guest_count) + delta))
        return self.update_guest_count(current, new_gc)
