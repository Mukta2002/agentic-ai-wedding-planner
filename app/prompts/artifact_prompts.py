from __future__ import annotations

from typing import List, Dict, Any

from app.models.schemas import (
    WeddingProfile,
    CreativePlan,
    LogisticsPlan,
    DesignDirectionSpec,
)


def _safe_join(items: List[str] | None, sep: str = ", ") -> str:
    return sep.join([str(x) for x in (items or []) if str(x).strip()])


def build_logo_prompt(
    profile: WeddingProfile,
    creative_plan: CreativePlan | None,
    design_spec: DesignDirectionSpec | None,
) -> str:
    """Build a premium logo/monogram prompt grounded in shared state only.

    Requirements:
    - Single final centered monogram/logo, no concept boards or variations.
    - Neutral clean background; polished, editorial, luxury finish.
    - Use couple initials from profile and design direction from design_spec.
    """
    bride = (profile.bride_name or "").strip()
    groom = (profile.groom_name or "").strip()
    initials = (bride[:1] + groom[:1]).upper()
    # prefer new field if provided
    text_pref = (
        (getattr(profile, "logo_text_mode", "") or getattr(profile, "logo_text_preference", "") or "")
        .strip()
        .lower()
    )

    # If no design_spec, still build from available state (no generic placeholders)
    if not design_spec:
        palette_list = []
        if creative_plan and getattr(creative_plan, "color_palette", None):
            palette_list = creative_plan.color_palette
        palette = _safe_join(palette_list)
        parts = [
            f"Create ONE final centered wedding monogram/logo for {bride} & {groom} (initials {initials}). ",
            "No multiple variations, no concept board, no palette dots, no extra brand elements. ",
            "Neutral clean background only. Premium, editorial, high-contrast mark. ",
        ]
        # Strict grounding: do not allow extra wording. Prefer initials when requested.
        if text_pref == "initials":
            parts.append(f"Render ONLY the initials '{initials}'. Do not add names, dates, or any other words. ")
        else:
            parts.append(f"Render ONLY the names '{bride} & {groom}'. Do not add dates or any other words. ")
        if palette:
            parts.append(f"Use palette: {palette}. ")
        # Minimal additive: include user preferences when present
        try:
            if getattr(profile, "logo_style", None):
                parts.append(f"Preferred style: {profile.logo_style}. ")
            if getattr(profile, "logo_colors", None):
                parts.append(f"Preferred colors: {', '.join(profile.logo_colors)}. ")
            if getattr(profile, "logo_text_preference", None):
                parts.append(
                    f"Text preference: {profile.logo_text_preference} only; do not add dates/location/extra text. "
                )
            if getattr(profile, "logo_motif", None):
                parts.append(f"Subtle motif: {profile.logo_motif}. ")
            if getattr(profile, "logo_palette", None):
                parts.append(f"Palette emphasis: {', '.join(profile.logo_palette)}. ")
            if getattr(profile, "logo_mood", None):
                parts.append(f"Mood: {profile.logo_mood}. ")
            # Additional intent controls
            if getattr(profile, "logo_feel", None):
                parts.append(f"Overall feel: {profile.logo_feel}. ")
            if getattr(profile, "logo_include_destination_symbol", None) is True:
                parts.append("Include subtle symbolic cue from the wedding destination. ")
            if getattr(profile, "logo_gender_balance", None):
                parts.append(f"Gender balance: {profile.logo_gender_balance}. ")
            if getattr(profile, "logo_detailing", None):
                parts.append(f"Detailing: {profile.logo_detailing}. ")
            if getattr(profile, "logo_hidden_motifs", None):
                parts.append(f"Consider hidden motifs: {', '.join(profile.logo_hidden_motifs)}. ")
        except Exception:
            pass
        parts.append(
            "Prefer minimal readable text; precision mark-making; subtle foil/deboss look, not overdone."
        )
        return "".join(parts)

    mood = _safe_join(design_spec.mood_keywords)
    palette_names = _safe_join(design_spec.palette_names)
    palette_hex = _safe_join(design_spec.palette_hex)
    motifs = _safe_join(design_spec.motifs)

    theme = (creative_plan.theme_name if (creative_plan and getattr(creative_plan, "theme_name", None)) else "").strip()
    parts = [
        f"Design ONE final, centered monogram/logo for {bride} & {groom} (initials {initials}). ",
        "Single presentation only — no concept board, no multiple variations, no palette dots unless extremely minimal. ",
        "Neutral background; polished editorial composition with generous negative space. ",
    ]
    if theme:
        parts.append(f"Theme: {theme}. ")
    parts.extend([
        f"Monogram direction: {design_spec.logo_direction}. ",
        f"Visual style: {design_spec.visual_style_name}; mood: {mood}; luxury: {design_spec.luxury_level}. ",
        f"Typography/lockup direction: {design_spec.typography_direction}. ",
        f"Subtle motifs allowed: {motifs}. ",
        f"Palette: {palette_names} ({palette_hex}). ",
        f"Destination cues: {design_spec.destination_story}. ",
        "Deliver a clean, vector-like, premium mark — ONE final image only.",
    ])
    # Strict grounding: add constraint on displayed text in final mark
    if text_pref == "initials":
        parts.append(f" Render ONLY the initials '{initials}'. No other words or dates.")
    else:
        parts.append(f" Render ONLY the names '{bride} & {groom}'. No dates or extra words.")
    # Honor additional explicit logo intent when provided (design-spec path)
    try:
        if getattr(profile, "logo_feel", None):
            parts.append(f" Overall feel: {profile.logo_feel}.")
        if getattr(profile, "logo_include_destination_symbol", None) is True:
            parts.append(" Include subtle symbolic cue from the wedding destination.")
        if getattr(profile, "logo_gender_balance", None):
            parts.append(f" Gender balance: {profile.logo_gender_balance}.")
        if getattr(profile, "logo_detailing", None):
            parts.append(f" Detailing: {profile.logo_detailing}.")
        if getattr(profile, "logo_hidden_motifs", None):
            parts.append(f" Hidden motifs to consider: {', '.join(profile.logo_hidden_motifs)}.")
    except Exception:
        pass
    return "".join(parts)


