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
    """Build a visual multi-page style guide PDF.

    Pages:
    - Cover
    - Overview
    - Palette
    - One page per ceremony (title/date/mood, swatches, men/women attire, collage)
    - Closing note
    """
    out_path = state_or_out if isinstance(state_or_out, str) else out_path_or_events
    _ensure_dir(out_path)
    try:
        if os.path.exists(out_path):
            os.remove(out_path)
    except Exception:
        pass

    # Pull grounded state
    ceremonies: List[Any] = []
    couple: str = ""
    place: str = ""
    dates_txt: str = ""
    hotel_txt: str = ""
    design_spec = None
    profile = None
    router = kwargs.get("router")
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
    built_prompts: List[Dict[str, Any]] = []
    dbg = {"ceremonies": [], "images": {}, "pages": 0}
    W, H = 1240, 1754

    # Cover
    try:
        cover = Image.new("RGB", (W, H), (244, 242, 238))
        draw = ImageDraw.Draw(cover)
        font_title = ImageFont.load_default()
        font_sub = ImageFont.load_default()
        draw.rectangle([(80, 120), (W - 80, H - 120)], outline=(200, 198, 194), width=3)

        y = 360
        title = couple or "Guest Style Guide"
        subtitle = place or ""
        sub2 = dates_txt or ""
        sub3 = f"Hotel: {hotel_txt}" if hotel_txt else ""

        def _draw_center(text: str, y_pos: int, font) -> int:
            if not text:
                return y_pos
            w_text, h_text = draw.textlength(text, font=font), 18
            x_pos = (W - int(w_text)) // 2
            draw.text((x_pos, y_pos), text, fill=(30, 30, 30), font=font)
            return y_pos + int(h_text) + 16

        y = _draw_center(title, y, font_title)
        y = _draw_center(subtitle, y + 10, font_sub)
        y = _draw_center(sub2, y + 6, font_sub)
        y = _draw_center(sub3, y + 6, font_sub)
        pages.append(cover)
    except Exception:
        pass

    # Overview
    if ceremonies:
        try:
            summary = Image.new("RGB", (W, H), (255, 255, 255))
            d = ImageDraw.Draw(summary)
            f_title = ImageFont.load_default()
            f_text = ImageFont.load_default()
            y = 80
            head = f"{couple} - {place}" if couple and place else "Guest Style Guide Overview"
            d.text((80, y), head, fill=(0, 0, 0), font=f_title)
            y += 30
            if dates_txt:
                d.text((80, y), dates_txt, fill=(0, 0, 0), font=f_text)
                y += 24
            if hotel_txt:
                d.text((80, y), f"Hotel: {hotel_txt}", fill=(0, 0, 0), font=f_text)
                y += 24
            y += 8
            for idx, c in enumerate(ceremonies, start=1):
                colors = ", ".join(getattr(c, "palette", []) or [])
                line1 = f"{idx}. {getattr(c, 'name', '')} | {getattr(c, 'event_date', '')} | {getattr(c, 'time_of_day', '')}"
                line2 = f"   Mood: {getattr(c, 'mood', '')} | Palette: {colors} | Dress: {getattr(c, 'dress_code', '')}"
                d.text((80, y), line1, fill=(0, 0, 0), font=f_text)
                y += 22
                d.text((80, y), line2, fill=(0, 0, 0), font=f_text)
                y += 28
                note = getattr(c, "guest_note", None)
                if note:
                    d.text((100, y), f"Note: {note}", fill=(0, 0, 0), font=f_text)
                    y += 24
            pages.append(summary)
            dbg["ceremonies"] = [getattr(c, "name", "") for c in ceremonies]
        except Exception:
            pass

    # Palette
    if design_spec is not None:
        try:
            palette_hex = list(getattr(design_spec, "palette_hex", []) or [])
            palette_names = list(getattr(design_spec, "palette_names", []) or [])
            if palette_hex or palette_names:
                pal = Image.new("RGB", (W, H), (250, 250, 248))
                d = ImageDraw.Draw(pal)
                f_title = ImageFont.load_default()
                f_text = ImageFont.load_default()
                d.text((80, 80), "Color Palette", fill=(0, 0, 0), font=f_title)
                x, y = 80, 140
                sw = 160
                for i in range(max(len(palette_hex), len(palette_names))):
                    name = palette_names[i] if i < len(palette_names) else ""
                    col = palette_hex[i] if i < len(palette_hex) else None
                    box = (x, y, x + sw, y + 90)
                    if col and isinstance(col, str) and col.strip().startswith('#') and len(col.strip()) >= 4:
                        try:
                            rgb = tuple(int(col.strip()[j:j+2], 16) for j in (1, 3, 5))
                        except Exception:
                            rgb = (230, 230, 230)
                    else:
                        rgb = (230, 230, 230)
                    d.rectangle(box, fill=rgb, outline=(200, 200, 200))
                    d.text((x, y + 98), f"{name} {col or ''}".strip(), fill=(20, 20, 20), font=f_text)
                    x += sw + 40
                    if x + sw + 80 > W:
                        x = 80
                        y += 150
                pages.append(pal)
        except Exception:
            pass

    # Ceremony pages
    for idx, c in enumerate(ceremonies, start=1):
        event_name = getattr(c, 'name', f'Event {idx}')
        slug = _slugify(event_name)
        gen_dir = os.path.join('assets', 'style_guides', 'generated')
        os.makedirs(gen_dir, exist_ok=True)
        mood_path = os.path.join(gen_dir, f"{idx:02d}_{slug}.png")
        # Logs about expected image path and existence
        try:
            print(f"[StyleGuide] Generating image for ceremony '{event_name}'")
        except Exception:
            pass

        # Generate main mood image if needed, with explicit logging and regen
        regeneration_attempted = False
        save_attempted = False
        # If router not provided, try to create one as a safe fallback
        if router is None:
            try:
                from app.services.model_router import ModelRouter
                router = ModelRouter()
                print("[StyleGuide] Router was None; instantiated a local ModelRouter fallback.")
            except Exception as _e:
                try:
                    print(f"[StyleGuide] Router unavailable; skipping generation. reason={_e}")
                except Exception:
                    pass

        if router is not None and (not os.path.exists(mood_path) or os.path.getsize(mood_path) == 0):
            try:
                from app.prompts.artifact_prompts import build_styleguide_image_prompt_struct
                built = build_styleguide_image_prompt_struct(
                    profile=profile,
                    design_spec=getattr(state, 'design_spec', None),
                    ceremony=c,
                    event_name=event_name,
                )
                prompt = built.get("image_prompt", "")
                try:
                    built_prompts.append(built)
                except Exception:
                    pass
                # Build prompt via guest-wardrobe builder and generate
                regeneration_attempted = True
                save_attempted = True
                _saved, _meta = router.generate_invite_image(prompt, out_path=mood_path, state=state)
                exists_after = os.path.exists(mood_path) and os.path.getsize(mood_path) > 0
                # Silent; summary printed after pages saved
            except Exception as e:
                try:
                    import traceback as _tb
                    print(f"[StyleGuide] Exception during generation for '{event_name}': {e}")
                    print(_tb.format_exc())
                except Exception:
                    pass
            # If still missing, attempt one more time with a simplified guest-wardrobe prompt
            if not (os.path.exists(mood_path) and os.path.getsize(mood_path) > 0):
                try:
                    pal_txt = ", ".join(getattr(c, 'palette', []) or [])
                    simple_prompt = (
                        f"Create one premium vertical guest wardrobe collage for '{event_name}'. "
                        f"Mood/theme: {getattr(c, 'mood', '')}; palette: {pal_txt}; dress code: {getattr(c, 'dress_code', '')}. "
                        f"Include mens and womens guestwear, accessories, footwear; no bride/groom portraits; no text overlays. Polished editorial layout."
                    )
                    save_attempted = True
                    _saved2, _meta2 = router.generate_invite_image(simple_prompt, out_path=mood_path, state=state)
                    exists_after2 = os.path.exists(mood_path) and os.path.getsize(mood_path) > 0
                    # Silent; summary printed after pages saved
                    if not exists_after2:
                        try:
                            print(f"[StyleGuide] No image returned for ceremony '{event_name}'")
                        except Exception:
                            pass
                except Exception as e:
                    try:
                        import traceback as _tb
                        print(f"[StyleGuide] Exception during fallback generation for '{event_name}': {e}")
                        print(_tb.format_exc())
                    except Exception:
                        pass
        else:
            # No router or file already exists
            try:
                if router is None:
                    print("[StyleGuide] Router unavailable; skipping generation.")
                else:
                    # File already exists; log quick confirmation
                    print("[StyleGuide] Existing moodboard detected; generation skipped.")
            except Exception:
                pass
        # No extra logs here to avoid duplicates

        # Skip tile generation per single-image policy
        try:
            print("[StyleGuide] Tile generation skipped")
        except Exception:
            pass

        # Compose page
        page = Image.new("RGB", (W, H), (252, 252, 250))
        d = ImageDraw.Draw(page)
        f_title = ImageFont.load_default()
        f_text = ImageFont.load_default()
        # Title (safe write even if a prior line failed)
        try:
            d.text((80, 60), f"{event_name} — Style & Mood", fill=(0, 0, 0), font=f_title)
        except Exception:
            try:
                d.text((80, 60), f"{event_name} | Style & Mood", fill=(0, 0, 0), font=f_title)
            except Exception:
                pass
        d.text((80, 60), f"{event_name} — Style & Mood", fill=(0, 0, 0), font=f_title)

        # Right details
        x_info, y_info = W - 460, 120
        # Guest-focused info block
        pal_txt = ", ".join(getattr(c, "palette", []) or [])
        dress_txt = getattr(c, "dress_code", "") or ""
        mood_txt = getattr(c, "mood", "") or ""
        def _join(vals):
            return ", ".join([v for v in (vals or []) if v])
        def _women_suggest():
            if "cocktail" in dress_txt.lower():
                return f"sleek cocktail dress or contemporary saree in {pal_txt or 'event colors'}"
            if any(k in dress_txt.lower() for k in ["traditional", "ethnic", "indian"]):
                return f"sarees or lehengas; tones from {pal_txt or 'palette'}"
            if "beach" in (hotel_txt or "").lower():
                return f"flowy maxi / resort-chic saree; breathable fabrics"
            return f"elegant dress or saree aligned to {mood_txt or 'event mood'}"
        def _men_suggest():
            if "cocktail" in dress_txt.lower():
                return f"tailored suit; tonal tie/pocket square; {pal_txt or 'palette'} accents"
            if any(k in dress_txt.lower() for k in ["traditional", "ethnic", "indian"]):
                return f"kurta-set, bandhgala or sherwani; subtle {pal_txt or 'palette'} pocket square"
            if "beach" in (hotel_txt or "").lower():
                return f"linen suit or band-collar shirt & trousers; loafers"
            return f"tailored separates; smart shirt; {pal_txt or 'palette'} accents"
        def _footwear_accessories():
            parts = []
            if any(k in (hotel_txt or "").lower() for k in ["lawn", "beach", "garden", "outdoor"]):
                parts.append("women: wedges/block heels; men: loafers/juttis")
            if "evening" in (getattr(c, "time_of_day", "") or "").lower():
                parts.append("metallic accents, refined jewelry")
            parts.append("textures: silk, georgette, jacquard per mood")
            return "; ".join(parts)
        fields = [
            ("Date / Time", f"{getattr(c, 'event_date', '')} {getattr(c, 'time_of_day', '')}".strip()),
            ("Mood / Theme", mood_txt),
            ("Suggested Color Palette", pal_txt),
            ("Suggested Attire for Women", _women_suggest()),
            ("Suggested Attire for Men", _men_suggest()),
            ("Footwear / Accessory", _footwear_accessories()),
        ]
        for k, v in fields:
            if v:
                d.text((x_info, y_info), f"{k}: {v}", fill=(15, 15, 15), font=f_text)
                y_info += 26
        note = getattr(c, "guest_note", None)
        if note:
            d.text((x_info, y_info), f"Styling note for guests: {note}", fill=(15, 15, 15), font=f_text)
            y_info += 24

        # Swatches
        cpal = list(getattr(c, 'palette', []) or [])
        if cpal:
            sx, sy = x_info, y_info + 16
            sw, sh = 96, 44
            for i, col in enumerate(cpal):
                rgb = (230, 230, 230)
                if isinstance(col, str) and col.strip().startswith('#') and len(col.strip()) >= 4:
                    try:
                        cs = col.strip()
                        rgb = tuple(int(cs[j:j+2], 16) for j in (1, 3, 5))
                    except Exception:
                        rgb = (230, 230, 230)
                d.rectangle((sx, sy, sx + sw, sy + sh), fill=rgb, outline=(200, 200, 200))
                d.text((sx, sy + sh + 6), str(col), fill=(10, 10, 10), font=f_text)
                sx += sw + 16
                if (i + 1) % 3 == 0:
                    sx = x_info
                    sy += sh + 30

        # Collage area
        bx0, by0, bx1, by1 = (80, 120, W - 500, H - 160)
        d.rectangle((bx0, by0, bx1, by1), outline=(210, 210, 210), width=2)
        used_images: List[str] = []
        try:
            print(f"[StyleGuide] Ceremony '{event_name}' collage box: ({bx0},{by0})-({bx1},{by1})")
        except Exception:
            pass
        embed_succeeded = False
        # Single-image placement logic
        single_path = os.path.join(gen_dir, f"{idx:02d}_wedding.png")
        try:
            print(f"[StyleGuide] Using single ceremony image: {single_path}")
            print(f"[StyleGuide] Single image exists: {os.path.exists(single_path) and os.path.getsize(single_path) > 0}")
        except Exception:
            pass
        if os.path.exists(single_path) and os.path.getsize(single_path) > 0:
            try:
                im = Image.open(single_path)
                im = im.convert('RGB')
                frame_w, frame_h = (bx1 - bx0 - 8), (by1 - by0 - 8)
                im.thumbnail((frame_w, frame_h))
                x = bx0 + (frame_w - im.width) // 2 + 4
                y = by0 + (frame_h - im.height) // 2 + 4
                page.paste(im, (x, y))
                used_images.append(single_path)
                embed_succeeded = True
                try:
                    print("[StyleGuide] Embedded single image successfully")
                except Exception:
                    pass
            except Exception:
                embed_succeeded = False

        # Render fallback panel if needed (no embed success log to avoid noise)
        if not embed_succeeded:
            try:
                d.rectangle((bx0, by0, bx1, by1), fill=(255, 245, 235), outline=(210, 210, 210), width=2)
                msg = "Moodboard image unavailable for this ceremony"
                tw = d.textlength(msg, font=f_title)
                tx = bx0 + max(16, int(((bx1 - bx0) - tw) // 2))
                ty = by0 + (by1 - by0) // 2 - 10
                d.text((tx, ty), msg, fill=(120, 60, 40), font=f_title)
            except Exception:
                pass

        dbg["images"][event_name] = used_images if used_images else ([])
        # Comfort/climate note per page
        rec_y = H - 120
        climate = getattr(profile, 'destination_climate', '') if profile is not None else ''
        closing_line = "Comfort note: consider breathable fabrics for day; layers for cool evenings."
        if isinstance(climate, str) and climate:
            closing_line = f"Comfort note: {climate}."
        d.text((80, rec_y), closing_line, fill=(25, 25, 25), font=f_text)
        pages.append(page)

    # Closing note
    try:
        closing = Image.new("RGB", (W, H), (246, 246, 244))
        dc = ImageDraw.Draw(closing)
        f_title = ImageFont.load_default()
        f_text = ImageFont.load_default()
        y = 140
        dc.text((80, y), "A Note on Styling & Practicalities", fill=(0, 0, 0), font=f_title)
        y += 36
        lines = [
            "- Coordinate with the suggested palette for a cohesive guest look.",
            "- Prefer breathable fabrics for day events; consider layers for late evenings.",
            "- Comfortable footwear is encouraged for outdoor venues.",
            "- Jewelry can be minimal or statement based on the event mood—avoid overpowering the ensemble.",
            "- Avoid neon/clashing tones unless noted; aim for elegant, camera-friendly textures.",
        ]
        for ln in lines:
            dc.text((90, y), ln, fill=(20, 20, 20), font=f_text)
            y += 26
        pages.append(closing)
    except Exception:
        pass

    if not pages:
        return {"path": out_path, "exists": False, "error": "no images found", "page_count": 0}

    try:
        first, rest = pages[0], pages[1:]
        first.save(out_path, save_all=True, append_images=rest)
    except Exception as e:
        return {"path": out_path, "exists": False, "error": str(e), "page_count": len(pages)}

    info = _file_info(out_path)
    info["page_count"] = len(pages)
    # Attach structured prompts to state.media for downstream use
    try:
        state = None if isinstance(state_or_out, str) else state_or_out
        if state is not None and built_prompts:
            media = getattr(state, "media", None)
            if media is None:
                setattr(state, "media", type("Media", (), {})())
                media = getattr(state, "media")
            setattr(media, "styleguide_prompts", built_prompts)
    except Exception:
        pass
    try:
        dbg["pages"] = len(pages)
        print(f"[StyleGuide] pages={dbg.get('pages')} out_path={out_path}")
    except Exception:
        pass
    return info
