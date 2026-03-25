from __future__ import annotations

import os
import math
from typing import Any, Dict, List, Optional
from datetime import datetime

import requests


class HotelService:
    """Simple Google Places-backed hotel recommender for CLI use.

    Keeps logic isolated and conservative so that existing flows remain intact.
    If API/network is unavailable, methods return safe fallbacks with messages.
    """

    PRICE_LEVEL_TO_RATE_INR = {
        0: 5000,   # unknown/very budget
        1: 8000,
        2: 12000,
        3: 22000,
        4: 35000,  # luxury
    }

    def __init__(self, api_key: Optional[str] | None = None, session: Optional[requests.Session] = None) -> None:
        self.api_key = (
            api_key
            or os.getenv("GOOGLE_MAPS_API_KEY")
            or os.getenv("GOOGLE_PLACES_API_KEY")
            or os.getenv("GOOGLE_API_KEY")
        )
        self.session = session or requests.Session()

    # ---- Core helpers ----
    def estimate_rooms(self, guest_count: int) -> int:
        """MVP rule: 2 guests per room (ceil)."""
        try:
            gc = max(0, int(guest_count))
        except Exception:
            gc = 0
        return max(0, math.ceil(gc / 2.0))

    def derive_nights(self, wedding_dates: List[str]) -> int:
        """Estimate number of nights from provided dates; fallback=2.

        Attempts to parse ISO-like strings; if at least two dates parse,
        returns inclusive span (at least 2). Otherwise returns 2.
        """
        if not wedding_dates:
            return 2
        parsed: List[datetime] = []
        for d in wedding_dates:
            try:
                # Support 'YYYY-MM-DD' or ISO with time
                parsed.append(datetime.fromisoformat(d.strip()))
            except Exception:
                # Ignore unparseable entries
                pass
        if len(parsed) >= 2:
            parsed.sort()
            days = (parsed[-1].date() - parsed[0].date()).days + 1
            return max(2, days)
        return 2

    # ---- Places API access ----
    def _text_search(self, query: str, region: Optional[str] = None) -> Dict[str, Any]:
        """Call Places Text Search. Returns parsed JSON or error dict."""
        if not self.api_key:
            return {"error": "missing_api_key"}
        url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
        params = {"query": query, "key": self.api_key}
        if region:
            params["region"] = region
        try:
            resp = self.session.get(url, params=params, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            return {"error": str(e)}

    def _price_to_rate(self, price_level: Optional[int]) -> int:
        try:
            pl = int(price_level) if price_level is not None else 0
        except Exception:
            pl = 0
        return int(self.PRICE_LEVEL_TO_RATE_INR.get(pl, 12000))

    def recommend_hotels(self, profile: Any, top_n: int = 5) -> Dict[str, Any]:
        """Return a recommendation payload based on profile.

        The payload includes:
        - rooms_needed
        - nights
        - accommodation_budget_cap
        - currency
        - hotels: list of dict summaries
        - message (optional) on errors/unavailable API
        """
        destination = getattr(profile, "wedding_place", None) or getattr(profile, "destination", None) or ""
        if not destination:
            return {"message": "Destination missing; cannot search for hotels.", "hotels": []}

        guest_count = getattr(profile, "guest_count", 0) or 0
        budget = float(getattr(profile, "budget", 0.0) or 0.0)
        currency = getattr(profile, "currency", "INR") or "INR"

        rooms_needed = self.estimate_rooms(int(guest_count))
        nights = self.derive_nights(getattr(profile, "wedding_dates", []) or [])
        accom_cap = 0.35 * float(budget)

        # Fetch via Places Text Search
        result = self._text_search(f"hotels in {destination}")
        if "error" in result:
            return {
                "rooms_needed": rooms_needed,
                "nights": nights,
                "accommodation_budget_cap": accom_cap,
                "currency": currency,
                "hotels": [],
                "message": f"Hotel recommendations unavailable: {result['error']}",
            }

        status = result.get("status") or result.get("Status")
        if status not in (None, "OK", "ZERO_RESULTS"):
            return {
                "rooms_needed": rooms_needed,
                "nights": nights,
                "accommodation_budget_cap": accom_cap,
                "currency": currency,
                "hotels": [],
                "message": f"Places API status: {status}",
            }

        items: List[Dict[str, Any]] = []
        for r in (result.get("results") or [])[: max(1, top_n * 2)]:
            name = r.get("name") or "Unknown Hotel"
            address = r.get("formatted_address") or ""
            price_level = r.get("price_level")
            avg_rate = self._price_to_rate(price_level)

            # Naive address parse: last tokens as city/country if available
            city = None
            country = None
            if address:
                parts = [p.strip() for p in address.split(",") if p.strip()]
                if len(parts) >= 1:
                    city = parts[-2] if len(parts) >= 2 else parts[-1]
                    country = parts[-1]

            est_total = int(avg_rate * rooms_needed * max(1, nights))
            within_cap = est_total <= accom_cap if accom_cap > 0 else False

            items.append(
                {
                    "name": name,
                    "city": city or destination,
                    "country": country,
                    "avg_room_rate": avg_rate,
                    "rooms_needed": rooms_needed,
                    "nights": nights,
                    "estimated_total_stay_cost": est_total,
                    "wedding_capacity": None,  # Not provided by Places
                    "max_rooms": None,         # Not provided by Places
                    "budget_fit": "within accommodation budget" if within_cap else "exceeds accommodation budget",
                    "notes": "Price estimated from Google price_level; capacity data unavailable",
                }
            )

        # Sort by estimated total stay cost ascending and keep top_n
        items.sort(key=lambda x: x.get("estimated_total_stay_cost", 0))
        items = items[:top_n]

        return {
            "rooms_needed": rooms_needed,
            "nights": nights,
            "accommodation_budget_cap": accom_cap,
            "currency": currency,
            "hotels": items,
        }

