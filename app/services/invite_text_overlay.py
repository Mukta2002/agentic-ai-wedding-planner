from __future__ import annotations

import os
from typing import Dict, List, Optional
from datetime import datetime

try:
    from PIL import Image, ImageDraw, ImageFont
except Exception:  # Pillow not guaranteed in requirements, but used elsewhere in repo
    Image = None  # type: ignore
    ImageDraw = None  # type: ignore
    ImageFont = None  # type: ignore


def _load_font(size: int = 56) -> Optional["ImageFont.ImageFont"]:  # type: ignore
    try:
        if ImageFont is None:
            return None
        # Try a commonly available font; fall back to default
        for name in ["arial.ttf", "DejaVuSans.ttf"]:
            try:
                return ImageFont.truetype(name, size=size)
            except Exception:
                pass
        return ImageFont.load_default()
    except Exception:
        return None


def _format_date_pretty(raw: str) -> str:
    s = (raw or "").strip()
    if not s:
        return s
    # Try common formats; fall back to original
    fmts = [
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%Y/%m/%d",
        "%d %b %Y",
        "%d %B %Y",
    ]
    for f in fmts:
        try:
            dt = datetime.strptime(s, f)
            # Invite-friendly: '10 December 2026'
            return dt.strftime("%d %B %Y").lstrip("0")
        except Exception:
            continue
    return s


def _compose_lines(payload: Dict) -> List[str]:
    bride = str(payload.get("bride_name", "")).strip()
    groom = str(payload.get("groom_name", "")).strip()
    dates = [str(d).strip() for d in (payload.get("wedding_dates") or []) if str(d).strip()]
    place = str(payload.get("wedding_place", "")).strip()
    include_venue = bool(payload.get("include_venue_details"))
    hotel = str(payload.get("selected_hotel") or "").strip()
    include_rsvp = bool(payload.get("include_rsvp"))

    # Wording prefs (optional)
    style = str(payload.get("invite_wording_style") or "").strip().lower()
    with_families = payload.get("invite_together_with_families")
    include_blessing = payload.get("invite_include_short_blessing")
    phrase = str(payload.get("invite_invitation_phrase") or "").strip().lower()
    rsvp_style = str(payload.get("invite_rsvp_sentence_style") or "").strip().lower()
    ceremony_summary_lines = payload.get("ceremony_summary_lines") or []

    # Map invitation phrase
    phrase_map = {
        "request the honor of your presence": "request the honor of your presence",
        "cordially invite you": "cordially invite you",
        "invite you to celebrate": "invite you to celebrate",
    }
    # Defaults by style if not explicitly chosen
    if not phrase:
        if style in ("formal", "royal"):
            phrase = "request the honor of your presence"
        elif style in ("warm", "modern elegant"):
            phrase = "cordially invite you"
        else:
            phrase = "invite you to celebrate"
    phrase_text = phrase_map.get(phrase, phrase)

    lines: List[str] = []

    # Opening line
    if with_families is True:
        lines.append("Together with their families")
    elif style == "royal":
        lines.append("In the presence of their loved ones")

    # Names
    if bride or groom:
        lines.append(f"{bride} & {groom}".strip())

    # Invitation sentence
    lines.append(f"{phrase_text} to their wedding celebration")

    # Optional blessing/celebratory line
    if include_blessing is True:
        if style in ("formal", "royal"):
            lines.append("with joyous hearts and blessings")
        else:
            lines.append("to celebrate love, laughter, and happily ever after")

    # Dates or compact ceremony summary
    if ceremony_summary_lines and isinstance(ceremony_summary_lines, list):
        lines.extend([str(x) for x in ceremony_summary_lines if str(x).strip()])
    else:
        for d in dates:
            lines.append(_format_date_pretty(d))

    # Place and optional venue/hotel
    if place:
        lines.append(place)
    if include_venue and hotel:
        lines.append(hotel)

    # RSVP
    if include_rsvp:
        if rsvp_style == "short":
            lines.append("Kindly RSVP at the earliest")
        else:
            lines.append("RSVP")

    return [ln for ln in lines if ln]


def validate_payload(payload: Dict) -> Optional[str]:
    # Required: bride, groom, at least one date, place
    if not (payload.get("bride_name") and payload.get("groom_name")):
        return "Missing bride or groom name"
    dates = payload.get("wedding_dates") or []
    if not isinstance(dates, list) or len([d for d in dates if d]):
        pass
    else:
        return "Missing wedding dates"
    if not payload.get("wedding_place"):
        return "Missing wedding place"
    return None