def build_invite_prompt(
    profile: WeddingProfile,
    creative_plan: CreativePlan | None,
    design_spec: DesignDirectionSpec | None,
) -> str:
    """Build a background-only invite art prompt (no readable text).

    We avoid injecting factual text (names/dates/venue/RSVP) into the image
    prompt to prevent hallucinated or altered information. The final text is
    rendered programmatically in a separate overlay step.
    """
    # Early return with background-only instruction to avoid text hallucinations
    mood = _safe_join(getattr(design_spec, "mood_keywords", []) if design_spec is not None else [])
    palette_names = _safe_join(getattr(design_spec, "palette_names", []) if design_spec is not None else [])
    palette_hex = _safe_join(getattr(design_spec, "palette_hex", []) if design_spec is not None else [])
    motifs = _safe_join(getattr(design_spec, "motifs", []) if design_spec is not None else [])
    typography = (getattr(design_spec, "typography_direction", "") or "").strip() if design_spec is not None else ""
    dest_story = (getattr(design_spec, "destination_story", "") or "").strip() if design_spec is not None else ""
    base_dir = (getattr(creative_plan, "invite_design_prompt", "") or "").strip() if creative_plan is not None else ""
    theme_name = (getattr(creative_plan, "theme_name", "") or "").strip() if creative_plan is not None else ""

    parts: List[str] = [
        "Design ONE final vertical invitation background artwork only. ",
        "Single full-frame card — no 3-up, no options, no stationery board. ",
        "Do NOT include any readable text: no names, no dates, no venue, no RSVP. ",
        "Leave clear, aesthetically balanced negative space for text blocks (title, details, RSVP). ",
    ]
    if base_dir:
        parts.append(f"Art direction: {base_dir}. ")
    if theme_name:
        parts.append(f"Theme: {theme_name}. ")
    try:
        # Richer creative controls
        if getattr(profile, "invite_theme", None):
            parts.append(f"Theme: {profile.invite_theme}. ")
        elif getattr(profile, "invite_style", None):
            parts.append(f"Style: {profile.invite_style}. ")
        if getattr(profile, "invite_background_scene", None):
            parts.append(f"Background scene: {profile.invite_background_scene}. ")
        # Palette
        if getattr(profile, "invite_palette", None):
            parts.append(f"Colors: {', '.join(profile.invite_palette)}. ")
        elif getattr(profile, "invite_colors", None):
            parts.append(f"Colors: {', '.join(profile.invite_colors)}. ")
        # Mood + adornments
        if getattr(profile, "invite_mood", None):
            parts.append(f"Mood: {profile.invite_mood}. ")
        if getattr(profile, "invite_floral_style", None):
            parts.append(f"Floral elements: {profile.invite_floral_style}. ")
        if getattr(profile, "invite_frame_style", None):
            parts.append(f"Framing: {profile.invite_frame_style}. ")
        if getattr(profile, "invite_layout_type", None):
            parts.append(f"Layout type: {profile.invite_layout_type}. ")
        if getattr(profile, "invite_vibe", None):
            parts.append(f"Format/vibe: {profile.invite_vibe}. ")
    except Exception:
        pass
    if typography:
        parts.append(f"Typography direction (for spacing reference only): {typography}. ")
    if motifs:
        parts.append(f"Motifs: {motifs}. ")
    if palette_names or palette_hex:
        parts.append(f"Palette: {palette_names} ({palette_hex}). ")
    if dest_story:
        parts.append(f"Destination cues: {dest_story}. ")
    parts.append(
        "Premium paper texture and subtle finishing; polished editorial render; ONE final background only."
    )
    return "".join(parts)
    bride = (profile.bride_name or "").strip()
    groom = (profile.groom_name or "").strip()
    couple = f"{bride} & {groom}"
    destination = (profile.destination or "").strip()
    dates = ", ".join([d for d in (profile.wedding_dates or []) if d])

    invitation_text = ""
    theme = ""
    if creative_plan is not None:
        invitation_text = (getattr(creative_plan, "invitation_text", "") or "").strip()
        theme = (getattr(creative_plan, "theme_name", "") or "").strip()

    if not design_spec:
        base_dir = (getattr(creative_plan, "invite_design_prompt", "") or "").strip()
        parts = [
            f"Design ONE final vertical invitation card for {couple}. ",
            "Single full-frame card only — no 3-up mockup, no side-by-side options, no stationery board. ",
            f"Include destination and dates: {destination}; {dates}. ",
        ]
        if invitation_text:
            parts.append(f"Use this invitation text as body copy: {invitation_text}. ")
        if theme:
            parts.append(f"Theme: {theme}. ")
        if base_dir:
            parts.append(f"Direction: {base_dir}. ")
        # Minimal additive: include user preferences when present
        try:
            if getattr(profile, "invite_style", None):
                parts.append(f"Style preference: {profile.invite_style}. ")
            if getattr(profile, "invite_colors", None):
                parts.append(f"Preferred colors: {', '.join(profile.invite_colors)}. ")
            if getattr(profile, "invite_vibe", None):
                parts.append(f"Vibe/format: {profile.invite_vibe}. ")
            if getattr(profile, "include_venue_details", None) is True:
                parts.append("Include concise venue/hotel details. ")
            if getattr(profile, "include_rsvp", None) is True:
                parts.append("Include RSVP text. ")
        except Exception:
            pass
        parts.append("Premium paper feel, refined typography, subtle illustration; polished final render.")
        return "".join(parts)

    mood = _safe_join(design_spec.mood_keywords)
    palette_names = _safe_join(design_spec.palette_names)
    palette_hex = _safe_join(design_spec.palette_hex)
    motifs = _safe_join(design_spec.motifs)

    parts = [
        f"Create ONE final vertically oriented wedding invitation for {couple}. ",
        "Show only the single finalized card — no multiple variations, no 3-up mockups, no stationery/brand boards. ",
        f"Destination: {destination}. Dates: {dates}. ",
    ]
    if theme:
        parts.append(f"Theme: {theme}. ")
    parts.extend([
        f"Use invitation body text from state (verbatim where present): {invitation_text}. ",
        f"Composition: strong hierarchy (names > details > RSVP), centered layout. ",
        f"Typography: {design_spec.typography_direction}. ",
        f"Motifs: {motifs}. ",
        f"Visual style: {design_spec.visual_style_name}; mood: {mood}; palette: {palette_names} ({palette_hex}). ",
        f"Destination cues: {design_spec.destination_story}. ",
        "Premium paper texture and subtle finishing; polished editorial render; ONE final card only.",
    ])
    return "".join(parts)


