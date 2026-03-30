from __future__ import annotations

import os
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime

# Initialize structured debug logging for invite rendering
logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
except Exception:  # Pillow not guaranteed in requirements, but used elsewhere in repo
    Image = None  # type: ignore
    ImageDraw = None  # type: ignore
    ImageFont = None  # type: ignore
    ImageFilter = None  # type: ignore


def _candidate_fonts_for_role(role: str) -> List[str]:
    """Return a prioritized list of candidate font files for a given role.

    This enables a minimal custom font mechanism for invite rendering without
    changing app flow. If custom fonts are present under assets/fonts, prefer
    them; otherwise, fall back to common system fonts.
    """
    role = (role or "").lower()
    fonts_dir = os.path.join("assets", "fonts")
    candidates: List[str] = []

    # Prefer decorative/script or elegant serif for names
    if role in ("names", "phrase"):
        candidates += [
            os.path.join(fonts_dir, "GreatVibes-Regular.ttf"),
            os.path.join(fonts_dir, "CormorantGaramond-SemiBold.ttf"),
            os.path.join(fonts_dir, "PlayfairDisplay-SemiBold.ttf"),
            "GreatVibes-Regular.ttf",
            "CormorantGaramond-SemiBold.ttf",
            "PlayfairDisplay-SemiBold.ttf",
            "DejaVuSerif.ttf",
            "Times New Roman.ttf",
            "times.ttf",
        ]
    # Subtle italic for header/eyebrow or RSVP if available
    if role in ("header", "eyebrow", "rsvp"):
        candidates += [
            os.path.join(fonts_dir, "CormorantGaramond-Italic.ttf"),
            os.path.join(fonts_dir, "PlayfairDisplay-Italic.ttf"),
            os.path.join(fonts_dir, "DejaVuSerif-Italic.ttf"),
            "CormorantGaramond-Italic.ttf",
            "PlayfairDisplay-Italic.ttf",
            "DejaVuSerif-Italic.ttf",
            "Georgia Italic.ttf",
            "timesi.ttf",
            "DejaVuSans-Oblique.ttf",
        ]
    # Clean readable font for body/details
    if role in ("body", "date", "venue", "place", "details"):
        candidates += [
            os.path.join(fonts_dir, "LibreBaskerville-Regular.ttf"),
            os.path.join(fonts_dir, "EBGaramond-Regular.ttf"),
            os.path.join(fonts_dir, "Inter-Regular.ttf"),
            os.path.join(fonts_dir, "DejaVuSans.ttf"),
            "LibreBaskerville-Regular.ttf",
            "EBGaramond-Regular.ttf",
            "Inter-Regular.ttf",
            "DejaVuSans.ttf",
            "Arial.ttf",
            "arial.ttf",
        ]

    # As a final safety, add generic fallbacks
    candidates += ["DejaVuSans.ttf", "arial.ttf"]
    # Deduplicate while keeping order
    seen = set()
    ordered: List[str] = []
    for c in candidates:
        if c and c not in seen:
            seen.add(c)
            ordered.append(c)
    return ordered


def _load_font(size: int = 56, role: str = "body") -> Optional["ImageFont.ImageFont"]:  # type: ignore
    try:
        if ImageFont is None:
            return None
        for cand in _candidate_fonts_for_role(role):
            try:
                return ImageFont.truetype(cand, size=size)
            except Exception:
                continue
        return ImageFont.load_default()
    except Exception:
        return None


def _ordinal(n: int) -> str:
    try:
        n_int = int(n)
    except Exception:
        return str(n)
    if 10 <= n_int % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n_int % 10, "th")
    return f"{n_int}{suffix}"


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
            # Invite-friendly: 'Saturday, 10th December 2026'
            dow = dt.strftime("%A")
            day = _ordinal(int(dt.strftime("%d")))
            month_year = dt.strftime("%B %Y")
            return f"{dow}, {day} {month_year}"
        except Exception:
            continue
    return s


