from __future__ import annotations

from typing import List, Optional

from app.models.schemas import WeddingProfile, CeremonyPlanItem


class CeremonyPlanner:
    """Interactive ceremony intake with minimal, resilient prompts.

    - Asks exactly once per run; skips if `profile.ceremonies` already present.
    - Validates event_date against profile.wedding_dates or accepts Day 1/2/3.
    - Stores results on `profile.ceremonies` as a list of CeremonyPlanItem.
    - Prints a clean summary after collection.
    """

    def _prompt_int(self, label: str, min_value: int = 0) -> int:
        while True:
            raw = input(f"{label}: ").strip()
            try:
                val = int(raw)
                if val >= min_value:
                    return val
            except Exception:
                pass
            print(f"Please enter a whole number >= {min_value}.")

    def _prompt_yn(self, label: str, default: Optional[bool] = None) -> bool:
        while True:
            raw = input(f"{label} ").strip().lower()
            if raw in ("y", "yes"):  # noqa: SIM103
                return True
            if raw in ("n", "no"):
                return False
            if default is not None and raw == "":
                return bool(default)
            print("Please enter 'y' or 'n'.")

    def _prompt_nonempty(self, label: str) -> str:
        while True:
            val = input(f"{label}: ").strip()
            if val:
                return val
            print("Please enter a value.")

    def _prompt_optional(self, label: str) -> Optional[str]:
        val = input(f"{label} ").strip()
        return val if val else None

    def _prompt_palette(self, label: str) -> List[str]:
        raw = input(f"{label} ").strip()
        if not raw:
            return []
        return [p.strip() for p in raw.split(",") if p.strip()]

    def _prompt_date_for_ceremony(self, profile: WeddingProfile) -> str:
        dates = list(profile.wedding_dates or [])
        # Show helpers
        if dates:
            print(f"Available dates: {', '.join(dates)} | or type 'Day 1', 'Day 2', ...")
        else:
            print("No wedding dates present in profile; you may type 'Day 1', 'Day 2', etc.")

        while True:
            raw = input("Which wedding date/day does this ceremony belong to?: ").strip()
            if not raw:
                print("Please enter a date or day label (e.g., 2026-12-10 or Day 1).")
                continue

            rlow = raw.lower()
            # Accept exact match to one of the dates
            if raw in dates:
                return raw
            # Accept Day N variants
            if rlow.startswith("day "):
                try:
                    n = int(rlow.split()[1])
                    if n > 0:
                        return f"Day {n}"
                except Exception:
                    pass
            # Allow simple synonyms like D1
            if rlow.startswith("d") and rlow[1:].strip().isdigit():
                return f"Day {int(rlow[1:].strip())}"

            print("Please enter a valid date from the list or a day label like 'Day 1'.")

    def collect_ceremonies(self, profile: WeddingProfile) -> None:
        try:
            if getattr(profile, "ceremonies", None):
                print("\n===== Ceremony Plan =====\nUsing previously provided values.")
                self.print_summary(profile)
                return

            print("\n===== Ceremony Planning =====")
            total = self._prompt_int("How many ceremonies/functions are planned in total?", min_value=0)
            ceremonies: List[CeremonyPlanItem] = []

            for i in range(1, total + 1):
                print(f"\n-- Ceremony {i} --")
                name = self._prompt_nonempty(
                    "Ceremony name (e.g. Haldi, Mehendi, Sangeet, Wedding, Reception)"
                )
                event_date = self._prompt_date_for_ceremony(profile)
                time_of_day = self._prompt_nonempty(
                    "Time of ceremony (morning / afternoon / evening / specific time)"
                )
                mood = self._prompt_nonempty(
                    "Ceremony mood/theme (royal, floral, vibrant, elegant, traditional, modern, beachy, etc.)"
                )
                palette = self._prompt_palette("Primary color palette for this ceremony (comma-separated):")
                dress_code = self._prompt_nonempty("Dress code for guests")
                guest_note = self._prompt_optional("Any special notes for guests (optional):")
                include_teaser = self._prompt_yn("Should this ceremony be included in the teaser? (y/n):", True)
                include_style = self._prompt_yn(
                    "Should this ceremony be included in the style guide? (y/n):",
                    True,
                )

                ceremonies.append(
                    CeremonyPlanItem(
                        name=name,
                        event_date=event_date,
                        time_of_day=time_of_day,
                        mood=mood,
                        palette=palette or None,
                        dress_code=dress_code,
                        guest_note=guest_note,
                        include_in_teaser=bool(include_teaser),
                        include_in_style_guide=bool(include_style),
                    )
                )

            profile.ceremonies = ceremonies
            self.print_summary(profile)
        except Exception as e:
            # Keep resilient: do not crash overall flow
            print(f"Ceremony planning skipped due to an error: {e}")

    def print_summary(self, profile: WeddingProfile) -> None:
        items = list(getattr(profile, "ceremonies", []) or [])
        print("\n===== Ceremony Plan Summary =====")
        if not items:
            print("No ceremonies added.")
            print("==================================\n")
            return
        for idx, c in enumerate(items, start=1):
            colors = ", ".join(c.palette or []) if getattr(c, "palette", None) else "-"
            print(
                f"{idx}. {c.name} | {c.event_date} | {c.time_of_day} | mood={c.mood} | "
                f"colors={colors} | dress={c.dress_code} | teaser={'Y' if c.include_in_teaser else 'N'} | "
                f"style_guide={'Y' if c.include_in_style_guide else 'N'}"
            )
            if getattr(c, "guest_note", None):
                print(f"    note: {c.guest_note}")
        print("==================================\n")

