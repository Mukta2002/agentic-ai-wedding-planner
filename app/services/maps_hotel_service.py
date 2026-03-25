from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from app.config import get_gemini_api_key, DEFAULT_GEMINI_TEXT_MODEL
from google import genai
from google.genai import types


class MapsHotelService:
    """Gemini + Google Maps-grounded hotel recommendation service.

    This service is additive and does not replace existing hotel logic.
    It consumes the intake profile and asks Gemini (with Google Maps grounding)
    to suggest destination-wedding-appropriate hotels/venues. Results are best-
    effort discovery hints, not live availability or guaranteed pricing.
    """

    def __init__(self, model: str | None = None, timeout_seconds: float = 25.0) -> None:
        api_key = get_gemini_api_key(required=False)
        # If no key is present, keep client as None to gracefully skip
        self.client: Optional[genai.Client] = genai.Client(api_key=api_key) if api_key else None
        # Use a model that supports Google Maps grounding in current SDK.
        # Note: "gemini-2.0-flash" is outdated for new users; defaulting to centralized
        # DEFAULT_GEMINI_TEXT_MODEL (currently "gemini-2.5-flash").
        self.model = model or DEFAULT_GEMINI_TEXT_MODEL
        self.timeout_seconds = timeout_seconds

    # ---- Prompt building ----
    def _build_prompt(self, profile: Any, top_n: int) -> str:
        place = getattr(profile, "wedding_place", None) or getattr(profile, "destination", "")
        guests = getattr(profile, "guest_count", 0)
        budget = getattr(profile, "wedding_budget", None)
        if budget is None:
            budget = getattr(profile, "budget", 0.0)
        currency = getattr(profile, "currency", "INR") or "INR"
        dates = getattr(profile, "wedding_dates", []) or []

        date_str = ", ".join(map(str, dates)) if dates else "(dates flexible)"

        # Ask for structured JSON to simplify normalization
        # Escape curly braces in the JSON example to avoid f-string formatting errors
        instructions = (
            f"You are a wedding planning assistant. Using Google Maps grounding, recommend {top_n} hotels or resorts suitable for hosting a destination wedding in or near \"{place}\".\n\n"
            "Context:\n"
            f"- Guest count: {guests}\n"
            f"- Total wedding budget: {budget} {currency}\n"
            f"- Wedding dates: {date_str}\n\n"
            "Guidance:\n"
            "- Prioritize venues with wedding/event suitability (ballrooms, lawns, capacity for approx. guest count).\n"
            "- Include a short reason for fit (capacity, venue spaces, reputation, suitability for weddings).\n"
            "- Include pricing hints if any are commonly available (do not invent exact prices). Use approximate language.\n"
            "- Provide any nearby/local context that might help with destination planning.\n"
            "- Be conservative: this is discovery only; do not claim real-time availability or quotes.\n\n"
            "Return JSON only with this structure:\n"
            "{{\n"
            "  \"recommendations\": [\n"
            "    {{\n"
            "      \"name\": \"string\",\n"
            "      \"location\": \"city or area\",\n"
            "      \"reason\": \"short reason it may fit\",\n"
            "      \"pricing_hints\": \"optional string\",\n"
            "      \"wedding_suitability\": \"optional string\",\n"
            "      \"nearby_context\": \"optional string\"\n"
            "    }}\n"
            "  ]\n"
            "}}\n"
        ).strip()
        # Override previous JSON-style guidance with plain-text format to avoid unsupported JSON-mode.
        instructions = (
            f"You are a wedding planning assistant. Using Google Maps grounding, recommend {top_n} hotels or resorts suitable for hosting a destination wedding in or near \"{place}\".\n\n"
            "Context:\n"
            f"- Guest count: {guests}\n"
            f"- Total wedding budget: {budget} {currency}\n"
            f"- Wedding dates: {date_str}\n\n"
            "Guidance:\n"
            "- Prioritize venues with wedding/event suitability (ballrooms, lawns, capacity for approx. guest count).\n"
            "- Prefer hotels that are realistically compatible with the provided budget; include upscale and mid-range options as needed.\n"
            "- Avoid recommending only iconic ultra-luxury properties if the budget is limited.\n"
            "- Include a short reason for fit (capacity, venue spaces, reputation, suitability for weddings).\n"
            "- Include pricing hints if any are commonly available (do not invent exact prices). Use approximate language.\n"
            "- Provide any nearby/local context that might help with destination planning.\n"
            "- Be conservative: this is discovery only; do not claim real-time availability or quotes.\n\n"
            "Return plain text in this exact block format for each hotel, separated by a blank line:\n"
            "Hotel: <name>\n"
            "Location: <city/state/country>\n"
            "Why it fits: <short reason>\n"
            "Pricing hint: <if available, else N/A>\n"
            "Capacity hint: <if available, else N/A>\n"
        ).strip()
        # Add stronger budget-conscious bias when requested
        try:
            if bool(getattr(profile, "prefer_budget_hotels", False)):
                instructions += (
                    "\n\nAdditional bias: Strongly favor budget-conscious, mid-range, value-for-money wedding-friendly properties. "
                    "Deprioritize ultra-luxury unless clearly budget-compatible."
                )
        except Exception:
            pass
        return instructions

    # ---- Normalization ----
    def _extract_json(self, text: str) -> Optional[Dict[str, Any]]:
        if not text:
            return None
        # Try direct JSON first
        try:
            return json.loads(text)
        except Exception:
            pass
        # Try to locate a JSON block in the text
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            snippet = text[start : end + 1]
            try:
                return json.loads(snippet)
            except Exception:
                return None
        return None

    def _normalize(self, payload: Dict[str, Any], fallback_place: str) -> Dict[str, Any]:
        items: List[Dict[str, Any]] = []
        for r in (payload or {}).get("recommendations", []) or []:
            name = (r or {}).get("name") or "Unknown Hotel"
            location = (r or {}).get("location") or fallback_place
            reason = (r or {}).get("reason") or ""
            pricing = (r or {}).get("pricing_hints") or None
            suitability = (r or {}).get("wedding_suitability") or None
            nearby = (r or {}).get("nearby_context") or None
            items.append(
                {
                    "name": name,
                    "location": location,
                    "reason": reason,
                    "pricing_hints": pricing,
                    "wedding_suitability": suitability,
                    "nearby_context": nearby,
                }
            )
        return {"recommendations": items}

    # ---- Public API ----
    def recommend_hotels(self, profile: Any, top_n: int = 5) -> Dict[str, Any]:
        """Return normalized Maps-grounded hotel recommendations.

        On failure or missing API key, returns {"recommendations": [], "message": str}.
        """
        place = getattr(profile, "wedding_place", None) or getattr(profile, "destination", None) or ""
        if not place:
            return {"recommendations": [], "message": "Destination missing; cannot request Maps-grounded recommendations."}
        if self.client is None:
            return {
                "recommendations": [],
                "message": "Gemini API key not found. Skipping Maps-grounded hotel recommendations.",
            }

        prompt = self._build_prompt(profile, top_n)
        try:
            # google-genai 1.67.0: tools should be provided under config, not as a top-level kwarg
            resp = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config={
                    "tools": [types.Tool(google_maps=types.GoogleMaps())],
                },
            )
        except Exception as e:
            return {"recommendations": [], "message": f"Gemini Maps-grounded call failed: {e}"}

        # Extract text and parse plain-text recommendations
        text = getattr(resp, "text", None) or ""
        items = self._parse_plaintext_recommendations(text, fallback_place=place)
        if items:
            # Enrich with pricing + budget estimations, dedupe and sort
            enriched = self._enrich_with_budget(profile, items)

            # Filter to only budget-fit items per strict rule
            in_budget = [
                h for h in enriched
                if isinstance(h.get("estimated_total_cost"), (int, float))
                and isinstance(h.get("accommodation_budget_cap"), (int, float))
                and float(h.get("estimated_total_cost")) <= float(h.get("accommodation_budget_cap"))
            ]

            # Keep a hidden/internal list of nearest over-budget options for future use
            over_budget = [h for h in enriched if h not in in_budget]
            # Sort over-budget by how close they are to budget (ascending ratio over 1.0)
            def _over_ratio(h: Dict[str, Any]) -> float:
                try:
                    total = float(h.get("estimated_total_cost") or 0.0)
                    cap = float(h.get("accommodation_budget_cap") or 1.0)
                    return (total / cap) if cap > 0 else float("inf")
                except Exception:
                    return float("inf")

            over_budget.sort(key=_over_ratio)

            # Sort in-budget by estimated total cost ascending
            in_budget.sort(key=lambda x: float(x.get("estimated_total_cost") or 0.0))

            payload: Dict[str, Any] = {"recommendations": in_budget}
            if over_budget:
                payload["_nearest_over_budget_candidates"] = over_budget  # hidden use, not printed in CLI
            # If none fit, attach a message for the CLI to show
            if not in_budget:
                payload["message"] = (
                    "No Gemini hotel recommendations fit the current estimated accommodation budget."
                )
            return payload
        # Fallback: no parseable items. Return raw text so CLI can show it instead of failing.
        return {"recommendations": [], "message": "Unparsed response; showing raw text.", "raw_text": text}

    # ---- Plain-text parsing ----
    def _parse_plaintext_recommendations(self, text: str, fallback_place: str) -> List[Dict[str, Any]]:
        lines = [l.strip() for l in (text or "").splitlines()]
        items: List[Dict[str, Any]] = []

        current: Dict[str, Any] = {}

        def flush_current() -> None:
            nonlocal current
            if any(current.values()):
                name = current.get("name") or "Unknown Hotel"
                location = current.get("location") or fallback_place or "N/A"
                reason = current.get("reason") or "N/A"
                pricing = current.get("pricing_hints") or "N/A"
                capacity = current.get("wedding_suitability") or current.get("capacity") or "N/A"
                items.append(
                    {
                        "name": name,
                        "location": location,
                        "reason": reason,
                        "pricing_hints": pricing,
                        "wedding_suitability": capacity,
                        "nearby_context": current.get("nearby_context") or "N/A",
                    }
                )
            current = {}

        for raw in lines:
            if not raw:
                # Blank line separates entries
                flush_current()
                continue
            lower = raw.lower()
            if lower.startswith("hotel:"):
                # New block starts; flush previous if any
                if any(current.values()):
                    flush_current()
                current["name"] = raw.split(":", 1)[1].strip() or "Unknown Hotel"
            elif lower.startswith("location:"):
                current["location"] = raw.split(":", 1)[1].strip() or fallback_place or "N/A"
            elif lower.startswith("why it fits:"):
                current["reason"] = raw.split(":", 1)[1].strip() or "N/A"
            elif lower.startswith("pricing hint:"):
                current["pricing_hints"] = raw.split(":", 1)[1].strip() or "N/A"
            elif lower.startswith("capacity hint:"):
                # Map capacity hint to wedding_suitability for display compatibility
                current["wedding_suitability"] = raw.split(":", 1)[1].strip() or "N/A"
            else:
                # Attach any other lines to reason if present, else ignore silently
                if current.get("reason"):
                    current["reason"] = (current.get("reason") + " " + raw).strip()

        # Flush last collected block
        flush_current()

        # Deduplicate by (name, location) case-insensitive to avoid repeats
        seen = set()
        unique: List[Dict[str, Any]] = []
        for it in items:
            name = (it.get("name") or "").strip()
            loc = (it.get("location") or "").strip()
            key = (name.lower(), loc.lower())
            if key in seen:
                continue
            seen.add(key)
            # Ensure missing values are represented as "N/A"
            unique.append(
                {
                    "name": name or "Unknown Hotel",
                    "location": loc or (fallback_place or "N/A"),
                    "reason": it.get("reason") or "N/A",
                    "pricing_hints": it.get("pricing_hints") or "N/A",
                    "wedding_suitability": it.get("wedding_suitability") or "N/A",
                    "nearby_context": it.get("nearby_context") or "N/A",
                }
            )

        return unique

    # ---- Estimation helpers ----
    def _estimate_rooms(self, guest_count: Any) -> int:
        try:
            gc = max(0, int(guest_count or 0))
        except Exception:
            gc = 0
        # 2 guests per room
        return (gc + 1) // 2 if gc > 0 else 0

    def _derive_nights(self, wedding_dates: Any) -> int:
        from datetime import datetime

        dates = wedding_dates or []
        if not isinstance(dates, list):
            return 2
        parsed = []
        for d in dates:
            try:
                parsed.append(datetime.fromisoformat(str(d).strip()))
            except Exception:
                pass
        if len(parsed) >= 2:
            parsed.sort()
            days = (parsed[-1].date() - parsed[0].date()).days + 1
            return max(2, days)
        return 2

    def _estimate_rate_from_hint(self, hint: str | None) -> int:
        """Map qualitative pricing hints to an approximate INR nightly rate.

        Ranges (midpoint used):
          - Very expensive: 30,000–60,000 => 45,000
          - High-end luxury: 25,000–50,000 => 37,500
          - Upscale: 10,000–25,000 => 17,500
          - Mid-range: 5,000–12,000 => 8,500
        Missing/unknown => 20,000 (conservative)
        """
        if not hint:
            return 20000
        h = hint.lower()
        if "very expensive" in h:
            return 45000
        if "high-end luxury" in h or "high end luxury" in h or "luxury" in h:
            return 37500
        if "upscale" in h:
            return 17500
        if "mid-range" in h or "midrange" in h or "mid range" in h:
            return 8500
        # Fallback conservative estimate
        return 20000

    def _budget_status(self, total: float, cap: float) -> str:
        if cap <= 0:
            return "Exceeds budget"
        if total <= cap:
            return "Within budget"
        # Slightly over if within 10% over cap
        if total <= cap * 1.10:
            return "Slightly over budget"
        return "Exceeds budget"

    def _enrich_with_budget(self, profile: Any, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        # Extract inputs from profile
        # Allow revised overrides from profile for interactive retries
        override_gc = getattr(profile, "revised_guest_count", None)
        try:
            guest_count = int(override_gc) if override_gc is not None and int(override_gc) > 0 else int(getattr(profile, "guest_count", 0) or 0)
        except Exception:
            guest_count = int(getattr(profile, "guest_count", 0) or 0)
        budget = getattr(profile, "wedding_budget", None)
        if budget is None:
            budget = getattr(profile, "budget", 0.0) or 0.0
        currency = getattr(profile, "currency", "INR") or "INR"
        # Nights may be overridden by user
        nights_override = getattr(profile, "selected_nights_override", None)
        try:
            nights = int(nights_override) if nights_override is not None and int(nights_override) > 0 else self._derive_nights(getattr(profile, "wedding_dates", []) or [])
        except Exception:
            nights = self._derive_nights(getattr(profile, "wedding_dates", []) or [])
        rooms = self._estimate_rooms(guest_count)
        # Accommodation budget share may be overridden by user
        share = getattr(profile, "accommodation_budget_share", None)
        try:
            share_val = float(share) if share is not None else 0.35
        except Exception:
            share_val = 0.35
        if share_val <= 0:
            share_val = 0.35
        accom_cap = share_val * float(budget)

        enriched: List[Dict[str, Any]] = []
        for it in items:
            rate = self._estimate_rate_from_hint(it.get("pricing_hints"))
            total = int(rate * max(1, rooms) * max(1, nights))
            status = self._budget_status(total, accom_cap)
            enriched.append(
                {
                    **it,
                    "currency": currency,
                    "estimated_room_rate": int(rate),
                    "estimated_total_cost": int(total),
                    "budget_status": status,
                    "rooms_needed": int(rooms),
                    "nights": int(nights),
                    "accommodation_budget_cap": float(accom_cap),
                }
            )

        # Sort: within budget first, then by total cost ascending
        def sort_key(x: Dict[str, Any]):
            status = x.get("budget_status") or "Exceeds budget"
            within_rank = 0 if status == "Within budget" else (1 if status == "Slightly over budget" else 2)
            return (within_rank, x.get("estimated_total_cost", 0))

        enriched.sort(key=sort_key)
        # Keep only top_n if desired at call site (we already request top_n from model)
        return enriched