def compose_invite_sections(payload: Dict) -> Dict[str, str]:
    """Compose an elegant invitation copy block from grounded fields only.

    Returns a dict of explicit sections that the renderer can place with
    hierarchy. No raw keys or Python lists are emitted.
    """
    bride = str(payload.get("bride_name", "")).strip()
    groom = str(payload.get("groom_name", "")).strip()
    couple = " & ".join([x for x in [bride, groom] if x]) or "Our Couple"

    dates_raw = [str(d).strip() for d in (payload.get("wedding_dates") or []) if str(d).strip()]
    pretty_dates = [_format_date_pretty(d) for d in dates_raw]
    if len(pretty_dates) == 1:
        date_line = pretty_dates[0]
    else:
        # Join multiple dates with subtle spacing (no Python list rendering)
        date_line = "   ".join([d for d in pretty_dates if d])

    place = str(payload.get("wedding_place", "")).strip()
    destination = str(payload.get("destination") or place or "").strip()
    include_venue = bool(payload.get("include_venue_details"))
    hotel = str(payload.get("selected_hotel") or "").strip()
    include_rsvp = bool(payload.get("include_rsvp"))

    style = str(payload.get("invite_wording_style") or "").strip().lower()
    with_families = payload.get("invite_together_with_families")
    include_blessing = payload.get("invite_include_short_blessing")
    ceremony_summary_lines = payload.get("ceremony_summary_lines") or []
    rsvp_style = str(payload.get("invite_rsvp_sentence_style") or "").strip().lower()

    # Invitation phrase: respect explicit preference if provided
    explicit_phrase = str(payload.get("invite_invitation_phrase") or "").strip()
    if explicit_phrase:
        base_phrase = explicit_phrase
    elif style in ("formal", "royal"):
        base_phrase = "request the honor of your presence"
    elif style in ("warm", "modern elegant", "modern"):
        base_phrase = "cordially invite you"
    else:
        base_phrase = "invite you to celebrate with them"

    if destination and destination != place:
        invitation_line = f"{base_phrase} to join them as they celebrate their wedding in {destination}"
    else:
        # Keep phrasing smooth, avoid redundancy
        invitation_line = f"{base_phrase} to join them as they celebrate their wedding"

    eyebrow = "Together with their families" if with_families else "With joy in their hearts"

    # Ceremony summary compact block can override date_line
    if ceremony_summary_lines and isinstance(ceremony_summary_lines, list):
        # Merge into a single tasteful line separated by middots if compact
        cleaned = [str(x).strip() for x in ceremony_summary_lines if str(x).strip()]
        if cleaned:
            date_line = "  •  ".join(cleaned)

    venue_line = hotel if (include_venue and hotel) else ""
    place_line = place
    rsvp_line = ""
    if include_rsvp:
        rsvp_line = (
            "Kindly RSVP at your earliest convenience" if rsvp_style == "short" else "RSVP"
        )

    sections = {
        "eyebrow": eyebrow,
        "names": couple,
        "invitation_line": invitation_line,
        "date_line": date_line,
        "venue_line": venue_line,
        "place_line": place_line,
        "rsvp_line": rsvp_line,
    }

    # Optional soft blessing line as part of body (kept separate so renderer can decide)
    if include_blessing is True:
        sections["blessing_line"] = "and begin their happily ever after"

    return sections


def _compose_lines(payload: Dict) -> List[str]:
    """Back-compat: build ordered lines from the explicit sections."""
    sec = compose_invite_sections(payload)
    ordered = [
        sec.get("eyebrow", ""),
        sec.get("names", ""),
        sec.get("invitation_line", ""),
    ]
    if sec.get("blessing_line"):
        ordered.append(sec["blessing_line"])  # type: ignore[index]
    for k in ("date_line", "venue_line", "place_line", "rsvp_line"):
        v = sec.get(k)
        if v:
            ordered.append(v)
    return [ln for ln in ordered if ln]


def _compose_labeled_lines_from_sections(sec: Dict[str, str]) -> List[Tuple[str, str]]:
    """Return (text, role) pairs maintaining a semantic role per line.

    Roles used: header|eyebrow, names, phrase, blessing, date, venue, place, rsvp
    """
    labeled: List[Tuple[str, str]] = []
    if sec.get("eyebrow"):
        labeled.append((sec["eyebrow"], "header"))
    if sec.get("names"):
        labeled.append((sec["names"], "names"))
    if sec.get("invitation_line"):
        labeled.append((sec["invitation_line"], "phrase"))
    if sec.get("blessing_line"):
        labeled.append((sec["blessing_line"], "blessing"))
    if sec.get("date_line"):
        labeled.append((sec["date_line"], "date"))
    if sec.get("venue_line"):
        labeled.append((sec["venue_line"], "venue"))
    if sec.get("place_line"):
        labeled.append((sec["place_line"], "place"))
    if sec.get("rsvp_line"):
        labeled.append((sec["rsvp_line"], "rsvp"))
    return labeled