def build_wardrobe_event_prompts(
    profile: WeddingProfile,
    logistics_plan: LogisticsPlan | None,
    design_spec: DesignDirectionSpec | None,
) -> List[Dict[str, Any]]:
    """Return one wardrobe/style prompt object per event in the schedule.

    Each object:
    - event_name
    - event_date
    - style_direction
    - guest_looks_prompt
    - couple_looks_prompt
    - palette_for_event
    """
    events = []
    schedule = []
    if logistics_plan and getattr(logistics_plan, "event_schedule", None):
        schedule = list(logistics_plan.event_schedule or [])

    for e in schedule:
        name = (e.get("event") or e.get("name") or "Event").strip()
        date = (e.get("date") or "").strip()

        if not design_spec:
            events.append(
                {
                    "event_name": name,
                    "event_date": date,
                    "style_direction": "Polished, destination-appropriate formalwear with cohesive palette.",
                    "guest_looks_prompt": "Guests in coordinated jewel tones or soft neutrals; breathable fabrics; tasteful accessories.",
                    "couple_looks_prompt": "Bride and groom in complementary palettes; elevated silhouettes; subtle metallic accents.",
                    "palette_for_event": ["ivory", "sage", "gold"],
                }
            )
            continue

        mood = _safe_join(design_spec.mood_keywords)
        palette_names = _safe_join(design_spec.palette_names)
        palette_hex = ", ".join(design_spec.palette_hex or [])

        style_direction = (
            f"{design_spec.wardrobe_art_direction} | Mood: {mood} | Luxury: {design_spec.luxury_level}. "
            f"Destination cues: {design_spec.destination_story}."
        )

        # Light tailoring per common events; still grounded in the spec
        event_lower = name.lower()
        if "sangeet" in event_lower or "welcome" in event_lower:
            guest_prompt = (
                f"Guests: expressive, colorful looks inspired by {palette_names}; breathable fabrics; mirrorwork/embroidery nods; "
                f"polished yet festive; coordinated accents from {palette_hex}."
            )
            couple_prompt = (
                "Couple: fashion-forward silhouettes; bride in jewel-toned lehenga or gown with refined embellishment; "
                "groom in tailored kurta/bandhgala with subtle metallic detailing; cohesive with palette."
            )
        elif "ceremony" in event_lower or "wedding" in event_lower:
            guest_prompt = (
                f"Guests: elevated day-formal; ivory/sand core with antique-gold accents; minimal prints; cohesive accessories; {palette_names}."
            )
            couple_prompt = (
                "Couple: classic ceremony silhouettes; bride in ivory/sand with intricate zari or lace; "
                "groom in complementary sherwani/suit with understated metallic details; heirloom elegance."
            )
        elif "reception" in event_lower:
            guest_prompt = (
                f"Guests: sleek eveningwear with modern sheen; midnight/navy base with metallic highlights; {palette_names}."
            )
            couple_prompt = (
                "Couple: bride in sleek gown with couture finish; groom in tailored tux/bandhgala; high-shine yet tasteful accessories."
            )
        else:
            guest_prompt = (
                f"Guests: coordinated looks reflecting {palette_names}; tasteful patterns; breathable luxury fabrics; polished accessories."
            )
            couple_prompt = (
                "Couple: complementary statement looks; refined embellishments; premium tailoring; cohesive with event palette."
            )

        events.append(
            {
                "event_name": name,
                "event_date": date,
                "style_direction": style_direction,
                "guest_looks_prompt": guest_prompt,
                "couple_looks_prompt": couple_prompt,
                "palette_for_event": design_spec.palette_hex,
            }
        )

    return events
