from __future__ import annotations

import math
from typing import Dict, Iterable, List, Optional, Tuple

from app.prompts.logistics_prompts import SCHEDULE_PROMPT
from app.models.schemas import WeddingProfile, LogisticsPlan
from app.services.storage import Storage


class LogisticsAgent:
    """Logistics keeps deterministic math in Python.

    - Embeddings are used for semantic matching tasks (optional if router
      provided): e.g., map guest preferences to room/event categories.
    - Text generation is used only for human-readable summaries/notes.
    """

    def __init__(self, router: Optional[object] = None, storage: Optional[Storage] = None) -> None:
        self.router = router
        self.storage = storage

    def plan_schedule(self, guest_count: int = 0) -> dict:
        """Backward-compatible helper returning a minimal schedule dict.

        Retained for tests and legacy callers. New structured planning uses
        `plan_logistics` with a `WeddingProfile` to produce `LogisticsPlan`.
        """
        _ = SCHEDULE_PROMPT  # Reserved for summary generation
        return {
            "ceremony": "2:00 PM",
            "reception": "6:00 PM",
            "guests": int(max(0, guest_count)),
        }

    # ---- Structured deterministic logistics planning ----
    def plan_logistics(self, profile: WeddingProfile) -> LogisticsPlan:
        """Produce a structured `LogisticsPlan` using confirmed RSVPs only.

        Deterministic rules (planner-side):
        - catering_headcount = confirmed_guest_count
        - room allocation from confirmed guests only:
          * ~60% assigned to double rooms (2 guests per room, enforce even)
          * ~20% assigned to family suites (4 guests per suite, enforce multiple of 4)
          * remaining assigned to standard rooms (1 guest per room)
        - pending/declined guests remain unassigned
        - guests.csv is updated to reflect assigned_room_type for confirmed guests
        - event schedule generated from profile
        """
        # Ensure guest sheet exists and matches target size if storage available
        if self.storage is not None:
            try:
                # Create/migrate and pad to target guest_count
                from app.models.schemas import WeddingState, CreativePlan, BudgetBreakdown
                # Lightweight state only for CSV sizing; content not persisted here
                tmp_state = WeddingState(
                    profile=profile,
                    creative=None,
                    logistics=None,
                    financial=None,
                    state_status="logistics_precheck",
                    last_updated="",
                )
                self.storage.export_guests_csv(tmp_state)
            except Exception:
                pass

        # Load guests and normalize RSVP statuses
        guests_rows: List[dict] = self.storage.read_guests() if self.storage else []

        def norm_status(s: Optional[str]) -> str:
            v = (s or "").strip().lower()
            if v in {"confirmed", "yes", "y"}:
                return "confirmed"
            if v in {"declined", "no", "n"}:
                return "declined"
            return "pending"

        for r in guests_rows:
            r["rsvp_status"] = norm_status(r.get("rsvp_status"))

        # Compute counts
        confirmed = [r for r in guests_rows if r.get("rsvp_status") == "confirmed"]
        pending = [r for r in guests_rows if r.get("rsvp_status") == "pending"]
        declined = [r for r in guests_rows if r.get("rsvp_status") == "declined"]

        confirmed_guest_count = int(len(confirmed))
        pending_guest_count = int(len(pending))
        declined_guest_count = int(len(declined))
        catering_headcount = confirmed_guest_count

        # Deterministic assignment for confirmed guests
        # Order confirmed guests by numeric guest_id if possible
        def gid_key(row: dict) -> Tuple[int, str]:
            gid = str(row.get("guest_id", ""))
            try:
                return (int(gid), gid)
            except Exception:
                return (10**9, gid)

        confirmed_sorted = sorted(confirmed, key=gid_key)

        # Quotas by guest count
        total_c = confirmed_guest_count
        double_guest_quota = int(round(0.60 * total_c))
        # enforce even
        if double_guest_quota % 2 == 1:
            double_guest_quota -= 1
        double_guest_quota = max(0, min(double_guest_quota, total_c))

        remaining_after_double = max(0, total_c - double_guest_quota)

        family_guest_quota = int(round(0.20 * total_c))
        # enforce multiple of 4
        family_guest_quota -= (family_guest_quota % 4)
        family_guest_quota = max(0, min(family_guest_quota, remaining_after_double - (remaining_after_double % 4)))

        remaining_guests = max(0, total_c - (double_guest_quota + family_guest_quota))

        # Build room allocation counts
        double_rooms = double_guest_quota // 2
        family_suites = family_guest_quota // 4
        standard_rooms = remaining_guests

        room_allocation: List[dict] = []
        if double_rooms > 0:
            room_allocation.append({"room_type": "double", "count": int(double_rooms)})
        if family_suites > 0:
            room_allocation.append({"room_type": "family_suite", "count": int(family_suites)})
        if standard_rooms > 0:
            room_allocation.append({"room_type": "standard", "count": int(standard_rooms)})

        # Assign room types to confirmed guests deterministically
        idx = 0
        for i in range(double_guest_quota):
            if i < len(confirmed_sorted):
                confirmed_sorted[i]["assigned_room_type"] = "double"
        idx += double_guest_quota
        for i in range(family_guest_quota):
            if idx + i < len(confirmed_sorted):
                confirmed_sorted[idx + i]["assigned_room_type"] = "family_suite"
        idx += family_guest_quota
        for i in range(remaining_guests):
            if idx + i < len(confirmed_sorted):
                confirmed_sorted[idx + i]["assigned_room_type"] = "standard"

        # Clear assignment for non-confirmed
        for r in pending + declined:
            r["assigned_room_type"] = ""

        # Merge back into original order rows by guest_id
        if self.storage is not None and guests_rows:
            by_id = {r.get("guest_id"): r for r in confirmed_sorted + pending + declined}
            merged: List[dict] = []
            for r in guests_rows:
                gid = r.get("guest_id")
                merged.append(by_id.get(gid, r))
            # Persist updated guests
            try:
                self.storage.write_guests(merged)
            except Exception:
                pass

        # Event schedule and summary
        event_schedule = self._generate_event_schedule(profile)
        logistics_summary = self._generate_summary(profile, catering_headcount, room_allocation, event_schedule)

        return LogisticsPlan(
            confirmed_guest_count=confirmed_guest_count,
            pending_guest_count=pending_guest_count,
            declined_guest_count=declined_guest_count,
            catering_headcount=catering_headcount,
            room_allocation=room_allocation,
            event_schedule=event_schedule,
            logistics_summary=logistics_summary,
        )

    def _generate_event_schedule(self, profile: WeddingProfile) -> List[dict]:
        dates = list(profile.wedding_dates or [])
        # Use first two dates if available; else fallback to placeholders
        d1 = dates[0] if len(dates) >= 1 else "2026-12-10"
        d2 = dates[1] if len(dates) >= 2 else d1

        if (profile.destination or "").strip().lower() == "goa":
            # Goa destination flow
            return [
                {"event": "Welcome Dinner & Sangeet", "date": d1, "time": "7:00 PM"},
                {"event": "Wedding Ceremony", "date": d2, "time": "2:00 PM"},
                {"event": "Reception", "date": d2, "time": "6:00 PM"},
            ]
        # Generic fallback schedule
        return [
            {"event": "Welcome Dinner", "date": d1, "time": "7:00 PM"},
            {"event": "Wedding Ceremony", "date": d2, "time": "2:00 PM"},
            {"event": "Reception", "date": d2, "time": "6:00 PM"},
        ]

    def _generate_summary(
        self,
        profile: WeddingProfile,
        catering_headcount: int,
        room_allocation: List[dict],
        event_schedule: List[dict],
    ) -> str:
        # Prepare a concise deterministic fallback summary
        destination = profile.destination
        rooms_str = ", ".join(f"{r['count']} {r['room_type'].replace('_', ' ')}" for r in room_allocation)
        first_event = event_schedule[0]["event"] if event_schedule else "Welcome Dinner"
        last_event = event_schedule[-1]["event"] if event_schedule else "Reception"

        fallback = (
            f"Planning for {catering_headcount} guests in {destination}. "
            f"Rooms allocated as: {rooms_str}. "
            f"The flow starts with {first_event} and concludes with {last_event}."
        )

        if not self.router or not hasattr(self.router, "generate_text"):
            return fallback

        # Use the text model to polish the paragraph
        prompt = (
            "Write a polished, 2-3 sentence logistics summary for a destination wedding. "
            "Keep it under 60 words. "
            f"Destination: {destination}. Guests: {catering_headcount}. "
            f"Rooms: {rooms_str}. Schedule: {event_schedule}."
        )
        try:
            return self.router.generate_text(prompt)
        except Exception:
            return fallback

    # ---- Embedding-based semantic matching (optional) ----
    def match_preferences_to_categories(
        self, preferences: Iterable[str], categories: Iterable[str]
    ) -> List[Tuple[str, str, float]]:
        """Match each preference to the closest category using embeddings.

        Returns a list of (preference, best_category, similarity).
        Falls back to naive string overlap if no router/embeddings.
        """
        prefs = list(preferences)
        cats = list(categories)
        if not prefs or not cats:
            return []

        if not self.router or not hasattr(self.router, "generate_embedding"):
            # Fallback: naive token overlap score
            def score(a: str, b: str) -> float:
                sa, sb = set(a.lower().split()), set(b.lower().split())
                return len(sa & sb) / (len(sa | sb) or 1)

            results = []
            for p in prefs:
                best_cat, best_s = max(((c, score(p, c)) for c in cats), key=lambda x: x[1])
                results.append((p, best_cat, float(best_s)))
            return results

        # Use cosine similarity on embeddings
        def embed(text: str) -> List[float]:
            return self.router.generate_embedding(text)

        cat_vecs = [(c, embed(c)) for c in cats]

        def cosine(a: List[float], b: List[float]) -> float:
            if not a or not b or len(a) != len(b):
                return 0.0
            dot = sum(x * y for x, y in zip(a, b))
            na = math.sqrt(sum(x * x for x in a))
            nb = math.sqrt(sum(y * y for y in b))
            if na == 0 or nb == 0:
                return 0.0
            return float(dot / (na * nb))

        results: List[Tuple[str, str, float]] = []
        for p in prefs:
            pv = embed(p)
            best_cat, best_s = max(((c, cosine(pv, v)) for c, v in cat_vecs), key=lambda x: x[1])
            results.append((p, best_cat, float(best_s)))
        return results

    # ---- Human-readable summary via text generation (optional) ----
    def schedule_summary(self, schedule: Dict[str, object]) -> str:
        """Return a human-readable summary using text generation.

        Uses `gemini-2.5-flash` and is safe to skip if router not provided.
        """
        if not self.router or not hasattr(self.router, "generate_text"):
            # Minimal deterministic fallback
            return f"Ceremony at {schedule.get('ceremony')}, Reception at {schedule.get('reception')}"

        prompt = (
            "Write a concise, friendly schedule summary for wedding guests. "
            f"Data: {schedule}. Keep it under 60 words."
        )
        return self.router.generate_text(prompt)