def _wrap_labeled_lines(
    draw: "ImageDraw.ImageDraw",
    lines: List[Tuple[str, str]],
    max_text_width: int,
    fonts: Dict[str, "ImageFont.ImageFont"],
) -> Tuple[List[Tuple[str, str]], List[str]]:
    """Wrap each (text, role) to width, preserving roles across wrapped fragments.

    Returns (wrapped_pairs, wrap_logs)
    """
    import textwrap
    wrapped: List[Tuple[str, str]] = []
    wrap_logs: List[str] = []
    for text, role in lines:
        font = fonts.get(role) or fonts.get("body")
        if font is None:
            wrapped.append((text, role))
            continue
        # Prefer natural breaks for date/venue/place
        try:
            w_full = draw.textlength(text, font=font)
        except Exception:
            w_full = max_text_width + 1
        if role == "date" and w_full > max_text_width:
            # Try split at comma first
            if "," in text:
                parts = [p.strip() for p in text.split(",", 1)]
                if len(parts) == 2 and all(parts):
                    wrapped.append((parts[0], role))
                    wrapped.append((parts[1], role))
                    wrap_logs.append("Wrapped date line into 2 lines (comma split)")
                    continue
        # Generic wrapping using avg char width as fallback
        try:
            avg_w = draw.textlength("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz", font=font) / 52.0
            max_chars = max(10, int(max_text_width / max(1.0, avg_w)))
        except Exception:
            max_chars = 40
        chunks = textwrap.wrap(text, width=max_chars) if len(text) > max_chars else [text]
        if len(chunks) > 1:
            wrap_logs.append(f"Wrapped {role} into {len(chunks)} lines")
        for c in chunks:
            wrapped.append((c, role))
    return wrapped, wrap_logs