def build_video_prompt(
    profile: WeddingProfile,
    logistics_plan: LogisticsPlan | None,
    design_spec: DesignDirectionSpec | None,
) -> str:
    """Build a stronger Veo prompt for a cinematic wedding teaser with explicit native audio."""
    bride = (profile.bride_name or "").strip()
    groom = (profile.groom_name or "").strip()
    couple = f"{bride} & {groom}"
    destination = (getattr(profile, "wedding_place", None) or profile.destination or "Destination").strip()
    wedding_dates = ", ".join([d for d in (profile.wedding_dates or []) if d])
    selected_hotel = (getattr(profile, "selected_hotel", None) or "").strip()

    # STRICT grounded builder: construct the full prompt now and return
    # Only uses current session data (profile/logistics/design_spec); no legacy/template content
    ceremony_lines: list[str] = []
    key_moments_strict = ""
    try:
        ceremonies = list(getattr(profile, "ceremonies", []) or [])
        cer_for_teaser = [c for c in ceremonies if getattr(c, "include_in_teaser", True)]
        if cer_for_teaser:
            parts_tmp: list[str] = []
            for c in cer_for_teaser:
                name = getattr(c, "name", "")
                date = getattr(c, "event_date", "")
                time = getattr(c, "time_of_day", "")
                mood_c = getattr(c, "mood", "")
                colors = ", ".join(getattr(c, "palette", []) or [])
                dress = getattr(c, "dress_code", "")
                bit = f"{name} ({date} {time}; mood: {mood_c}; colors: {colors}; dress: {dress})".strip()
                parts_tmp.append(bit)
                ceremony_lines.append(
                    f"- {name}  {date} {time}  mood {mood_c}  palette {colors}  dress code {dress}"
                )
            key_moments_strict = ", ".join([p for p in parts_tmp if p])
    except Exception:
        key_moments_strict = ""

    if not key_moments_strict and logistics_plan and getattr(logistics_plan, "event_schedule", None):
        try:
            events = [
                str((e.get("event") or e.get("name") or "").strip())
                for e in (logistics_plan.event_schedule or [])
            ]
            key_moments_strict = ", ".join([e for e in events if e])
        except Exception:
            key_moments_strict = ""

    # Teaser preference mappings (additive)
    style_map = {
        "royal": "royal, heritage grandeur, polished, stately, premium",
        "elegant": "elegant, refined, graceful, premium, timeless",
        "cinematic": "cinematic, filmic, premium, artfully composed",
        "editorial": "editorial, fashion-forward, premium, magazine-like",
        "modern subtle": "modern, subtle, understated, premium",
        "traditional luxe": "traditional, luxurious, ornate yet tasteful, premium",
    }
    pacing_map = {
        "slow dreamy": "slow, dreamy pacing with long graceful shots",
        "balanced": "balanced pacing with measured rhythm",
        "energetic": "controlled energetic pacing without feeling flashy",
    }
    music_map = {
        "orchestral": "orchestral strings and piano, regal undertones",
        "soft instrumental": "soft instrumental with piano and light strings",
        "celebratory": "uplifting celebratory cue with elegant percussion",
        "regal": "regal orchestration with noble timbre, subtle percussion",
    }
    feel_map = {
        "palace-luxury": "palace-luxury, royal architecture, opulent textures, warm gold accents",
        "intimate-romantic": "intimate-romantic, close candid moments, gentle light, soft focus",
        "fashion-forward": "fashion-forward, editorial styling, dramatic silhouettes, refined poses",
    }
    pref_style = (getattr(profile, "teaser_style", "") or "").strip().lower()
    pref_pacing = (getattr(profile, "teaser_pacing", "") or "").strip().lower()
    pref_music = (getattr(profile, "teaser_music_vibe", "") or "").strip().lower()
    pref_feel = (getattr(profile, "teaser_feel", "") or "").strip().lower()
    names_timing = (getattr(profile, "teaser_names_timing", "") or "").strip().lower()
    ending_style = (getattr(profile, "teaser_ending_text_style", "") or "").strip().lower()
    must_show = (getattr(profile, "teaser_must_show", "") or "").strip()

    base_style_words = (
        "premium, royal, elegant, subtle, cinematic; destination wedding luxury film aesthetic; not flashy; not cheap;"
    )
    if pref_style in style_map:
        base_style_words = style_map[pref_style]

    if design_spec is None:
        parts = [
            f"Create a 20–30 second cinematic luxury wedding teaser for {couple} in {destination}. ",
            f"Wedding dates: {wedding_dates}. ",
        ]
        if selected_hotel:
            parts.append(f"Selected hotel/venue: {selected_hotel}. ")
        parts.extend([
            f"Style direction: {base_style_words} ",
            "Visual language: golden-hour light, refined compositions, shallow depth of field, smooth camera moves, intimate macro details. ",
            (pacing_map.get(pref_pacing, "") + ". ") if pacing_map.get(pref_pacing) else "",
            (feel_map.get(pref_feel, "") + ". ") if feel_map.get(pref_feel) else "",
            "Narrative: open with destination establishing, move into authentic couple moments, ceremony highlights, refined celebration energy, close with poetic sunset. ",
        ])
        if ceremony_lines:
            parts.append("Ceremony sequence (use exactly these in order; include visual progression; do not omit any): ")
            parts.append("\n" + "\n".join(ceremony_lines) + "\n")
        else:
            base_key = key_moments_strict
            if must_show:
                base_key = (base_key + "; must-show: " + must_show).strip("; ")
            parts.append(f"Key moments: {base_key}. ")
        parts.extend([
            "AUDIO IS REQUIRED: generate native audio. Video must not be silent. ",
            "Soundtrack: warm romantic ballad feel, gentle piano/strings, elegant cinematic pacing; professionally mixed. ",
            "Music vibe: " + music_map.get(pref_music, "soft instrumental with piano and strings") + ". ",
            "Ambient layers: destination-appropriate natural sounds only. ",
            "Names/dates placement: " + ("end-only" if names_timing.startswith("end") else "allow tasteful identifiers earlier but prefer end emphasis") + ". ",
            "Deliver one polished premium teaser only (no multiple versions).",
        ])
        return "".join(parts)

    # With design_spec: include spec-driven identity while keeping premium constraints explicit
    mood = _safe_join(design_spec.mood_keywords)
    palette_names = _safe_join(design_spec.palette_names)
    motifs = _safe_join(design_spec.motifs)
    parts = [
        f"Create a 20–30 second cinematic luxury wedding teaser for {couple} in {destination}. ",
        f"Wedding dates: {wedding_dates}. ",
    ]
    if selected_hotel:
        parts.append(f"Selected hotel/venue: {selected_hotel}. ")
    parts.extend([
        f"Visual identity: {design_spec.visual_style_name}. ",
        f"Luxury level: {design_spec.luxury_level}. ",
        f"Mood: {mood}. ",
        f"Palette: {palette_names}. ",
        f"Motifs: {motifs}. ",
        f"Creative direction: {design_spec.video_art_direction}. ",
        f"Destination story: {design_spec.destination_story}. ",
        f"Style direction: {base_style_words} ",
        "Cinematic language: golden-hour light, refined color, soft highlights, shallow depth-of-field, intimate macros, elegant wides. ",
        "Narrative: destination establishing → authentic couple → ceremony highlights → refined celebration → poetic sunset close. ",
    ])
    # Teaser preferences: pacing and feel (design-spec path)
    if pacing_map.get(pref_pacing):
        parts.append(pacing_map[pref_pacing] + ". ")
    if feel_map.get(pref_feel):
        parts.append(feel_map[pref_feel] + ". ")
    if ceremony_lines:
        parts.append("Ceremony sequence (use exactly these in order; include visual progression; do not omit any): ")
        parts.append("\n" + "\n".join(ceremony_lines) + "\n")
    else:
        parts.append(f"Key moments: {key_moments_strict}. ")
    parts.extend([
        "AUDIO IS MANDATORY: generate native audio (no silent clip). ",
        "Soundtrack: warm, modern romantic; subtle, premium; professionally mixed. ",
        "Ambient layers: destination-appropriate natural sounds only. ",
        "Output one polished premium wedding teaser only.",
    ])
    # Teaser preferences: music vibe and names placement (design-spec path)
    parts.append("Music vibe: " + music_map.get(pref_music, "soft instrumental with piano and strings") + ". ")
    parts.append(
        "Names/dates placement: "
        + ("end-only" if names_timing.startswith("end") else "allow tasteful identifiers earlier but prefer end emphasis")
        + ". "
    )
    return "".join(parts)

    # Prefer explicit ceremony plan from profile when available
    key_moments = ""
    try:
        ceremonies = list(getattr(profile, "ceremonies", []) or [])
        cer_for_teaser = [c for c in ceremonies if getattr(c, "include_in_teaser", True)]
        if cer_for_teaser:
            seq_parts: list[str] = []
            for c in cer_for_teaser:
                name = getattr(c, "name", "")
                date = getattr(c, "event_date", "")
                time = getattr(c, "time_of_day", "")
                mood_c = getattr(c, "mood", "")
                colors = ", ".join(getattr(c, "palette", []) or [])
                bit = f"{name} ({date} {time}; mood: {mood_c}; colors: {colors})".strip()
                seq_parts.append(bit)
            key_moments = ", ".join([p for p in seq_parts if p])
    except Exception:
        key_moments = ""

    # Fallback to logistics events when no ceremony plan
    if not key_moments:
        events = []
        if logistics_plan and getattr(logistics_plan, "event_schedule", None):
            events = [
                str((e.get("event") or e.get("name") or "").strip())
                for e in (logistics_plan.event_schedule or [])
            ]
        key_moments = ", ".join([e for e in events if e])

    if not design_spec:
        return (
            f"Create a 20–30 second cinematic luxury wedding teaser film for {couple} set in {destination}. "
            f"Wedding dates: {wedding_dates}. "
            "Visual style: golden-hour coastal aesthetic, soft sunlight, ocean breeze, palm silhouettes, warm tropical tones, "
            "high-end editorial wedding film, smooth camera movement, shallow depth of field, elegant slow motion, and refined compositions. "
            "Narrative flow: begin with scenic coastline establishing shots, transition into intimate couple moments, then wedding ceremony details, "
            "celebration energy, and end with a sunset silhouette closing shot. "
            f"Highlight these moments: {key_moments}. "
            "AUDIO IS REQUIRED: generate native audio in the final video. The video must not be silent. "
            "Use a continuous romantic wedding soundtrack throughout the clip: warm, vintage-inspired, soft instrumental ballad feel, "
            "gentle piano and strings, subtle emotional rise, elegant cinematic pacing. "
            "Also include realistic ambient sound design: soft ocean waves, light coastal breeze, distant laughter, subtle celebration atmosphere, "
            "and delicate clinking glasses in reception moments. "
            "Audio must be present from beginning to end, professionally mixed, emotionally uplifting, and never overpower the visuals. "
            "Mood: romantic, intimate, joyful, timeless, elegant, emotionally resonant. "
            "Output one polished premium wedding teaser suitable for a luxury wedding announcement."
        )

    mood = _safe_join(design_spec.mood_keywords)
    palette_names = _safe_join(design_spec.palette_names)
    motifs = _safe_join(design_spec.motifs)

    return (
        f"Create a 20–30 second cinematic luxury wedding teaser film for {couple} in {destination}, India. "
        f"Wedding dates: {wedding_dates}. "
        f"Visual identity: {design_spec.visual_style_name}. "
        f"Luxury level: {design_spec.luxury_level}. "
        f"Mood: {mood}. "
        f"Palette: {palette_names}. "
        f"Motifs: {motifs}. "
        f"Creative direction: {design_spec.video_art_direction}. "
        f"Destination story: {design_spec.destination_story}. "
        "Use a high-end editorial wedding-film style with golden-hour light, cinematic color grading, soft highlights, refined tropical atmosphere, "
        "slow motion, intimate close-ups, elegant wide establishing shots, and emotionally expressive storytelling. "
        "Narrative structure: "
        "1) opening with serene Goan coastline and warm ocean light, "
        "2) intimate candid couple moments, "
        "3) detailed ceremony styling and emotional expressions, "
        "4) elevated reception celebration energy, "
        "5) ending with a poetic sunset closing shot of the couple. "
        f"Feature these wedding moments: {key_moments}. "
        "AUDIO IS MANDATORY: generate native audio in the final video. DO NOT return a silent clip. "
        "Include a continuous romantic wedding soundtrack across the full teaser with a warm, vintage-inspired soft ballad feel, "
        "gentle piano and strings, soft emotional build, elegant cinematic pacing, and a polished premium mix. "
        "Also include natural ambient sound layers appropriate to the visuals: soft ocean waves, coastal breeze, distant guest laughter, "
        "light celebration ambience, and subtle reception details. "
        "Audio should remain present from beginning to end, synchronized with the visual pacing, emotionally uplifting, cinematic, and professionally mixed. "
        "Optional minimal title card only at the end: "
        "End with a minimal closing title card: first line shows the couple names exactly as '" + couple + "', "
        "second line shows the wedding date(s) exactly as '" + wedding_dates + "'. "
        f"'{couple}' and '{destination} • {wedding_dates}'. "
        "Do not make the teaser feel generic, stock, or overly commercial. "
        "It should feel bespoke, luxurious, emotionally rich, and authentically destination-wedding focused. "
        "Output one polished premium wedding teaser with synchronized visuals and native background audio."
    )


