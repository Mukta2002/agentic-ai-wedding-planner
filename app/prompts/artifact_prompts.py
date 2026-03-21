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
        if palette:
            parts.append(f"Use palette: {palette}. ")
        parts.append("Finish suggestion: subtle foil/deboss look, not overdone.")
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
    return "".join(parts)


def build_invite_prompt(
    profile: WeddingProfile,
    creative_plan: CreativePlan | None,
    design_spec: DesignDirectionSpec | None,
) -> str:
    """Build a premium single-invite prompt grounded in shared state only.

    Requirements:
    - Exactly ONE final vertically oriented invitation card (no 3-up, no options).
    - Use couple names, destination, dates, invitation text, theme/palette/motifs from state.
    - Premium, polished, editorial finish.
    """
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
    destination = (profile.destination or "Destination").strip()
    wedding_dates = ", ".join([d for d in (profile.wedding_dates or []) if d])

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