def _sample_region_luminance(img: "Image.Image", box: Tuple[int, int, int, int]) -> float:  # type: ignore
    try:
        region = img.crop(box).convert("L")
        # Downsample to reduce cost
        small = region.resize((32, 32))
        # Average luminance 0..255
        px = small.getdata()
        return sum(px) / float(len(px) or 1)
    except Exception:
        return 180.0  # assume bright


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
    logger.debug("Starting invite rendering")
    logger.debug(f"Invite payload: {payload}")
    logger.debug("Ensuring single render execution")
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

    # Compose sections and flattened lines (explicit render payload)
    sections = compose_invite_sections(payload)
    logger.debug("Validating text variables before rendering")
    logger.debug(f"Header: {sections.get('eyebrow')}")
    logger.debug(f"Names: {sections.get('names')}")
    _body_dbg: List[str] = []
    if sections.get('invitation_line'):
        _body_dbg.append(sections.get('invitation_line'))
    if sections.get('blessing_line'):
        _body_dbg.append(sections.get('blessing_line'))
    logger.debug(f"Body: {_body_dbg}")
    logger.debug(f"Date: {sections.get('date_line')}")
    logger.debug(f"Venue: {sections.get('venue_line')}")
    # Build final conceptual lines exactly once (no mutation later)
    final_lines: List[str] = []
    for ln in [
        sections.get("eyebrow", ""),
        sections.get("names", ""),
        sections.get("invitation_line", ""),
        sections.get("blessing_line", ""),
        sections.get("date_line", ""),
        sections.get("venue_line", ""),
        sections.get("place_line", ""),
        sections.get("rsvp_line", ""),
    ]:
        if ln:
            final_lines.append(str(ln))

    # Strict debug validation before rendering
    try:
        print("===== DEBUG: FINAL LINES =====")
        for i, line in enumerate(final_lines):
            print(f"{i}: {line}")
        print("Total lines:", len(final_lines))
    except Exception:
        pass

    # Build labeled lines so we can style: header, names, phrase, date, venue, place, rsvp
    labeled = _compose_labeled_lines_from_sections(sections)

    # Typography: refined hierarchy with role-based font pairing
    base = int(min(W, H))
    h_size = max(26, int(base * 0.038))
    n_size = max(64, int(base * 0.11))
    b_size = max(28, int(base * 0.04))
    logger.debug("Applying typography hierarchy")
    # Strengthen hierarchy: smaller header, larger names, clearer steps down
    fonts = {
        "header": _load_font(size=max(22, int(base * 0.032)), role="header"),
        "names": _load_font(size=max(72, int(base * 0.125)), role="names"),
        "phrase": _load_font(size=max(36, int(base * 0.048)), role="phrase"),
        "date": _load_font(size=max(30, int(base * 0.044)), role="body"),
        "venue": _load_font(size=max(26, int(base * 0.038)), role="body"),
        "place": _load_font(size=max(26, int(base * 0.038)), role="body"),
        "rsvp": _load_font(size=max(24, int(base * 0.035)), role="rsvp"),
        "blessing": _load_font(size=max(28, int(base * 0.04)), role="body"),
        "body": _load_font(size=max(28, int(base * 0.04)), role="body"),
    }
    if any(v is None for v in [fonts["header"], fonts["names"], fonts["body"]]):
        return {"ok": False, "path": out_path, "exists": False, "error": "Font load failed", "fields": fields}
    header_font = fonts.get('header')
    name_font = fonts.get('names')
    body_font = fonts.get('body')
    try:
        def _fname(f):
            try:
                return getattr(f, 'path', None) or (f.getname() if hasattr(f, 'getname') else str(f))
            except Exception:
                return str(f)
        logger.debug(f"Header font: {_fname(header_font)}")
        logger.debug(f"Names font: {_fname(name_font)}")
        logger.debug(f"Body font: {_fname(body_font)}")
    except Exception:
        logger.debug("Font debug names unavailable")

    max_text_width = int(W * 0.72)
    wrapped_pairs, wrap_logs = _wrap_labeled_lines(draw, labeled, max_text_width, fonts)
    for wl in wrap_logs:
        logger.debug(wl)

    # Measure bboxes after wrapping
    roles: List[str] = []
    bboxes: List[Tuple[int, int]] = []
    heights: List[int] = []
    for text, role in wrapped_pairs:
        font = fonts.get(role) or fonts.get("body")
        bbox = draw.textbbox((0, 0), text, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        roles.append(role)
        bboxes.append((w, h))
        heights.append(h)

    # Spacing tuned per role (more air around names and before RSVP)
    def _gap_for(role: str) -> int:
        # Increased contrast in vertical rhythm
        if role in ("header", "eyebrow"):
            return int(H * 0.02)
        if role == "names":
            return int(H * 0.038)
        if role in ("phrase", "date"):
            return int(H * 0.024)
        if role in ("venue", "place"):
            return int(H * 0.018)
        if role == "rsvp":
            return int(H * 0.026)
        return int(H * 0.016)

    total_h = 0
    for i in range(len(heights)):
        total_h += heights[i]
        if i < len(heights) - 1:
            total_h += _gap_for(roles[i])

    # Define an elegant vertical band and distribute lines across it
    band_top = int(H * 0.18)
    band_bottom = int(H * 0.86)
    band_height = max(1, band_bottom - band_top)
    # Base position if content exceeds band
    y = band_top
    # Compute additional spacing to use more vertical space when available
    gaps = [
        _gap_for(roles[i]) for i in range(len(heights) - 1)
    ]
    base_stack_h = sum(heights) + sum(gaps)
    extra_per_gap = 0
    if len(gaps) > 0 and base_stack_h < band_height:
        extra = band_height - base_stack_h
        extra_per_gap = int(extra / max(1, len(gaps)))
    # Compute union text area bounding box for background softening
    text_left = min([(W - bboxes[i][0]) // 2 for i in range(len(bboxes))]) if bboxes else W // 4
    text_right = max([(W + bboxes[i][0]) // 2 for i in range(len(bboxes))]) if bboxes else int(W * 0.75)
    text_top = y
    text_bottom = y + total_h
    positions = {"left": text_left, "right": text_right, "top": text_top, "bottom": text_bottom}
    line_spacing = {
        "header": int(H * 0.02),
        "names": int(H * 0.038),
        "phrase": int(H * 0.024),
        "date": int(H * 0.024),
        "venue": int(H * 0.018),
        "place": int(H * 0.018),
        "rsvp": int(H * 0.026),
        "body": int(H * 0.016),
    }
    logger.debug(f"Section positions: {positions}")
    logger.debug(f"Line spacing: {line_spacing}")
    logger.debug(f"Total text block height: {total_h}")

    # Subtle readability aids that preserve the scenic image (no boxes/frames)
    logger.debug("Applying text readability enhancements")
    try:
        # 1) Softer vertical edge gradients (reduced alpha)
        shade = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        sdraw = ImageDraw.Draw(shade)
        top_h = int(H * 0.16)
        bot_h = int(H * 0.16)
        shade_applied = False
        if top_h > 0:
            for i in range(top_h):
                a = int(40 * (1.0 - (i / max(1, top_h))))
                sdraw.line([(0, i), (W, i)], fill=(0, 0, 0, a))
                shade_applied = True
        if bot_h > 0:
            for j in range(bot_h):
                a = int(40 * (1.0 - (j / max(1, bot_h))))
                yb = H - 1 - j
                sdraw.line([(0, yb), (W, yb)], fill=(0, 0, 0, a))
                shade_applied = True
        if shade_applied:
            bg = Image.alpha_composite(bg, shade)

        # 2) Conditional, very gentle blur only if mid-tone background makes text harder to read
        blur_applied = False
        if ImageFilter is not None and text_right > text_left and text_bottom > text_top:
            region_lumi = _sample_region_luminance(bg, (text_left, text_top, text_right, text_bottom))
            if 110 < region_lumi < 160:
                logger.debug("Applying gentle background blur under text region")
                blurred = bg.filter(ImageFilter.GaussianBlur(radius=max(2, int(min(W, H) * 0.005))))
                mask = Image.new("L", (W, H), 0)
                mdraw = ImageDraw.Draw(mask)
                pad_x = int(W * 0.028)
                pad_y = int(H * 0.012)
                mdraw.rounded_rectangle(
                    (max(0, text_left - pad_x), max(0, text_top - pad_y), min(W, text_right + pad_x), min(H, text_bottom + pad_y)),
                    radius=max(6, int(min(W, H) * 0.012)), fill=120
                )
                mask = mask.filter(ImageFilter.GaussianBlur(radius=max(4, int(min(W, H) * 0.012))))
                bg = Image.composite(blurred, bg, mask)
                blur_applied = True
    except Exception:
        pass
    logger.debug(f"Gradient applied: {bool('shade_applied' in locals() and shade_applied)}")
    logger.debug(f"Background blur applied: {bool('blur_applied' in locals() and blur_applied)}")

    # Adaptive text color based on background luminance (sample underlying area)
    lumi = _sample_region_luminance(bg, (text_left, text_top, text_right, text_bottom))
    primary_fill = (24, 24, 24, 255) if lumi >= 155 else (242, 242, 242, 255)
    header_fill = (16, 16, 16, 255) if lumi >= 155 else (248, 248, 248, 255)
    logger.debug(f"Region luminance: {int(lumi)}")
    logger.debug(f"Text color selected: primary={primary_fill}, header={header_fill}")

    # Draw lines centered with refined hierarchy; add a slim divider under names
    section_positions: List[Dict[str, int]] = []
    glow_applied = False
    for i, (text, role) in enumerate(wrapped_pairs):
        font = fonts.get(role) or fonts.get("body")
        fill = header_fill if role in ("header", "eyebrow") else primary_fill
        w, h = bboxes[i]
        x = (W - w) // 2
        logger.debug(f"Rendering section: {role}")

        # Subtle shadow for readability on busy backgrounds
        shadow = (0, 0, 0, 70) if fill[0] > 128 else (255, 255, 255, 70)
        try:
            draw.text((x + 1, y + 1), text, fill=shadow, font=font)
        except Exception:
            pass
        # Very light glow for mid-tone regions
        need_glow = 100 < lumi < 170
        if need_glow and ImageFilter is not None:
            try:
                txt_mask = Image.new("L", (w + 8, h + 8), 0)
                mdraw = ImageDraw.Draw(txt_mask)
                mdraw.text((4, 4), text, fill=180, font=font)
                blurred = txt_mask.filter(ImageFilter.GaussianBlur(radius=max(1, int(min(W, H) * 0.004))))
                glow = Image.new("RGBA", blurred.size, (255, 255, 255, 0)) if fill[0] < 128 else Image.new("RGBA", blurred.size, (0, 0, 0, 0))
                glow.putalpha(blurred)
                overlay.alpha_composite(glow, dest=(x - 4, y - 4))
                glow_applied = True
            except Exception:
                pass
        draw.text((x, y), text, fill=fill, font=font)

        # If names, consider a very thin divider line underneath for elegance
        if role == "names":
            try:
                line_w = max(int(w * 0.35), int(W * 0.12))
                line_x0 = (W - line_w) // 2
                line_y = y + h + int(H * 0.008)
                line_color = (fill[0], fill[1], fill[2], 90)
                draw.line([(line_x0, line_y), (line_x0 + line_w, line_y)], fill=line_color, width=max(1, int(min(W, H) * 0.002)))
                # Increase spacing after the divider
                y = line_y + int(H * 0.012)
            except Exception:
                y += h + _gap_for(role)
        else:
            y += h + _gap_for(role)

        # Increase spacing to gently use vertical band
        if i < len(wrapped_pairs) - 1:
            y += extra_per_gap
        section_positions.append({"x": x, "y": y, "w": w, "h": h})

    logger.debug("Shadow applied: True")
    logger.debug(f"Glow applied: {glow_applied}")
    logger.debug(f"Section positions: {section_positions}")

    # Optional decorative caricature/illustration (tasteful, small, not dominant)
    try:
        logger.debug("Checking if caricature generation is enabled")
        include_cari = bool(payload.get("invite_include_caricature"))
        cari_path = (
            str(payload.get("invite_caricature_path") or "").strip()
            or os.path.join("assets", "invites", "caricature.png")
        )
        if include_cari and os.path.exists(cari_path):
            deco = Image.open(cari_path).convert("RGBA")
            # Scale to ~14% width, preserve aspect, and place near lower-right with margin
            target_w = int(W * 0.14)
            scale = max(1, int(target_w / max(1, deco.size[0])))
            new_w = target_w
            new_h = int(deco.size[1] * (new_w / float(deco.size[0])))
            deco = deco.resize((new_w, new_h))
            margin_x = int(W * 0.04)
            margin_y = int(H * 0.04)
            pos = (W - new_w - margin_x, H - new_h - margin_y)
            overlay.alpha_composite(deco, dest=pos)
    except Exception:
        pass

    try:
        composed = Image.alpha_composite(bg, overlay).convert("RGB")
        composed.save(out_path)

        exists = os.path.exists(out_path)
        size = os.path.getsize(out_path) if exists else 0
        logger.info("Invite rendering completed")
        return {
            "ok": exists,
            "path": out_path,
            "exists": exists,
            "error": None,
            "size": size,
            "fields": fields,
            # Expose explicit render payload for visibility/validation
            "render": {"sections": sections, "lines": final_lines},
        }
    except Exception as e:
        logger.error(f"Invite rendering failed: {str(e)}", exc_info=True)
        raise


def render_invite_sections(background_path: str, sections_payload: Dict, out_path: str) -> Dict:
    """Render ONLY composed invitation sections (no raw field labels).

    sections_payload must contain keys:
      - header_line, names_line, body_lines (list), date_line, venue_line, place_line, rsvp_line

    If raw field-like keys are detected (e.g., bride_name, wedding_dates), this returns an error
    directing the caller to compose polished copy first.
    """
    # Hard validation: reject raw structured keys reaching the renderer
    raw_keys = {"bride_name", "groom_name", "wedding_dates", "wedding_place", "selected_hotel", "include_rsvp"}
    if any(k in sections_payload for k in raw_keys):
        return {
            "ok": False,
            "path": out_path,
            "exists": False,
            "error": "Raw invite fields provided to renderer; expected composed copy sections.",
            "fields": {k: sections_payload.get(k) for k in sorted(list(raw_keys))},
        }

    # Extract composed text
    header_line = str(sections_payload.get("header_line", "")).strip()
    names_line = str(sections_payload.get("names_line", "")).strip()
    body_lines = [str(x).strip() for x in (sections_payload.get("body_lines") or []) if str(x).strip()]
    date_line = str(sections_payload.get("date_line", "")).strip()
    venue_line = str(sections_payload.get("venue_line", "")).strip()
    place_line = str(sections_payload.get("place_line", "")).strip()
    rsvp_line = str(sections_payload.get("rsvp_line", "")).strip()
    logger.debug("Starting invite rendering")
    logger.debug("Ensuring single render execution")
    logger.debug(f"Invite payload: {sections_payload}")
    logger.debug("Validating text variables before rendering")
    logger.debug(f"Header: {header_line}")
    logger.debug(f"Names: {names_line}")
    logger.debug(f"Body: {body_lines}")
    logger.debug(f"Date: {date_line}")
    logger.debug(f"Venue: {venue_line}")

    composed_payload = {
        "header_line": header_line,
        "names_line": names_line,
        "body_lines": body_lines,
        "date_line": date_line,
        "venue_line": venue_line,
        "place_line": place_line,
        "rsvp_line": rsvp_line,
    }

    # Build final lines exactly once
    lines: List[str] = [
        header_line,
        names_line,
        *body_lines,
        date_line,
        venue_line,
        place_line,
        rsvp_line,
    ]
    # Filter empties and ensure flat list
    lines = [str(x) for x in lines if isinstance(x, (str, int, float)) and str(x).strip()]

    # Strict debug validation before rendering
    try:
        print("===== DEBUG: FINAL LINES =====")
        for i, line in enumerate(lines):
            print(f"{i}: {line}")
        print("Total lines:", len(lines))
    except Exception:
        pass

    # Convert sections into labeled lines for typography control
    sec: Dict[str, str] = {
        "eyebrow": header_line,
        "names": names_line,
        # invitation_line comes from body_lines[0] if present; the rest are general body
        "invitation_line": (body_lines[0] if body_lines else ""),
        "date_line": date_line,
        "venue_line": venue_line,
        "place_line": place_line,
        "rsvp_line": rsvp_line,
    }
    labeled = _compose_labeled_lines_from_sections(sec)
    # Insert remaining body lines (if any) with role 'body' after the phrase
    if body_lines and len(body_lines) > 1:
        insert_at = 0
        for idx, (_t, r) in enumerate(labeled):
            if r == "phrase":
                insert_at = idx + 1
                break
        extras = [(t, "body") for t in body_lines[1:]]
        labeled[insert_at:insert_at] = extras

    # Use the same drawing implementation as render_invite_text with minimal duplication
    if Image is None:
        return {"ok": False, "path": out_path, "exists": False, "error": "Pillow not available", "fields": {}}

    try:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
    except Exception:
        pass

    try:
        bg = Image.open(background_path).convert("RGBA")
    except Exception as e:
        return {"ok": False, "path": out_path, "exists": False, "error": f"background open failed: {e}", "fields": {}}

    W, H = bg.size
    overlay = Image.new("RGBA", (W, H), (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)

    # Typography hierarchy (names prominent, role-aware)
    base = int(min(W, H))
    h_size = max(26, int(base * 0.038))
    n_size = max(64, int(base * 0.11))
    b_size = max(28, int(base * 0.04))
    logger.debug("Applying typography hierarchy")
    fonts = {
        "header": _load_font(size=max(22, int(base * 0.032)), role="header"),
        "names": _load_font(size=max(72, int(base * 0.125)), role="names"),
        "phrase": _load_font(size=max(36, int(base * 0.048)), role="phrase"),
        "date": _load_font(size=max(30, int(base * 0.044)), role="body"),
        "venue": _load_font(size=max(26, int(base * 0.038)), role="body"),
        "place": _load_font(size=max(26, int(base * 0.038)), role="body"),
        "rsvp": _load_font(size=max(24, int(base * 0.035)), role="rsvp"),
        "blessing": _load_font(size=max(28, int(base * 0.04)), role="body"),
        "body": _load_font(size=max(28, int(base * 0.04)), role="body"),
    }
    if any(v is None for v in [fonts["header"], fonts["names"], fonts["body"]]):
        return {"ok": False, "path": out_path, "exists": False, "error": "Font load failed", "fields": {}}
    header_font = fonts.get('header')
    name_font = fonts.get('names')
    body_font = fonts.get('body')
    try:
        def _fname(f):
            try:
                return getattr(f, 'path', None) or (f.getname() if hasattr(f, 'getname') else str(f))
            except Exception:
                return str(f)
        logger.debug(f"Header font: {_fname(header_font)}")
        logger.debug(f"Names font: {_fname(name_font)}")
        logger.debug(f"Body font: {_fname(body_font)}")
    except Exception:
        logger.debug("Font debug names unavailable")

    max_text_width = int(W * 0.72)
    wrapped_pairs, wrap_logs = _wrap_labeled_lines(draw, labeled, max_text_width, fonts)
    for wl in wrap_logs:
        logger.debug(wl)

    roles: List[str] = []
    bboxes: List[Tuple[int, int]] = []
    heights: List[int] = []
    for text, role in wrapped_pairs:
        font = fonts.get(role) or fonts.get("body")
        bbox = draw.textbbox((0, 0), text, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        bboxes.append((w, h))
        heights.append(h)
        roles.append(role)

    def _gap_for(role: str) -> int:
        if role in ("header", "eyebrow"):
            return int(H * 0.02)
        if role == "names":
            return int(H * 0.038)
        if role in ("phrase", "date"):
            return int(H * 0.024)
        if role in ("venue", "place"):
            return int(H * 0.018)
        if role == "rsvp":
            return int(H * 0.026)
        return int(H * 0.016)

    total_h = 0
    for i in range(len(heights)):
        total_h += heights[i]
        if i < len(heights) - 1:
            total_h += _gap_for(roles[i])

    # Distribute within a tall vertical band for better breathing space
    band_top = int(H * 0.18)
    band_bottom = int(H * 0.86)
    band_height = max(1, band_bottom - band_top)
    y = band_top
    gaps = [
        _gap_for(roles[i]) for i in range(len(heights) - 1)
    ]
    base_stack_h = sum(heights) + sum(gaps)
    extra_per_gap = 0
    if len(gaps) > 0 and base_stack_h < band_height:
        extra = band_height - base_stack_h
        extra_per_gap = int(extra / max(1, len(gaps)))
    text_left = min([(W - bboxes[i][0]) // 2 for i in range(len(bboxes))]) if bboxes else W // 4
    text_right = max([(W + bboxes[i][0]) // 2 for i in range(len(bboxes))]) if bboxes else int(W * 0.75)
    text_top = y
    text_bottom = y + total_h

    # Apply the same subtle readability aids (with gentler parameters)
    logger.debug("Applying text readability enhancements")
    try:
        shade = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        sdraw = ImageDraw.Draw(shade)
        top_h = int(H * 0.16)
        bot_h = int(H * 0.16)
        shade_applied = False
        if top_h > 0:
            for i in range(top_h):
                a = int(40 * (1.0 - (i / max(1, top_h))))
                sdraw.line([(0, i), (W, i)], fill=(0, 0, 0, a))
                shade_applied = True
        if bot_h > 0:
            for j in range(bot_h):
                a = int(40 * (1.0 - (j / max(1, bot_h))))
                yb = H - 1 - j
                sdraw.line([(0, yb), (W, yb)], fill=(0, 0, 0, a))
                shade_applied = True
        if shade_applied:
            bg = Image.alpha_composite(bg, shade)

        blur_applied = False
        if ImageFilter is not None and text_right > text_left and text_bottom > text_top:
            region_lumi = _sample_region_luminance(bg, (text_left, text_top, text_right, text_bottom))
            if 110 < region_lumi < 160:
                logger.debug("Applying gentle background blur under text region")
                blurred = bg.filter(ImageFilter.GaussianBlur(radius=max(2, int(min(W, H) * 0.005))))
                mask = Image.new("L", (W, H), 0)
                mdraw = ImageDraw.Draw(mask)
                pad_x = int(W * 0.028)
                pad_y = int(H * 0.012)
                mdraw.rounded_rectangle(
                    (max(0, text_left - pad_x), max(0, text_top - pad_y), min(W, text_right + pad_x), min(H, text_bottom + pad_y)),
                    radius=max(6, int(min(W, H) * 0.012)), fill=120
                )
                mask = mask.filter(ImageFilter.GaussianBlur(radius=max(4, int(min(W, H) * 0.012))))
                bg = Image.composite(blurred, bg, mask)
                blur_applied = True
    except Exception:
        pass
    logger.debug(f"Gradient applied: {bool('shade_applied' in locals() and shade_applied)}")
    logger.debug(f"Background blur applied: {bool('blur_applied' in locals() and blur_applied)}")

    lumi = _sample_region_luminance(bg, (text_left, text_top, text_right, text_bottom))
    primary_fill = (20, 20, 20, 255) if lumi >= 155 else (238, 238, 238, 255)
    header_fill = (12, 12, 12, 255) if lumi >= 155 else (246, 246, 246, 255)
    logger.debug(f"Region luminance: {int(lumi)}")
    logger.debug(f"Text color selected: primary={primary_fill}, header={header_fill}")

    for i, (text, role) in enumerate(wrapped_pairs):
        font = fonts.get(role) or fonts.get("body")
        fill = header_fill if role in ("header", "eyebrow") else primary_fill
        w, h = bboxes[i]
        x = (W - w) // 2
        # Subtle text shadow for readability
        shadow = (0, 0, 0, 70) if primary_fill[0] < 100 else (255, 255, 255, 70)
        if role == "names" and draw.textlength(text, font=font) > int(max_text_width * 0.9) and ("&" in text):
            # Split bride and groom onto separate centered lines for elegance
            parts = [p.strip() for p in text.split("&", 1)]
            gap_between = int(H * 0.012)
            total_h_names = 0
            for j, part in enumerate(parts):
                bw, bh = draw.textbbox((0, 0), part, font=font)[2:4]
                nx = (W - bw) // 2
                draw.text((nx, y + total_h_names + 1), part, fill=shadow, font=font)
                draw.text((nx, y + total_h_names), part, fill=fill, font=font)
                total_h_names += bh
                if j == 0:
                    total_h_names += gap_between
            # Optional thin divider under split names too
            try:
                line_w = max(int(W * 0.18), int(W * 0.12))
                line_x0 = (W - line_w) // 2
                line_y = y + total_h_names + int(H * 0.006)
                line_color = (fill[0], fill[1], fill[2], 90)
                draw.line([(line_x0, line_y), (line_x0 + line_w, line_y)], fill=line_color, width=max(1, int(min(W, H) * 0.002)))
                y = line_y + int(H * 0.012)
            except Exception:
                y += total_h_names + _gap_for("names")
            if i < len(wrapped_pairs) - 1:
                y += extra_per_gap
            continue
        # shadow then text for all other roles, with optional glow
        draw.text((x, y + 1), text, fill=shadow, font=font)
        need_glow = 100 < lumi < 170
        if need_glow and ImageFilter is not None:
            try:
                txt_mask = Image.new("L", (w + 8, h + 8), 0)
                mdraw = ImageDraw.Draw(txt_mask)
                mdraw.text((4, 4), text, fill=180, font=font)
                blurred = txt_mask.filter(ImageFilter.GaussianBlur(radius=max(1, int(min(W, H) * 0.004))))
                glow = Image.new("RGBA", blurred.size, (255, 255, 255, 0)) if fill[0] < 128 else Image.new("RGBA", blurred.size, (0, 0, 0, 0))
                glow.putalpha(blurred)
                overlay.alpha_composite(glow, dest=(x - 4, y - 4))
            except Exception:
                pass
        draw.text((x, y), text, fill=fill, font=font)
        y += h + _gap_for(role)
        if i < len(wrapped_pairs) - 1:
            y += extra_per_gap

    try:
        composed_img = Image.alpha_composite(bg, overlay).convert("RGB")
        composed_img.save(out_path)

        exists = os.path.exists(out_path)
        size = os.path.getsize(out_path) if exists else 0
        logger.info("Invite rendering completed")
        return {
            "ok": exists,
            "path": out_path,
            "exists": exists,
            "error": None,
            "size": size,
            "fields": {},
            "render": {"sections": composed_payload, "lines": lines},
        }
    except Exception as e:
        logger.error(f"Invite rendering failed: {str(e)}", exc_info=True)
        raise