def render_invite_text(background_path: str, payload: Dict, out_path: str) -> Dict:
    """Overlay exact invite text using confirmed payload onto a background image.

    Returns a dict with info: { ok: bool, path, exists, error, fields }
    """
    fields = {
        "bride_name": payload.get("bride_name"),
        "groom_name": payload.get("groom_name"),
        "wedding_dates": payload.get("wedding_dates"),
        "wedding_place": payload.get("wedding_place"),
        "selected_hotel": payload.get("selected_hotel"),
        "include_venue_details": payload.get("include_venue_details"),
        "include_rsvp": payload.get("include_rsvp"),
    }

    # Validation/echo — printed by caller for transparency before saving
    err = validate_payload(payload)
    if err is not None:
        return {"ok": False, "path": out_path, "exists": False, "error": err, "fields": fields}

    if Image is None:
        return {"ok": False, "path": out_path, "exists": False, "error": "Pillow not available", "fields": fields}

    try:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
    except Exception:
        pass

    try:
        bg = Image.open(background_path).convert("RGBA")
    except Exception as e:
        return {"ok": False, "path": out_path, "exists": False, "error": f"background open failed: {e}", "fields": fields}

    W, H = bg.size
    overlay = Image.new("RGBA", (W, H), (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)

    # Compose lines
    lines = _compose_lines(payload)
    # Typography: clearer hierarchy
    title_font = _load_font(size=max(56, int(min(W, H) * 0.075)))
    body_font = _load_font(size=max(30, int(min(W, H) * 0.035)))
    if title_font is None or body_font is None:
        return {"ok": False, "path": out_path, "exists": False, "error": "Font load failed", "fields": fields}

    # Layout: centered stack with balanced spacing in safe central area
    gap = int(H * 0.02)
    heights = []
    widths = []
    bboxes = []
    for i, text in enumerate(lines):
        font = title_font if i == 0 else body_font
        bbox = draw.textbbox((0, 0), text, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        widths.append(w)
        heights.append(h)
        bboxes.append((w, h))
    total_h = sum(heights) + gap * (len(heights) - 1 if heights else 0)
    y = max(int((H - total_h) / 2), int(H * 0.35))
    # Compute union text area bounding box for background softening
    text_left = min([(W - bboxes[i][0]) // 2 for i in range(len(bboxes))]) if bboxes else W // 4
    text_right = max([(W + bboxes[i][0]) // 2 for i in range(len(bboxes))]) if bboxes else int(W * 0.75)
    text_top = y
    text_bottom = y + total_h
    # Soften/blur only behind text region to improve readability
    try:
        from PIL import ImageFilter
        bg_rgba = bg.copy()
        # Expand bbox padding
        pad_x = int(W * 0.04)
        pad_y = int(H * 0.02)
        bx1 = max(0, text_left - pad_x)
        by1 = max(0, text_top - pad_y)
        bx2 = min(W, text_right + pad_x)
        by2 = min(H, text_bottom + pad_y)
        region = bg_rgba.crop((bx1, by1, bx2, by2)).filter(ImageFilter.GaussianBlur(radius=max(6, int(min(W, H) * 0.01))))
        # Light translucent overlay to lift text region
        shade = Image.new("RGBA", (bx2 - bx1, by2 - by1), (255, 255, 255, 80))
        region = Image.alpha_composite(region, shade)
        bg_rgba.paste(region, (bx1, by1))
        bg = bg_rgba
    except Exception:
        # If blur not available, draw a subtle translucent panel instead
        panel = Image.new("RGBA", (text_right - text_left + int(W * 0.08), total_h + int(H * 0.04)), (255, 255, 255, 70))
        px = max(0, text_left - int(W * 0.04))
        py = max(0, text_top - int(H * 0.02))
        bg = Image.alpha_composite(bg, Image.new("RGBA", bg.size, (0, 0, 0, 0)))
        bg.paste(panel, (px, py), panel)
    # Draw lines centered with strong hierarchy & contrast
    for i, text in enumerate(lines):
        font = title_font if i == 0 else body_font
        w, h = bboxes[i]
        x = (W - w) // 2
        # Use darker text for better contrast over softened background
        fill = (20, 20, 20, 255)
        if i == 0:
            # Slightly darker for the title
            fill = (10, 10, 10, 255)
        draw.text((x, y), text, fill=fill, font=font)
        y += h + gap

    composed = Image.alpha_composite(bg, overlay).convert("RGB")
    composed.save(out_path)

    exists = os.path.exists(out_path)
    size = os.path.getsize(out_path) if exists else 0
    return {"ok": exists, "path": out_path, "exists": exists, "error": None, "size": size, "fields": fields}
