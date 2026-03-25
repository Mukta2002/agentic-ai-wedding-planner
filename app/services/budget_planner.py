from __future__ import annotations

from typing import Dict, List, Tuple


DEFAULT_BREAKDOWN_PCT: Dict[str, float] = {
    "hotel_accommodation_venue": 30.0,
    "catering": 25.0,
    "decor": 15.0,
    "photography_videography": 10.0,
    "outfits_styling": 8.0,
    "entertainment": 5.0,
    "invitations_branding": 2.0,
    "misc_buffer": 5.0,
}


def _round_amounts_to_total(items: List[Tuple[str, float]], total: float) -> Dict[str, int]:
    """Round item amounts to integers while preserving the exact total by
    adjusting the last category with any rounding delta.

    items: list of (category, amount_float)
    returns: dict category -> int amount
    """
    rounded: Dict[str, int] = {}
    running = 0
    for i, (k, v) in enumerate(items):
        if i < len(items) - 1:
            iv = int(round(v))
            rounded[k] = iv
            running += iv
        else:
            # Last bucket absorbs the delta to match total exactly
            rounded[k] = int(round(total - running))
    return rounded


def _compute_breakdown(total_budget: float, pct_map: Dict[str, float]) -> Dict[str, Dict[str, float | int]]:
    # Compute float amounts first
    floats: List[Tuple[str, float]] = []
    for k, pct in pct_map.items():
        amt = (pct / 100.0) * float(total_budget)
        floats.append((k, amt))

    # Stable order for deterministic rounding: use the insertion order of pct_map
    amounts_int = _round_amounts_to_total(floats, float(total_budget))

    return {
        k: {"percentage": float(pct_map[k]), "amount": int(amounts_int[k])}
        for k in pct_map.keys()
    }


def _scale_remaining(defaults: Dict[str, float], new_hotel_pct: float) -> Dict[str, float]:
    """Return new percentage map scaling non-hotel categories proportionally
    to fill the remaining after assigning hotel_accommodation_venue=new_hotel_pct.
    """
    hotel_key = "hotel_accommodation_venue"
    if hotel_key not in defaults:
        raise ValueError("Defaults must include hotel_accommodation_venue")

    # Clamp to sensible bounds
    new_hotel_pct = max(0.0, min(100.0, float(new_hotel_pct)))

    default_hotel = float(defaults[hotel_key])
    remainder = 100.0 - new_hotel_pct
    default_remainder = max(0.0001, 100.0 - default_hotel)

    out: Dict[str, float] = {}
    for k, v in defaults.items():
        if k == hotel_key:
            out[k] = new_hotel_pct
        else:
            out[k] = float(v) * (remainder / default_remainder)
    return out


def print_breakdown_cli(breakdown: Dict[str, Dict[str, float | int]], currency: str = "INR") -> None:
    print("===== Proposed Budget Breakdown =====")
    for key, row in breakdown.items():
        label = {
            "hotel_accommodation_venue": "Hotel / Accommodation / Venue",
            "catering": "Catering",
            "decor": "Decor",
            "photography_videography": "Photography / Videography",
            "outfits_styling": "Outfits / Styling",
            "entertainment": "Entertainment",
            "invitations_branding": "Invitations / Branding",
            "misc_buffer": "Misc / Buffer",
        }.get(key, key)
        pct = row.get("percentage", 0.0)
        amt = row.get("amount", 0)
        try:
            pct_s = f"{float(pct):.1f}%" if float(pct) % 1 else f"{int(float(pct))}%"
        except Exception:
            pct_s = f"{pct}%"
        try:
            amt_s = f"{currency} {int(amt):,}"
        except Exception:
            amt_s = f"{currency} {amt}"
        print(f"- {label:<30} {pct_s:>6}  |  {amt_s}")
    print("=====================================\n")


def confirm_and_apply_breakdown(profile: object) -> None:
    """Interactive confirmation loop. Minimal, additive side-effects on profile:
    - Sets profile.accommodation_budget_share (float in 0..1)
    - Sets profile.confirmed_budget_breakdown (mapping category -> {percentage, amount}) if available
    """
    total = getattr(profile, "wedding_budget", None)
    if total is None:
        total = getattr(profile, "budget", 0.0)
    currency = getattr(profile, "currency", "INR") or "INR"

    # Start from defaults
    current_pct = dict(DEFAULT_BREAKDOWN_PCT)
    breakdown = _compute_breakdown(total, current_pct)
    print_breakdown_cli(breakdown, currency)

    while True:
        ans = input("Does this budget breakdown look okay? Enter Y to continue or N to adjust: ").strip()
        if ans.lower() in ("y", "yes"):
            # Apply hotel share and save breakdown
            hotel_pct = float(current_pct["hotel_accommodation_venue"]) / 100.0
            try:
                # explicit field used by hotel recommender
                setattr(profile, "accommodation_budget_share", hotel_pct)
            except Exception:
                pass
            try:
                setattr(profile, "confirmed_budget_breakdown", breakdown)  # type: ignore[attr-defined]
            except Exception:
                pass
            return
        if ans.lower() in ("n", "no"):
            # Ask only for revised hotel/accommodation percentage
            pct_raw = input("Enter revised hotel/accommodation % (e.g., 30, 35, 40): ").strip()
            try:
                new_pct = float(pct_raw)
                if new_pct <= 0 or new_pct >= 100:
                    print("Please enter a number between 1 and 99.")
                    continue
            except Exception:
                print("Please enter a numeric percentage like 35.")
                continue

            # Recompute remaining categories proportionally to fill 100%
            current_pct = _scale_remaining(DEFAULT_BREAKDOWN_PCT, new_pct)
            breakdown = _compute_breakdown(total, current_pct)
            print_breakdown_cli(breakdown, currency)
            # Loop will ask to confirm again
            continue
        # Any other input: re-prompt concisely
        print("Please enter Y to continue or N to adjust.")

