from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from app.models.schemas import WeddingProfile
from app.services.llm_client import LLMClient


def _safe_parse_json(text: str) -> Dict[str, Any]:
    try:
        return json.loads(text)
    except Exception:
        # Heuristic: extract first JSON object
        import re

        try:
            m = re.search(r"\{[\s\S]*\}", text)
            if m:
                return json.loads(m.group(0))
        except Exception:
            pass
    return {}


def _fallback_sections(
    profile: WeddingProfile,
    include_rsvp: Optional[bool],
    selected_hotel: Optional[str],
) -> Dict[str, Any]:
    bride = (profile.bride_name or "").strip()
    groom = (profile.groom_name or "").strip()
    names_line = f"{bride} & {groom}".strip(" & ") or "Our Couple"
    # Dates
    date_line = ", ".join([d for d in (profile.wedding_dates or []) if d])
    # Place / venue
    place = (getattr(profile, "wedding_place", None) or profile.destination or "").strip()
    venue_line = selected_hotel or ""
    rsvp_line = "" if not include_rsvp else "Kindly RSVP at your earliest convenience"

    return {
        "header_line": "Together with their families",
        "names_line": names_line,
        "body_lines": [
            "cordially invite you to celebrate their wedding",
        ],
        "date_line": date_line,
        "venue_line": venue_line,
        "place_line": place,
        "rsvp_line": rsvp_line,
    }


def generate_invitation_copy(
    profile: WeddingProfile,
    *,
    theme_hint: Optional[str] = None,
    include_rsvp: Optional[bool] = None,
    include_venue_details: Optional[bool] = None,
    selected_hotel: Optional[str] = None,
) -> Dict[str, Any]:
    """Use Gemini to generate polished invitation copy sections.

    Returns a dict like:
    {
      "header_line": str,
      "names_line": str,
      "body_lines": [str, ...],
      "date_line": str,
      "venue_line": str,
      "place_line": str,
      "rsvp_line": str,
    }
    """
    client = LLMClient()
    # Minimal explicit log about the text model used
    print(f"[InviteCopy] generate_invitation_copy -> model={client.model}")

    couple = f"{profile.bride_name} & {profile.groom_name}"
    place = (getattr(profile, "wedding_place", None) or profile.destination or "").strip()
    dates = ", ".join([d for d in (profile.wedding_dates or []) if d])

    # Provide creative context and strict output schema
    prompt = (
        "You are a wedding copywriter. Based on the couple and details, write a polished, "
        "elegant invitation suitable for a premium printed card. Keep it tasteful, concise, and split into clear lines.\n\n"
        f"Couple: {couple}\n"
        f"Destination/Place: {place}\n"
        f"Dates (verbatim): {dates}\n"
        f"Include RSVP line: {bool(include_rsvp)}\n"
        f"Include venue details: {bool(include_venue_details)}\n"
        f"Selected hotel/venue (if any): {selected_hotel or ''}\n"
        f"Theme/Style hint (optional): {theme_hint or ''}\n\n"
        "Style guidance (reflect dynamically, do not hardcode):\n"
        "- header_line: Hosting line (e.g., 'Together with their families') or an elegant alternative.\n"
        "- names_line: Couple names as a centerpiece line.\n"
        "- body_lines: 1–3 short lines: a compact invite phrase (e.g., 'joyfully invite you...'), plus 0–2 elegant supporting lines.\n"
        "- date_line: A concise formatted date or compact summary (single line).\n"
        "- venue_line: Venue or hotel only when venue details are included and available.\n"
        "- place_line: City/region.\n"
        "- rsvp_line: Only include a short RSVP sentence if Include RSVP line is true; otherwise make it an empty string.\n\n"
        "Return ONLY valid JSON with EXACTLY these keys and no extra commentary:\n"
        "{\n"
        "  \"header_line\": string,\n"
        "  \"names_line\": string,\n"
        "  \"body_lines\": array of 1-3 strings,\n"
        "  \"date_line\": string,\n"
        "  \"venue_line\": string,\n"
        "  \"place_line\": string,\n"
        "  \"rsvp_line\": string\n"
        "}\n"
        "Constraints: Do not include labels like 'Bride:' or any raw field names. Keep each line short and elegant; avoid multi-sentence paragraphs."
    )

    try:
        text = client.generate_text(prompt)
        data = _safe_parse_json(text)
        # Minimal validation and fallback fill
        if not isinstance(data, dict):
            raise ValueError("parsed data not a dict")
        for key in [
            "header_line",
            "names_line",
            "body_lines",
            "date_line",
            "venue_line",
            "place_line",
            "rsvp_line",
        ]:
            if key not in data:
                raise ValueError(f"missing key: {key}")
        # Coerce body_lines
        bl = data.get("body_lines")
        if not isinstance(bl, list):
            data["body_lines"] = [str(bl)] if bl is not None else []
        return {
            "header_line": str(data.get("header_line", "")).strip(),
            "names_line": str(data.get("names_line", "")).strip(),
            "body_lines": [str(x).strip() for x in (data.get("body_lines") or []) if str(x).strip()],
            "date_line": str(data.get("date_line", "")).strip(),
            "venue_line": str(data.get("venue_line", "")).strip(),
            "place_line": str(data.get("place_line", "")).strip(),
            "rsvp_line": str(data.get("rsvp_line", "")).strip(),
        }
    except Exception as e:
        print(f"[InviteCopy] fallback due to error: {e}")
        return _fallback_sections(profile, include_rsvp, selected_hotel)
