import os
from typing import Any, Dict, List, Optional, Tuple

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
    """Build a ceremony-aware style guide PDF with large event pages.

    Structure:
    - Cover page
    - Summary page
    - One page per selected ceremony
    - Closing notes page
    """
    out_path = state_or_out if isinstance(state_or_out, str) else out_path_or_events
    force = bool(kwargs.get("force", False))
    _ensure_dir(out_path)
    try:
        print("[StyleGuide][DEBUG] Entered build_style_guide_pdf")
        print("[StyleGuide] Building PDF")
        print("[StyleGuide][DEBUG] Entered style guide generation orchestrator")
        print("[StyleGuide][DEBUG] Entered PDF builder")
    except Exception:
        pass
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
                names = [getattr(c, 'name', '') for c in ceremonies]
                print(f"[StyleGuide][DEBUG] Selected ceremonies count: {len(ceremonies)}")
                print(f"[StyleGuide][DEBUG] Selected ceremonies names: {names}")
            except Exception as e:
                try:
                    print(f"[StyleGuide][DEBUG] Error while logging selected ceremonies: {e}")
                except Exception:
                    pass
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
            # Hashtag settings (optional)
            try:
                use_tag = bool(getattr(state, "use_wedding_hashtag", False))
                include_tag_style = bool(getattr(state, "include_hashtag_in_style_guide", False))
                wedding_hashtag = str(getattr(state, "wedding_hashtag", "") or "").strip()
            except Exception:
                use_tag = False
                include_tag_style = False
                wedding_hashtag = ""
    except Exception:
        ceremonies = []

    pages: List[Image.Image] = []
    built_prompts: List[Dict[str, Any]] = []
    W, H = 1240, 1754

    # Typography helpers (local to keep changes contained)
    def _try_truetype(candidates: List[str], size: int) -> Any:
        try:
            # Common Windows font directory
            win_dir = os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts")
            search_paths = ["", win_dir]
            for base in search_paths:
                for name in candidates:
                    fp = os.path.join(base, name) if base else name
                    try:
                        return ImageFont.truetype(fp, size=size)
                    except Exception:
                        continue
        except Exception:
            pass
        try:
            # PIL often bundles DejaVu fonts
            return ImageFont.truetype("DejaVuSans.ttf", size=size)
        except Exception:
            return ImageFont.load_default()

    def _serif(size: int) -> Any:
        return _try_truetype([
            "Georgia.ttf", "georgia.ttf",
            "Times New Roman.ttf", "times.ttf", "timesbd.ttf",
            "Cambria.ttf", "Garamond.ttf", "Constantia.ttf", "Book Antiqua.ttf", "Palatino Linotype.ttf",
            "DejaVuSerif.ttf", "LiberationSerif-Regular.ttf",
        ], size)

    def _sans(size: int, bold: bool = False) -> Any:
        if bold:
            return _try_truetype([
                "Arial Bold.ttf", "arialbd.ttf", "Calibri Bold.ttf", "calibrib.ttf", "Segoe UI Bold.ttf",
                "DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf",
            ], size)
        return _try_truetype([
            "Arial.ttf", "arial.ttf", "Helvetica.ttf", "Calibri.ttf", "calibri.ttf", "Segoe UI.ttf",
            "DejaVuSans.ttf", "LiberationSans-Regular.ttf",
        ], size)

    def _text_height(draw_ctx: ImageDraw.ImageDraw, text: str, font: Any) -> int:
        try:
            box = draw_ctx.textbbox((0, 0), text, font=font)
            return (box[3] - box[1])
        except Exception:
            return 18

    # Cover
    try:
        cover = Image.new("RGB", (W, H), (244, 242, 238))
        draw = ImageDraw.Draw(cover)
        # Elegant frame
        draw.rectangle([(80, 120), (W - 80, H - 120)], outline=(200, 198, 194), width=3)

        # Fonts
        f_title = _serif(88)
        f_sub = _sans(40)
        f_info = _sans(34)

        # Content
        y = 320
        title = couple or "Guest Style Guide"
        subtitle = place or ""
        sub2 = dates_txt or ""
        sub3 = f"Hotel: {hotel_txt}" if hotel_txt else ""

        def _draw_center(text: str, y_pos: int, font, color=(30, 30, 30), gap=18) -> int:
            if not text:
                return y_pos
            w_text = draw.textlength(text, font=font)
            x_pos = int((W - w_text) // 2)
            draw.text((x_pos, y_pos), text, fill=color, font=font)
            return y_pos + _text_height(draw, text, font) + gap

        y = _draw_center(title, y, f_title, color=(25, 25, 25), gap=32)
        y = _draw_center(subtitle, y, f_sub, color=(40, 40, 40), gap=12)
        y = _draw_center(sub2, y, f_info, color=(55, 55, 55), gap=10)
        y = _draw_center(sub3, y, f_info, color=(55, 55, 55), gap=10)
        # Optional hashtag placed elegantly near footer or below titles
        try:
            if 'use_tag' in locals() and 'include_tag_style' in locals():
                if use_tag and include_tag_style:
                    tag = wedding_hashtag if 'wedding_hashtag' in locals() else ""
                    tag = (tag or "").strip()
                    if tag:
                        print(f"[StyleGuide] Hashtag added to cover: {tag}")
                        # Footer placement (centered, high-contrast on light bg)
                        w_text = int(draw.textlength(tag, font=f_info))
                        x_foot = int((W - w_text) // 2)
                        y_foot = int(H * 0.94)
                        draw.text((x_foot, y_foot), tag, fill=(50, 50, 50), font=f_info)
                        try:
                            print(f"[StyleGuide] Cover hashtag rendered at: x={x_foot}, y={y_foot}, text={tag}")
                        except Exception:
                            pass
        except Exception:
            pass
        pages.append(cover)
    except Exception:
        pass

    # Summary
    if ceremonies:
        try:
            summary = Image.new("RGB", (W, H), (255, 255, 255))
            d = ImageDraw.Draw(summary)
            f_head = _serif(56)
            f_meta = _sans(34)
            f_list = _sans(32)
            f_label = _sans(30, bold=True)

            y = 96
            head = f"{couple} · {place}" if couple and place else (couple or place or "Guest Style Guide Overview")
            d.text((100, y), head, fill=(25, 25, 25), font=f_head)
            y += _text_height(d, head, f_head) + 16

            if dates_txt:
                d.text((100, y), dates_txt, fill=(40, 40, 40), font=f_meta)
                y += _text_height(d, dates_txt, f_meta) + 6
            if hotel_txt:
                t = f"Hotel: {hotel_txt}"
                d.text((100, y), t, fill=(40, 40, 40), font=f_meta)
                y += _text_height(d, t, f_meta) + 18

            # Thin separator
            d.line([(100, y), (W - 100, y)], fill=(220, 220, 220), width=2)
            y += 16

            for idx, c in enumerate(ceremonies, start=1):
                colors = ", ".join(getattr(c, "palette", []) or [])
                name = f"{idx:02d}. {getattr(c, 'name', '')}"
                meta = f"{(getattr(c, 'event_date', '') or '').strip()} · {(getattr(c, 'time_of_day', '') or '').strip()}"
                d.text((100, y), name, fill=(30, 30, 30), font=f_label)
                y += _text_height(d, name, f_label) + 2
                d.text((100, y), meta, fill=(55, 55, 55), font=f_list)
                y += _text_height(d, meta, f_list) + 4

                line2 = f"Mood: {(getattr(c, 'mood', '') or '').strip()}  ·  Palette: {colors}  ·  Dress: {(getattr(c, 'dress_code', '') or '').strip()}"
                d.text((100, y), line2, fill=(60, 60, 60), font=f_list)
                y += _text_height(d, line2, f_list) + 6

                note = (getattr(c, "guest_note", "") or "").strip()
                if note and note.lower() != 'no':
                    note_t = f"Note: {note}"
                    d.text((120, y), note_t, fill=(70, 70, 70), font=f_list)
                    y += _text_height(d, note_t, f_list) + 10

                # Light divider between ceremonies
                d.line([(100, y), (W - 100, y)], fill=(235, 235, 235), width=1)
                y += 16
            # pages.append(summary)  # Removed to drop the summary page for a visual-first board
        except Exception:
            pass

    # Ceremony pages
    def _find_existing_image_for_ceremony(
        ceremony: Any,
        idx: int,
        slug: str,
        preferred_path: str,
    ) -> Tuple[Optional[str], List[str]]:
        """Return the most reliable, already-saved image path for this ceremony.

        Priority order:
        1) Explicit path on ceremony object if present and exists
        2) The preferred_path if it exists
        3) A file in known output folders that matches slug or index pattern

        Returns (selected_path, debug_candidates_checked)
        """
        checked: List[str] = []
        # 0) Global mapping on state.media if present (outer kwargs)
        try:
            parent_state = kwargs.get("_state_ref")  # injected via outer scope
        except Exception:
            parent_state = None
        if parent_state is not None:
            try:
                media = getattr(parent_state, "media", None)
                if media is not None:
                    img_map = getattr(media, "styleguide_image_map", None)
                    if isinstance(img_map, dict):
                        key = (getattr(ceremony, "name", None) or slug or str(idx)).strip()
                        mapped = img_map.get(key)
                        if isinstance(mapped, str) and mapped:
                            checked.append(mapped)
                            if os.path.exists(mapped) and os.path.getsize(mapped) > 0:
                                return mapped, checked
            except Exception:
                pass
        # 1) Ceremony-attached attributes (if any exist in user env)
        for attr in (
            "styleguide_image_path",
            "wardrobe_image_path",
            "moodboard_image_path",
            "image_path",
        ):
            try:
                p = getattr(ceremony, attr, None)
            except Exception:
                p = None
            if isinstance(p, str) and p:
                checked.append(p)
                if os.path.exists(p) and os.path.getsize(p) > 0:
                    return p, checked

        # 2) Preferred (builder) path
        if preferred_path:
            checked.append(preferred_path)
            if os.path.exists(preferred_path) and os.path.getsize(preferred_path) > 0:
                return preferred_path, checked

        # 3) Search known folders without reconstructing a new filename
        search_dirs = [
            os.path.join("assets", "style_guides", "generated"),
            os.path.join("assets", "style_guides", "generated-images"),
            os.path.join("assets", "style_guides", "generated_images"),
        ]
        candidates: List[str] = []
        idx_strs = [f"{idx}", f"{idx:02d}"]
        for ddir in search_dirs:
            try:
                if not os.path.isdir(ddir):
                    continue
                for name in os.listdir(ddir):
                    lower = name.lower()
                    if not (lower.endswith(".png") or lower.endswith(".jpg") or lower.endswith(".jpeg") or lower.endswith(".webp")):
                        continue
                    full = os.path.join(ddir, name)
                    checked.append(full)
                    # Heuristics: prefer files that mention the slug; otherwise ones containing the ceremony index token
                    if slug and slug in lower:
                        if os.path.exists(full) and os.path.getsize(full) > 0:
                            candidates.append(full)
                    else:
                        if any(tok in lower for tok in idx_strs):
                            if os.path.exists(full) and os.path.getsize(full) > 0:
                                candidates.append(full)
            except Exception:
                continue

        if candidates:
            try:
                # Choose most recent
                chosen = sorted(candidates, key=lambda p: os.path.getmtime(p), reverse=True)[0]
                return chosen, checked
            except Exception:
                return candidates[0], checked

        return None, checked
    try:
        print("[StyleGuide][DEBUG] Entered ceremony image generation loop")
    except Exception:
        pass
    for idx, c in enumerate(ceremonies, start=1):
        event_name = getattr(c, 'name', f'Event {idx}')
        try:
            print(f"[StyleGuide][DEBUG] Processing ceremony: {event_name}")
        except Exception:
            pass
        slug = _slugify(event_name)
        gen_dir = os.path.join('assets', 'style_guides', 'generated')
        os.makedirs(gen_dir, exist_ok=True)
        mood_path = os.path.join(gen_dir, f"{idx:02d}_{slug}.png")
        # One-time ceremony-level debug context
        try:
            cer_info = {
                "name": getattr(c, 'name', None),
                "event_date": getattr(c, 'event_date', None),
                "time_of_day": getattr(c, 'time_of_day', None),
                "mood": getattr(c, 'mood', None),
                "palette": list(getattr(c, 'palette', []) or []),
                "dress_code": getattr(c, 'dress_code', None),
                "guest_note": getattr(c, 'guest_note', None),
                "include_in_style_guide": getattr(c, 'include_in_style_guide', None),
            }
            print(f"[StyleGuide][DEBUG] Ceremony input: {cer_info}")
            print(f"[StyleGuide][DEBUG] Starting image generation for: {event_name}")
            print(f"[StyleGuide][DEBUG] Slug/index chosen: {slug} / {idx:02d}")
            print(f"[StyleGuide][DEBUG] Planned output path: {os.path.abspath(mood_path)}")
        except Exception:
            pass

        # Generate image only if missing or force=True
        saved_path: Optional[str] = None
        if router is None:
            try:
                print("[StyleGuide][DEBUG] Generation skipped: generation disabled")
            except Exception:
                pass
            # list folder contents for context
            try:
                contents = sorted(os.listdir(gen_dir)) if os.path.isdir(gen_dir) else []
                print(f"[StyleGuide][DEBUG] Generated folder contents: {contents}")
            except Exception:
                pass
        elif (not force) and os.path.exists(mood_path) and os.path.getsize(mood_path) > 0:
            try:
                print("[StyleGuide][DEBUG] Generation skipped: existing file detected")
                contents = sorted(os.listdir(gen_dir)) if os.path.isdir(gen_dir) else []
                print(f"[StyleGuide][DEBUG] Generated folder contents: {contents}")
            except Exception:
                pass
        elif router is not None and (force or not (os.path.exists(mood_path) and os.path.getsize(mood_path) > 0)):
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
                    preview = str(prompt)[:300].replace('\n', ' ')
                except Exception:
                    preview = "<unavailable>"
                try:
                    print(f"[StyleGuide][DEBUG] Built prompt for ceremony: {preview}")
                except Exception:
                    pass
                try:
                    built_prompts.append(built)
                except Exception:
                    pass
                try:
                    print("[StyleGuide][DEBUG] Calling image generator now")
                    saved_path, meta = router.generate_invite_image(prompt, out_path=mood_path, state=state)
                except Exception as e:
                    try:
                        print(f"[StyleGuide][DEBUG] Image generation error: {e}")
                    except Exception:
                        pass
                    saved_path, meta = None, {"error": str(e)}
                ok = bool(saved_path) and os.path.exists(mood_path) and os.path.getsize(mood_path) > 0
                try:
                    print(f"[StyleGuide][DEBUG] Image generator returned: {'success' if ok else 'failure'}")
                    print(f"[StyleGuide][DEBUG] Returned image object/path: {saved_path}")
                except Exception:
                    pass
                try:
                    exists_after = os.path.exists(mood_path)
                    print(f"[StyleGuide][DEBUG] Saved file exists after generation: {'yes' if exists_after else 'no'}")
                except Exception:
                    pass
                # folder listing after generation
                try:
                    contents = sorted(os.listdir(gen_dir)) if os.path.isdir(gen_dir) else []
                    print(f"[StyleGuide][DEBUG] Generated folder contents: {contents}")
                except Exception:
                    pass
                # Persist direct mapping on the ceremony/state for later resolution
                try:
                    if saved_path:
                        setattr(c, "styleguide_image_path", saved_path)
                        # Also mirror into media map early if available
                        st = None if isinstance(state_or_out, str) else state_or_out
                        if st is not None:
                            media = getattr(st, "media", None)
                            if media is None:
                                setattr(st, "media", type("Media", (), {})())
                                media = getattr(st, "media")
                            mg = getattr(media, "styleguide_image_map", None)
                            if not isinstance(mg, dict):
                                mg = {}
                                setattr(media, "styleguide_image_map", mg)
                            mg[getattr(c, 'name', event_name)] = saved_path
                except Exception:
                    pass
            except Exception:
                pass

        # Compose page(s). For the first ceremony page only (editorial spread),
        # render a clean, image-first layout with just the main heading and
        # a centered image occupying ~75-85% of page height.
        editorial = True

        page = Image.new("RGB", (W, H), (252, 252, 250))
        d = ImageDraw.Draw(page)
        f_title = _serif(58)
        f_label = _sans(30, bold=True)
        f_text = _sans(28)

        # Title (kept for both; minimal on editorial)
        title_x, title_y = 80, 60
        d.text((title_x, title_y), f"{event_name}", fill=(25, 25, 25), font=f_title)

        # Image area
        if editorial:
            # Premium editorial margins
            left_margin = right_margin = 120
            top_margin = 160
            bottom_margin = 160

            # Space below title before image
            title_h = _text_height(d, f"{event_name}", f_title)
            # Optional small subtitle under the ceremony title (e.g., "Day 1   Evening")
            try:
                _tod = (getattr(c, 'time_of_day', '') or '').strip()
            except Exception:
                _tod = ''
            _subtitle = f"Day {idx}   {_tod}".strip() if _tod else (f"Day {idx}" if idx else '')
            _subtitle_font = _sans(26)
            if _subtitle:
                d.text((title_x, title_y + title_h + 6), _subtitle, fill=(70, 70, 70), font=_subtitle_font)
                title_block_h = title_h + 6 + _text_height(d, _subtitle, _subtitle_font)
            else:
                title_block_h = title_h
            content_top = max(top_margin, title_y + title_block_h + 24)
            content_bottom = H - bottom_margin
            content_height = max(0, content_bottom - content_top)

            # Target ~82% of page height for image, but do not exceed available
            target_h = min(int(H * 0.82), content_height)
            target_w = W - left_margin - right_margin

            bx0, by0 = left_margin, content_top
            bx1, by1 = W - right_margin, content_top + target_h
            # No decorative rectangle/frame for editorial layout
        else:
            # Original bordered image frame + info blocks below
            margin = 80
            bx0, by0 = margin, 140
            bx1, by1 = W - margin, H - 360
            d.rectangle((bx0, by0, bx1, by1), outline=(210, 210, 210), width=2)

        # Resolve final image path from actual saved files (don't reconstruct)
        try:
            print(f"[StyleGuide] Ceremony: {event_name}")
        except Exception:
            pass

        # Allow resolver to see state for global mapping lookups
        kwargs["_state_ref"] = None if isinstance(state_or_out, str) else state_or_out
        resolved_path, _checked = _find_existing_image_for_ceremony(
            ceremony=c,
            idx=idx,
            slug=slug,
            preferred_path=(saved_path or mood_path),
        )
        # Logging: actual generation path and the final embed path
        try:
            if saved_path:
                print(f"[StyleGuide] Actual generated image path: {saved_path}")
        except Exception:
            pass
        try:
            embed_path_log = resolved_path or (saved_path or mood_path)
            print(f"[StyleGuide][DEBUG] Handing image path to PDF builder: {embed_path_log}")
            print(f"[StyleGuide][DEBUG] PDF embed exists: {'yes' if (embed_path_log and os.path.exists(embed_path_log)) else 'no'}")
            # Wrong path mapping hint: saved exists but resolved missing
            try:
                if saved_path and (resolved_path != saved_path) and (not (resolved_path and os.path.exists(resolved_path))):
                    print("[StyleGuide][DEBUG] Generation skipped: wrong path mapping (resolved differs, file missing)")
            except Exception:
                pass
        except Exception:
            pass
        try:
            exists_flag = bool(resolved_path and os.path.exists(resolved_path) and os.path.getsize(resolved_path) > 0)
            print(f"[StyleGuide] Image exists: {'yes' if exists_flag else 'no'}")
        except Exception:
            exists_flag = bool(resolved_path and os.path.exists(resolved_path) and os.path.getsize(resolved_path) > 0)
            pass

        embed_succeeded = False
        if resolved_path and exists_flag:
            try:
                im = Image.open(resolved_path).convert('RGB')
                frame_w, frame_h = (bx1 - bx0 - 16), (by1 - by0 - 16)
                im.thumbnail((frame_w, frame_h))
                x = bx0 + (frame_w - im.width) // 2 + 8
                y = by0 + (frame_h - im.height) // 2 + 8
                page.paste(im, (x, y))
                embed_succeeded = True
                try:
                    print(f"[StyleGuide] Embedded image: {resolved_path}")
                except Exception:
                    pass
            except Exception as e:
                try:
                    print(f"[StyleGuide][DEBUG] Embed error: {e}")
                except Exception:
                    pass
                embed_succeeded = False

        if not embed_succeeded:
            # Graceful placeholder without captions (no extra text for editorial)
            try:
                fill_rect = (255, 245, 235)
                if editorial:
                    d.rectangle((bx0, by0, bx1, by1), fill=fill_rect)
                else:
                    d.rectangle((bx0, by0, bx1, by1), fill=fill_rect, outline=(210, 210, 210), width=2)
                try:
                    print("[StyleGuide] Fallback placeholder used")
                except Exception:
                    pass
            except Exception:
                pass

        # Only non-editorial pages include detailed text blocks
        if not editorial:
            # Info section below image
            y_text = by1 + 32
            pal_txt = ", ".join(getattr(c, "palette", []) or [])
            fields = [
                ("Day / Date", (getattr(c, 'event_date', '') or '').strip()),
                ("Time", (getattr(c, 'time_of_day', '') or '').strip()),
                ("Mood / Theme", (getattr(c, 'mood', '') or '').strip()),
                ("Color Palette", pal_txt),
                ("Dress Code", (getattr(c, 'dress_code', '') or '').strip()),
            ]
            guest_note = (getattr(c, 'guest_note', '') or '').strip()
            if guest_note and guest_note.lower() != 'no':
                fields.append(("Guest Note", guest_note))

            x_text = 80  # original margin value
            for label, val in fields:
                if not val:
                    continue
                d.text((x_text, y_text), f"{label}", fill=(40, 40, 40), font=f_label)
                y_text += _text_height(d, label, f_label) + 4
                d.text((x_text, y_text), val, fill=(30, 30, 30), font=f_text)
                y_text += _text_height(d, val, f_text) + 18

            # Climate note
            climate = getattr(profile, 'destination_climate', '') if profile is not None else ''
            closing_line = (
                f"Comfort note: {climate}." if isinstance(climate, str) and climate
                else "Comfort note: breathable fabrics for day; light layers for cool evenings."
            )
            d.text((x_text, H - 96), closing_line, fill=(35, 35, 35), font=_sans(28))

        pages.append(page)
        try:
            print(f"[StyleGuide] Ceremony page added: {event_name}")
        except Exception:
            pass

    # Closing note
    try:
        closing = Image.new("RGB", (W, H), (246, 246, 244))
        dc = ImageDraw.Draw(closing)
        f_t = _serif(46)
        f_b = _sans(28)
        y = 140
        dc.text((100, y), "A Note on Styling & Practicalities", fill=(25, 25, 25), font=f_t)
        y += _text_height(dc, "A Note on Styling & Practicalities", f_t) + 20
        lines = [
            "• Coordinate with the suggested palette for a cohesive guest look.",
            "• Prefer breathable fabrics for day events; consider layers for late evenings.",
            "• Comfortable footwear is encouraged for outdoor venues.",
            "• Jewelry can be minimal or statement based on the event mood; avoid overpowering the ensemble.",
            "• Avoid neon/clashing tones unless noted; aim for elegant, camera-friendly textures.",
        ]
        for ln in lines:
            dc.text((110, y), ln, fill=(35, 35, 35), font=f_b)
            y += _text_height(dc, ln, f_b) + 10
        pages.append(closing)
    except Exception:
        pass

    if not pages:
        return {"path": out_path, "exists": False, "error": "no images found", "page_count": 0}

    try:
        first, rest = pages[0], pages[1:]
        first.save(out_path, save_all=True, append_images=rest)
    except Exception as e:
        try:
            print(f"[StyleGuide][DEBUG] PDF save error: {e}")
        except Exception:
            pass
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
        print(f"[StyleGuide] Saved: {out_path}")
    except Exception:
        pass
    try:
        print("[StyleGuide][DEBUG] Exiting build_style_guide_pdf")
    except Exception:
        pass
    return info
