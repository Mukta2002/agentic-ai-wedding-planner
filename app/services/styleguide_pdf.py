import os
from typing import Any, Dict, List

from PIL import Image, ImageDraw, ImageFont


def _slugify(name: str) -> str:
    keep = [c.lower() if c.isalnum() else '-' for c in (name or '')]
    s = ''.join(keep)
    while '--' in s:
        s = s.replace('--', '-')
    return s.strip('-')


def _ensure_dir(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)


def _file_info(path: str) -> Dict[str, Any]:
    return {
        "path": path,
        "exists": os.path.exists(path),
        "size": os.path.getsize(path) if os.path.exists(path) else 0,
    }


def build_style_guide_pdf(
    state_or_out: Any,
    out_path_or_events: Any,
    *args,
    **kwargs,
) -> Dict[str, Any]:
    """Restore the richer style-guide layout and populate with CURRENT session data.

    Structure (restored template-style):
    - Cover page (couple, place, dates, hotel)
    - Overview page (ceremonies list)
    - Palette page (from design_spec if available)
    - Moodboard pages: one per included ceremony (embeds generated images)
    - Ceremony detail pages (compact, grounded fields)

    Notes:
    - Never keep stale pages; generate a fresh PDF each run.
    - All content is grounded in current state; no hardcoded names.
    """
    # Support legacy/new signatures; we only need the output path.
    out_path = state_or_out if isinstance(state_or_out, str) else out_path_or_events
    _ensure_dir(out_path)
    # Hard reset any previous PDF at target path to prevent leaking old pages
    try:
        if os.path.exists(out_path):
            os.remove(out_path)
    except Exception:
        pass

    # Read ceremony plan from state when provided (for filtering & summary/details pages)
    ceremonies: List[Any] = []
    couple: str = ""
    place: str = ""
    dates_txt: str = ""
    hotel_txt: str = ""
    design_spec = None
    profile = None
    router = kwargs.get("router")  # optional ModelRouter to generate images
    try:
        state = None if isinstance(state_or_out, str) else state_or_out
        if state is not None:
            prof = getattr(state, "profile", None)
            profile = prof
            raw_cers = list(getattr(prof, "ceremonies", []) or []) if prof is not None else []
            ceremonies = [c for c in raw_cers if getattr(c, "include_in_style_guide", True)]
            try:
                bride = (getattr(prof, "bride_name", "") or "").strip()
                groom = (getattr(prof, "groom_name", "") or "").strip()
                couple = (f"{bride} & {groom}").strip(" &")
            except Exception:
                couple = ""
            try:
                place = (getattr(prof, "wedding_place", None) or getattr(prof, "destination", "") or "").strip()
            except Exception:
                place = ""
            try:
                dates_list = list(getattr(prof, "wedding_dates", []) or [])
                dates_txt = ", ".join([d for d in dates_list if d])
            except Exception:
                dates_txt = ""
            try:
                hotel_txt = (getattr(prof, "selected_hotel", None) or "").strip()
            except Exception:
                hotel_txt = ""
            try:
                design_spec = getattr(state, "design_spec", None)
            except Exception:
                design_spec = None
    except Exception:
        ceremonies = []

    pages: List[Image.Image] = []
    W, H = 1240, 1754  # A4-ish at ~150dpi
    # Cover page (restored polished layout)
    try:
        cover = Image.new("RGB", (W, H), (244, 242, 238))
        draw = ImageDraw.Draw(cover)
        try:
            font_title = ImageFont.load_default()
            font_sub = ImageFont.load_default()
        except Exception:
            font_title = None
            font_sub = None
        # Soft frame
        draw.rectangle([(80, 120), (W - 80, H - 120)], outline=(200, 198, 194), width=3)

        y = 360
        title = couple or "Guest Style Guide"
        subtitle = place or ""
        sub2 = dates_txt or ""
        sub3 = f"Hotel: {hotel_txt}" if hotel_txt else ""
        # Centered text helpers
        def _draw_center(text: str, y_pos: int, font) -> int:
            if not text:
                return y_pos
            w_text, h_text = draw.textlength(text, font=font), 18
            x_pos = (W - int(w_text)) // 2
            draw.text((x_pos, y_pos), text, fill=(30, 30, 30), font=font)
            return y_pos + int(h_text) + 16

        y = _draw_center(title, y, font_title)
        y = _draw_center(subtitle, y + 10, font_sub)
        y = _draw_center(sub2, y, font_sub)
        y = _draw_center(sub3, y, font_sub)
        pages.append(cover)
    except Exception:
        pass
    # Overview/summary page listing ceremonies
    if ceremonies:
        summary = Image.new("RGB", (W, H), (255, 255, 255))
        draw = ImageDraw.Draw(summary)
        try:
            font_title = ImageFont.load_default()
            font_text = ImageFont.load_default()
        except Exception:
            font_title = None
            font_text = None
        y = 80
        head = "Guest Style Guide Overview"
        if couple and place:
            head = f"{couple} - {place}"
        draw.text((80, y), head, fill=(0, 0, 0), font=font_title)
        y += 30
        if dates_txt:
            draw.text((80, y), dates_txt, fill=(0, 0, 0), font=font_text)
            y += 24
        if hotel_txt:
            draw.text((80, y), f"Hotel: {hotel_txt}", fill=(0, 0, 0), font=font_text)
            y += 24
        y += 8
        for idx, c in enumerate(ceremonies, start=1):
            colors = ", ".join(getattr(c, "palette", []) or [])
            line1 = f"{idx}. {getattr(c, 'name', '')} | {getattr(c, 'event_date', '')} | {getattr(c, 'time_of_day', '')}"
            line2 = f"   Mood: {getattr(c, 'mood', '')} | Palette: {colors} | Dress: {getattr(c, 'dress_code', '')}"
            draw.text((80, y), line1, fill=(0, 0, 0), font=font_text)
            y += 22
            draw.text((80, y), line2, fill=(0, 0, 0), font=font_text)
            y += 28
            note = getattr(c, "guest_note", None)
            if note:
                draw.text((100, y), f"Note: {note}", fill=(0, 0, 0), font=font_text)
                y += 24
        pages.append(summary)

    # Palette page (from design_spec) for visual richness
    if design_spec is not None:
        try:
            palette_hex = list(getattr(design_spec, "palette_hex", []) or [])
            palette_names = list(getattr(design_spec, "palette_names", []) or [])
            if palette_hex or palette_names:
                pal = Image.new("RGB", (W, H), (250, 250, 248))
                d = ImageDraw.Draw(pal)
                try:
                    f_title = ImageFont.load_default()
                    f_text = ImageFont.load_default()
                except Exception:
                    f_title = None
                    f_text = None
                d.text((80, 80), "Color Palette", fill=(0, 0, 0), font=f_title)
                # draw swatches
                x, y = 80, 140
                sw = 160
                for i in range(max(len(palette_hex), len(palette_names))):
                    name = palette_names[i] if i < len(palette_names) else ""
                    col = palette_hex[i] if i < len(palette_hex) else None
                    # swatch box
                    box = (x, y, x + sw, y + 90)
                    if col and isinstance(col, str) and col.strip().startswith('#') and len(col.strip()) >= 4:
                        # try hex fill
                        try:
                            rgb = tuple(int(col.strip()[j:j+2], 16) for j in (1, 3, 5))
                        except Exception:
                            rgb = (230, 230, 230)
                    else:
                        rgb = (230, 230, 230)
                    d.rectangle(box, fill=rgb, outline=(200, 200, 200))
                    # label
                    d.text((x, y + 98), f"{name} {col or ''}".strip(), fill=(20, 20, 20), font=f_text)
                    x += sw + 40
                    if x + sw + 80 > W:
                        x = 80
                        y += 150
                pages.append(pal)
        except Exception:
            pass

        # Moodboard + details pages per ceremony
        for idx, c in enumerate(ceremonies, start=1):
            event_name = getattr(c, 'name', f'Event {idx}')
            slug = _slugify(event_name)
            gen_dir = os.path.join('assets', 'style_guides', 'generated')
            os.makedirs(gen_dir, exist_ok=True)
            mood_path = os.path.join(gen_dir, f"{idx:02d}_{slug}.png")

            # If router present, generate or refresh moodboard image for this event
            if router is not None and (not os.path.exists(mood_path) or os.path.getsize(mood_path) == 0):
                try:
                    # Build prompt grounded in current state/spec
                    from app.prompts.artifact_prompts import build_moodboard_prompt
                    prompt = build_moodboard_prompt(
                        profile=profile,
                        creative_plan=getattr(state, 'creative', None),
                        design_spec=getattr(state, 'design_spec', None),
                        logistics_plan=getattr(state, 'logistics', None),
                        event_name=event_name,
                    )
                    # Reuse invite image generator for generic image output
                    _saved, _meta = router.generate_invite_image(prompt, out_path=mood_path, state=state)
                except Exception:
                    pass

            # Moodboard page
            page = Image.new("RGB", (W, H), (252, 252, 250))
            d = ImageDraw.Draw(page)
            try:
                f_title = ImageFont.load_default()
                f_text = ImageFont.load_default()
            except Exception:
                f_title = None
                f_text = None
            d.text((80, 60), f"{event_name} — Moodboard", fill=(0, 0, 0), font=f_title)
            # Image placement
            if os.path.exists(mood_path):
                try:
                    im = Image.open(mood_path).convert('RGB')
                    # Fit into a centered frame
                    frame_w, frame_h = W - 160, int(H * 0.6)
                    im.thumbnail((frame_w, frame_h))
                    x = (W - im.width) // 2
                    y = 120
                    page.paste(im, (x, y))
                except Exception:
                    pass
            # Ceremony palette swatches row (if available)
            try:
                cpal = list(getattr(c, 'palette', []) or [])
                if cpal:
                    sx, sy = 90, int(H * 0.74)
                    sw, sh = 120, 48
                    for col in cpal:
                        rgb = (230, 230, 230)
                        if isinstance(col, str) and col.strip().startswith('#') and len(col.strip()) >= 4:
                            try:
                                cs = col.strip()
                                rgb = tuple(int(cs[j:j+2], 16) for j in (1, 3, 5))
                            except Exception:
                                pass
                        d.rectangle((sx, sy, sx + sw, sy + sh), fill=rgb, outline=(200, 200, 200))
                        try:
                            d.text((sx, sy + sh + 6), str(col), fill=(10, 10, 10), font=f_text)
                        except Exception:
                            pass
                        sx += sw + 24
                        if sx + sw + 80 > W:
                            sx = 90
                            sy += sh + 36
            except Exception:
                pass
            pages.append(page)

            # Details page
            dpage = Image.new("RGB", (W, H), (253, 253, 253))
            dd = ImageDraw.Draw(dpage)
            try:
                ft = ImageFont.load_default()
                fx = ImageFont.load_default()
            except Exception:
                ft = None
                fx = None
            y = 100
            dd.text((80, y), f"{event_name}", fill=(0, 0, 0), font=ft)
            y += 36
            fields = [
                ("Date", getattr(c, "event_date", "")),
                ("Time", getattr(c, "time_of_day", "")),
                ("Mood/Theme", getattr(c, "mood", "")),
                ("Palette", ", ".join(getattr(c, "palette", []) or [])),
                ("Dress Code", getattr(c, "dress_code", "")),
            ]
            for k, v in fields:
                dd.text((80, y), f"{k}: {v}", fill=(10, 10, 10), font=fx)
                y += 24
            note = getattr(c, "guest_note", None)
            if note:
                y += 8
                dd.text((80, y), f"Guest Notes: {note}", fill=(10, 10, 10), font=fx)
            # Suggested attire guidance
            try:
                y += 24
                dd.text((80, y), "Suggested Attire", fill=(0, 0, 0), font=ft)
                y += 30
                dress = getattr(c, 'dress_code', '') or ''
                mood = getattr(c, 'mood', '') or ''
                pal_txt = ", ".join(getattr(c, 'palette', []) or [])
                men = f"Men: {dress} in palette ({pal_txt})" if dress else f"Men: palette-coordinated classic tailoring ({pal_txt})"
                women = f"Women: {dress} with elegant accessories" if dress else "Women: palette-coordinated sarees/lehengas or gowns, refined accessories"
                guests = f"Guests: keep looks {mood or 'elegant'} and cohesive; avoid clashing neons; tasteful jewelry"
                for tip in (men, women, guests):
                    dd.text((100, y), f"• {tip}", fill=(20, 20, 20), font=fx)
                    y += 22
            except Exception:
                pass
            pages.append(dpage)

    if not pages:
        return {"path": out_path, "exists": False, "error": "no images found", "page_count": 0}

    try:
        first, rest = pages[0], pages[1:]
        first.save(out_path, save_all=True, append_images=rest)
    except Exception as e:
        return {"path": out_path, "exists": False, "error": str(e), "page_count": len(pages)}

    info = _file_info(out_path)
    info["page_count"] = len(pages)
    return info