def build_moodboard_prompt(
    profile: WeddingProfile,
    creative_plan: CreativePlan | None,
    design_spec: DesignDirectionSpec | None,
    logistics_plan: LogisticsPlan | None,
    event_name: str,
) -> str:
    """Build a single, vertically composed fashion moodboard prompt for an event.

    Requirements to enforce:
    - one fashion moodboard page
    - editorial wedding styling collage
    - guest looks and couple looks
    - accessories / shoes / jewelry
    - palette-coordinated visuals
    - premium magazine-like styling
    - no plain text poster
    - no generic catalog grid
    """
    bride = (profile.bride_name or "").strip()
    groom = (profile.groom_name or "").strip()
    couple = f"{bride} & {groom}".strip()
    destination = (profile.destination or "").strip()
    dates = ", ".join([d for d in (profile.wedding_dates or []) if d])

    theme = (getattr(creative_plan, "theme_name", "") or "").strip() if creative_plan is not None else ""
    mood = _safe_join(getattr(design_spec, "mood_keywords", []) if design_spec is not None else [])
    palette_names = _safe_join(getattr(design_spec, "palette_names", []) if design_spec is not None else [])
    palette_hex = _safe_join(getattr(design_spec, "palette_hex", []) if design_spec is not None else [])
    wardrobe = (getattr(design_spec, "wardrobe_art_direction", "") or "").strip() if design_spec is not None else ""
    dest_story = (getattr(design_spec, "destination_story", "") or "").strip() if design_spec is not None else ""

    parts = [
        f"Create ONE vertically composed fashion moodboard page for '{event_name}'. ",
        f"Couple: {couple}. Destination: {destination}. Dates: {dates}. ",
    ]
    if theme:
        parts.append(f"Theme: {theme}. ")
    if wardrobe:
        parts.append(f"Wardrobe direction: {wardrobe}. ")
    if mood:
        parts.append(f"Mood: {mood}. ")
    if palette_names or palette_hex:
        parts.append(f"Palette: {palette_names} ({palette_hex}). ")
    if dest_story:
        parts.append(f"Destination cues: {dest_story}. ")

    parts.extend([
        "Editorial wedding styling collage with premium magazine-like art direction. ",
        "Show guest looks and couple looks, include accessories/shoes/jewelry, palette-coordinated visuals. ",
        "Avoid plain text posters, avoid generic catalog grids, avoid multiple separate pages. ",
        "Deliver one cohesive vertical moodboard image with refined composition.",
    ])
    return "".join(parts)
