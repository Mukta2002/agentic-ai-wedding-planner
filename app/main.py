from __future__ import annotations

import json
import os
import sys
import logging
from typing import Any, Dict, List
from datetime import datetime

# Ensure .env gets loaded centrally via config on import
from app.config import get_gemini_api_key  # noqa: F401 (import for side-effect & helper)

# Safe sys.path fix when run as: python app/main.py
if __package__ in (None, ""):
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.model_router import ModelRouter
from app.services.styleguide_pdf_v2 import build_style_guide_pdf
from app.services.storage import Storage
from app.models.schemas import WeddingState, MediaArtifacts
from app.prompts.artifact_prompts import (
    build_logo_prompt,
    build_invite_prompt,
    build_video_prompt,
    build_teaser_prompt_struct,
)
from app.services.teaser_ending_card import render_teaser_ending_card, append_ending_card_to_video
from app.services.maps_hotel_service import MapsHotelService


_INVITE_COPY_LOGGED = False
_RENDER_PAYLOAD_LOGGED = False


def _init_logging() -> None:
    """Configure logging to keep terminal output clean by default.

    - App-level: INFO
    - Third-party libraries (httpx/httpcore/PIL/etc.): WARNING
    - Enable DEBUG only when WEDDING_DEBUG=1/true/yes
    """
    debug_env = os.environ.get("WEDDING_DEBUG", "").strip().lower() in ("1", "true", "yes")
    level = logging.DEBUG if debug_env else logging.INFO

    # Configure root logger minimally; avoid duplicate handlers
    root = logging.getLogger()
    root.setLevel(level)
    if not root.handlers:
        h = logging.StreamHandler()
        fmt = logging.Formatter("[%(levelname)s] %(message)s")
        h.setFormatter(fmt)
        root.addHandler(h)

    # Suppress noisy third-party loggers unless debug mode
    noisy = [
        "httpx",
        "httpcore",
        "PIL",
        "PIL.Image",
        "PIL.PngImagePlugin",
        "urllib3",
        "google",
    ]
    for name in noisy:
        try:
            logging.getLogger(name).setLevel(logging.WARNING if not debug_env else logging.DEBUG)
            logging.getLogger(name).propagate = False
        except Exception:
            pass

def _get_state() -> WeddingState | Any:
    """Return a structured WeddingState from memory or from data/state.json.

    - If the orchestrator placed a state module in memory (app.state), use it.
    - Otherwise, load and validate the JSON at data/state.json via Storage.
    """
    # Prefer in-memory state if orchestrator already populated it
    try:
        from app import state as app_state  # type: ignore
        return app_state
    except Exception:
        pass

    # Fallback: load from disk
    try:
        storage = Storage()
        loaded = storage.load_state()
        if loaded is not None:
            return loaded
    except Exception:
        pass

    # As a last resort, raise to avoid using weak fallback dicts for media
    raise RuntimeError(
        "No structured WeddingState available. Ensure orchestrator saved data/state.json."
    )


def _has_styleguide_state(state: WeddingState | Any) -> bool:
    try:
        logistics = getattr(state, "logistics", None)
        schedule = getattr(logistics, "event_schedule", None) if logistics is not None else None
        return isinstance(schedule, list) and len(schedule) > 0
    except Exception:
        return False


# Legacy shim: no longer used for population; styleguide pulls from state directly.
def _read_style_events_from_state(state: WeddingState | Any) -> List[Dict[str, Any]]:
    return []


def main() -> None:
    global _INVITE_COPY_LOGGED
    global _RENDER_PAYLOAD_LOGGED
    # Initialize clean logging first
    _init_logging()
    # Stage 1: Interactive intake flow (default). To run full generation, set
    # env var WEDDING_RUN_GENERATION=1
    run_generation = os.environ.get("WEDDING_RUN_GENERATION", "").lower() in ("1", "true", "yes")
    if not run_generation:
        from app.services.intake_manager import IntakeManager

        intake = IntakeManager()
        profile = intake.collect_basic_details()

        # Neat summary
        print("\n===== Wedding Profile Summary =====")
        print(f"Bride:           {profile.bride_name}")
        print(f"Groom:           {profile.groom_name}")
        print(f"Place:           {getattr(profile, 'wedding_place', None) or profile.destination}")
        print(f"Dates:           {', '.join(profile.wedding_dates)}")
        print(f"Guests:          {profile.guest_count}")
        print(f"Budget:          {profile.budget} {getattr(profile, 'currency', 'INR')}")
        print("==================================\n")

        # Budget breakdown confirmation before hotel recommendations
        try:
            from app.services.budget_planner import confirm_and_apply_breakdown
            confirm_and_apply_breakdown(profile)
        except Exception as e:
            # Non-blocking: if planner fails, proceed with existing flow
            print(f"Budget breakdown step skipped due to an error: {e}")

        # Maps-grounded hotel recommendations via Gemini
        try:
            maps_service = MapsHotelService()
            maps_rec = maps_service.recommend_hotels(profile, top_n=5)

            maps_hotels = maps_rec.get("recommendations", [])
            maps_msg = maps_rec.get("message")

            # Context for hotel/accommodation budget being used
            try:
                total_budget = getattr(profile, 'wedding_budget', None)
                if total_budget is None:
                    total_budget = getattr(profile, 'budget', 0.0)
                currency = getattr(profile, 'currency', 'INR') or 'INR'
                share = getattr(profile, 'accommodation_budget_share', None)
                try:
                    share_pct = float(share) * 100.0 if share is not None else None
                except Exception:
                    share_pct = None
                accom_cap = None
                if share_pct is not None:
                    accom_cap = float(total_budget) * (share_pct / 100.0)
                print("===== Budget-fit Hotel Recommendations (Gemini) =====")
                # Print concise context header
                if share_pct is not None and accom_cap is not None:
                    try:
                        print(
                            f"Context: Total budget {currency} {int(total_budget):,} | "
                            f"Hotel/Accommodation share {int(share_pct) if share_pct.is_integer() else round(share_pct,1)}% | "
                            f"Cap used {currency} {int(accom_cap):,}"
                        )
                    except Exception:
                        print(
                            f"Context: Total budget {currency} {total_budget} | Hotel/Accommodation share {share_pct}%"
                        )
                else:
                    # Fallback if share missing
                    print(f"Context: Total budget {currency} {int(total_budget):,}")
            except Exception:
                print("===== Budget-fit Hotel Recommendations (Gemini) =====")
            if maps_msg and not maps_hotels:
                # Preserve current message
                print(maps_msg)
                # New: interactive follow-up instead of stopping
                print("No hotels fit the current estimated accommodation budget. What would you like to do?")
                print("  1. Search for more budget-conscious hotels")
                print("  2. Increase hotel budget share")
                print("  3. Reduce guest count")
                print("  4. Reduce number of nights")
                print("  5. Skip hotel selection for now")
                choice = input("> ").strip()

                performed_retry = False
                if choice == "1":
                    # Bias prompt toward budget-conscious/mid-range/value-for-money
                    try:
                        setattr(profile, "prefer_budget_hotels", True)
                    except Exception:
                        pass
                    performed_retry = True
                elif choice == "2":
                    try:
                        pct_str = input("Enter new hotel budget share percentage (e.g., 35, 40, 50): ").strip()
                        pct = float(pct_str)
                        if pct > 0 and pct < 100:
                            setattr(profile, "accommodation_budget_share", pct / 100.0)
                            performed_retry = True
                        else:
                            print("Invalid percentage. Keeping previous share.")
                    except Exception:
                        print("Invalid input. Keeping previous share.")
                elif choice == "3":
                    try:
                        gc_str = input("Enter revised guest count: ").strip()
                        gc = int(gc_str)
                        if gc > 0:
                            setattr(profile, "revised_guest_count", gc)
                            performed_retry = True
                        else:
                            print("Invalid guest count. Keeping previous value.")
                    except Exception:
                        print("Invalid input. Keeping previous value.")
                elif choice == "4":
                    try:
                        nights_str = input("Enter revised number of nights: ").strip()
                        nn = int(nights_str)
                        if nn > 0:
                            setattr(profile, "selected_nights_override", nn)
                            performed_retry = True
                        else:
                            print("Invalid nights value. Keeping previous estimate.")
                    except Exception:
                        print("Invalid input. Keeping previous estimate.")
                elif choice == "5":
                    print("Skipping hotel selection for now.")
                    print("==================================\n")
                    return
                else:
                    print("Unrecognized choice. Continuing without hotel selection.")
                    print("==================================\n")
                    return

                if performed_retry:
                    # Re-run the Maps-grounded recommendation with updated profile
                    maps_rec = maps_service.recommend_hotels(profile, top_n=5)
                    maps_hotels = maps_rec.get("recommendations", [])
                    maps_msg = maps_rec.get("message")
                    if not maps_hotels:
                        # Show the standard guidance and end the section
                        if maps_msg:
                            print(maps_msg)
                        else:
                            print("No Gemini hotel recommendations fit the current estimated accommodation budget.")
                        print("Try increasing budget, reducing guest count, shortening stay, or asking for more budget-conscious hotels.")
                        print("==================================\n")
                        return

            if maps_hotels:
                # Ensure sorted by estimated total cost ascending
                def _cost(h: dict) -> float:
                    try:
                        return float(h.get("estimated_total_cost") or 0.0)
                    except Exception:
                        return 0.0

                maps_hotels = sorted(maps_hotels, key=_cost)

                for idx, h in enumerate(maps_hotels, start=1):
                    name = h.get("name") or "Not available from Gemini response"
                    loc = h.get("location") or "Not available from Gemini response"
                    reason = h.get("reason") or "Not available from Gemini response"
                    pricing = h.get("pricing_hints") or "Not available from Gemini response"
                    suit = h.get("wedding_suitability") or "Not available from Gemini response"
                    nearby = h.get("nearby_context") or "Not available from Gemini response"

                    # Budget-aware fields (safe defaults)
                    currency = h.get("currency") or getattr(profile, 'currency', 'INR') or "INR"
                    est_rate = h.get("estimated_room_rate")
                    est_total = h.get("estimated_total_cost")
                    rooms = h.get("rooms_needed")
                    nights = h.get("nights")

                    print(f"{idx}. {name} - {loc}")
                    print(f"   Why it fits: {reason}")
                    print(f"   Wedding suitability: {suit}")
                    print(f"   Pricing hints: {pricing}")
                    if isinstance(est_rate, (int, float)):
                        print(f"   Estimated room rate: {currency} {int(est_rate):,} per night")
                    else:
                        print("   Estimated room rate: Not available from Gemini response")
                    if isinstance(est_total, (int, float)):
                        detail = ""
                        if isinstance(rooms, int) and isinstance(nights, int) and rooms and nights:
                            detail = f" ({rooms} rooms x {nights} nights)"
                        print(f"   Estimated total cost: {currency} {int(est_total):,}{detail}")
                    else:
                        print("   Estimated total cost: Not available from Gemini response")
            else:
                # If no budget-fit hotels and no explicit message, show concise fallback
                if maps_msg:
                    print(maps_msg)
                else:
                    print("No Gemini hotel recommendations fit the current estimated accommodation budget.")
                print("Try increasing budget, reducing guest count, shortening stay, or asking for more budget-conscious hotels.")
            print("==================================\n")
            # After hotel recommendations, collect creative prefs and generate assets
            try:
                # Optionally allow user to select a hotel to anchor context
                selected_context = None
                if maps_hotels:
                    sel = input("Optionally pick a hotel number to anchor designs (Enter to skip): ").strip()
                    try:
                        if sel:
                            si = int(sel)
                            if 1 <= si <= len(maps_hotels):
                                chosen = maps_hotels[si - 1]
                                name = chosen.get("name") or ""
                                loc = chosen.get("location") or ""
                                selected_context = f"{name} - {loc}".strip(" -")
                                # Persist selected hotel on profile for grounded text overlay
                                try:
                                    setattr(profile, "selected_hotel", name)
                                except Exception:
                                    pass
                    except Exception:
                        pass

                # Ask logo and invite preferences (visual only). Skip wording prompts for copy.
                # Important: Do NOT ask teaser questions yet. We will ask them only AFTER
                # the invite has been fully generated and saved.
                intake.collect_logo_preferences(profile)
                intake.collect_invite_preferences(profile)
                # Intentionally bypass invite wording questions; Gemini will compose copy.

                # Creative preferences summary
                print("\n===== Creative Preferences Summary =====")
                if selected_context:
                    print(f"Hotel context: {selected_context}")
                else:
                    # Fall back to top recommendation when available
                    if maps_hotels:
                        top = maps_hotels[0]
                        print(f"Hotel context: {top.get('name')} - {top.get('location')}")
                    else:
                        print("Hotel context: (none selected)")
                # Logo prefs
                print("Logo: ", end="")
                print(
                    ", ".join(
                        [
                            s
                            for s in [
                                f"style={getattr(profile, 'logo_style', None) or '-'}",
                                f"text={getattr(profile, 'logo_text_mode', None) or getattr(profile, 'logo_text_preference', None) or '-'}",
                                f"motif={getattr(profile, 'logo_motif', None) or '-'}",
                                f"palette={','.join(getattr(profile, 'logo_palette', []) or getattr(profile, 'logo_colors', []) or []) or '-'}",
                                f"mood={getattr(profile, 'logo_mood', None) or '-'}",
                            ]
                        ]
                    )
                )
                # Invite prefs
                print("Invite: ", end="")
                print(
                    ", ".join(
                        [
                            s
                            for s in [
                                f"theme={getattr(profile, 'invite_theme', None) or getattr(profile, 'invite_style', None) or '-'}",
                                f"scene={getattr(profile, 'invite_background_scene', None) or '-'}",
                                f"palette={','.join(getattr(profile, 'invite_palette', []) or getattr(profile, 'invite_colors', []) or []) or '-'}",
                                f"mood={getattr(profile, 'invite_mood', None) or '-'}",
                                f"floral={getattr(profile, 'invite_floral_style', None) or '-'}",
                                f"frame={getattr(profile, 'invite_frame_style', None) or '-'}",
                                f"layout={getattr(profile, 'invite_layout_type', None) or '-'}",
                                f"venue_details={'yes' if getattr(profile, 'include_venue_details', None) else 'no'}",
                                f"rsvp={'yes' if getattr(profile, 'include_rsvp', None) else 'no'}",
                            ]
                        ]
                    )
                )
                print("==================================\n")

                # Build confirmed structured creative payload
                from app.models.schemas import ConfirmedCreativePayload
                initials = (profile.bride_name[:1] + profile.groom_name[:1]).upper()
                # Optional compact ceremony summary for invite
                cer_summary = []
                try:
                    cers = list(getattr(profile, 'ceremonies', []) or [])
                    for c in cers:
                        name = getattr(c, 'name', '')
                        date = getattr(c, 'event_date', '')
                        tod = getattr(c, 'time_of_day', '')
                        mood = getattr(c, 'mood', '')
                        if name or date or tod:
                            cer_summary.append(f"{name}  {date} {tod}  {mood}".strip())
                except Exception:
                    cer_summary = []
                payload = ConfirmedCreativePayload(
                    bride_name=profile.bride_name,
                    groom_name=profile.groom_name,
                    initials=initials,
                    wedding_dates=list(profile.wedding_dates or []),
                    wedding_place=(getattr(profile, 'wedding_place', None) or profile.destination),
                    selected_hotel=getattr(profile, 'selected_hotel', None),
                    logo_style=getattr(profile, 'logo_style', None),
                    logo_colors=getattr(profile, 'logo_colors', None),
                    logo_text_preference=getattr(profile, 'logo_text_preference', None),
                    logo_motif=getattr(profile, 'logo_motif', None),
                    logo_text_mode=getattr(profile, 'logo_text_mode', None),
                    logo_palette=getattr(profile, 'logo_palette', None),
                    logo_mood=getattr(profile, 'logo_mood', None),
                    invite_style=getattr(profile, 'invite_style', None),
                    invite_colors=getattr(profile, 'invite_colors', None),
                    invite_vibe=getattr(profile, 'invite_vibe', None),
                    invite_theme=getattr(profile, 'invite_theme', None),
                    invite_background_scene=getattr(profile, 'invite_background_scene', None),
                    invite_palette=getattr(profile, 'invite_palette', None),
                    invite_mood=getattr(profile, 'invite_mood', None),
                    invite_floral_style=getattr(profile, 'invite_floral_style', None),
                    invite_frame_style=getattr(profile, 'invite_frame_style', None),
                    invite_layout_type=getattr(profile, 'invite_layout_type', None),
                    include_rsvp=getattr(profile, 'include_rsvp', None),
                    include_venue_details=getattr(profile, 'include_venue_details', None),
                    # Wording fields
                    invite_wording_style=getattr(profile, 'invite_wording_style', None),
                    invite_together_with_families=getattr(profile, 'invite_together_with_families', None),
                    invite_include_short_blessing=getattr(profile, 'invite_include_short_blessing', None),
                    invite_invitation_phrase=getattr(profile, 'invite_invitation_phrase', None),
                    invite_rsvp_sentence_style=getattr(profile, 'invite_rsvp_sentence_style', None),
                    ceremony_summary_lines=cer_summary or None,
                )

                # Build prompts directly from profile + preferences (no design_spec in intake mode)
                logo_prompt = build_logo_prompt(profile, None, None)
                invite_prompt = build_invite_prompt(profile, None, None)  # background-only

                router = ModelRouter()
                # Pre-generation grounded summary
                try:
                    cers = list(getattr(profile, 'ceremonies', []) or [])
                    teaser_inc = [c.name for c in cers if getattr(c, 'include_in_teaser', True)]
                    style_inc = [c.name for c in cers if getattr(c, 'include_in_style_guide', True)]
                    print("\n===== Generation Plan (Grounded) =====")
                    print(
                        "Logo prefs: "
                        + ", ".join(
                            [
                                f"style={getattr(profile, 'logo_style', None) or '-'}",
                                f"feel={getattr(profile, 'logo_feel', None) or '-'}",
                                f"text={getattr(profile, 'logo_text_mode', None) or getattr(profile, 'logo_text_preference', None) or '-'}",
                                f"motif={getattr(profile, 'logo_motif', None) or '-'}",
                                f"hidden={','.join(getattr(profile, 'logo_hidden_motifs', []) or []) or '-'}",
                            ]
                        )
                    )
                    print(
                        "Invite wording: "
                        + ", ".join(
                            [
                                f"style={getattr(profile, 'invite_wording_style', None) or '-'}",
                                f"families={'yes' if getattr(profile, 'invite_together_with_families', None) else 'no'}",
                                f"blessing={'yes' if getattr(profile, 'invite_include_short_blessing', None) else 'no'}",
                                f"phrase={getattr(profile, 'invite_invitation_phrase', None) or '-'}",
                                f"rsvp={getattr(profile, 'invite_rsvp_sentence_style', None) or '-'}",
                            ]
                        )
                    )
                    print(f"Style guide ceremonies: {', '.join(style_inc) if style_inc else '-'}")
                    print(f"Teaser ceremonies: {', '.join(teaser_inc) if teaser_inc else '-'}")
                    print("==================================\n")
                except Exception:
                    pass
                # Generate logo once (happens before teaser questions per required flow)
                logo_path, logo_meta = router.generate_logo_image(logo_prompt, state=None)

                # Invite: Step A background only, Step B overlay composed text
                from app.services.invite_text_overlay import render_invite_sections
                from app.services.invite_copy_service import generate_invitation_copy
                bg_out = os.path.join("assets", "invites", "invite_background.png")
                final_out = os.path.join("assets", "invites", "invite.png")

                # Debug visibility for invite background generation (interactive flow)
                try:
                    requested_venue = (
                        getattr(profile, 'selected_hotel', None)
                        or getattr(profile, 'wedding_place', None)
                        or getattr(profile, 'destination', None)
                        or '-'
                    )
                    requested_bg = getattr(profile, 'invite_background_scene', None)
                    # Exact-location request detection (best-effort keywords)
                    try:
                        scene_l = (requested_bg or "").lower()
                        exact_requested = any(k in scene_l for k in [
                            "atal", "bridge", "riverfront", "gateway of india", "taj mahal", "lake palace", "fort", "temple"
                        ])
                    except Exception:
                        exact_requested = False
                    if exact_requested:
                        bg_mode = 'venue_exact_unsupported'
                    elif getattr(profile, 'selected_hotel', None):
                        bg_mode = 'venue_inspired'
                    else:
                        bg_mode = 'generic_scene'
                    print("===== Invite Background Debug =====")
                    print(f"Requested venue: {requested_venue}")
                    print(f"Requested background: {requested_bg or '-'}")
                    print(f"Generation mode: {bg_mode}")
                    if exact_requested:
                        print("[Note] Exact location rendering is not supported in current pipeline; using scenic/inspired fallback.")
                    print("Final prompt (image generation):")
                    try:
                        import textwrap as _tw
                        for line in _tw.wrap(invite_prompt, width=120):
                            print(line)
                    except Exception:
                        print(invite_prompt)
                    print("===================================")
                except Exception:
                    pass

                _, bg_meta = router.generate_invite_image(invite_prompt, out_path=bg_out, state=None)

                # Post-generation verification (non-blocking)
                try:
                    ver = router.verify_invite_background(
                        image_path=bg_out,
                        venue_name=getattr(profile, 'selected_hotel', None),
                        place_name=(getattr(profile, 'wedding_place', None) or getattr(profile, 'destination', None)),
                    )
                    print("===== Invite Background Verification =====")
                    try:
                        import json as _json
                        print(_json.dumps({k: v for k, v in ver.items() if not str(k).startswith('_')}, indent=2))
                    except Exception:
                        print(ver)
                    if not bool(ver.get('is_match', False)):
                        print("[WARNING] Generated image does NOT match requested venue")
                        try:
                            if exact_requested:
                                print("[Info] Mismatch expected: exact-location rendering unsupported; generated scenic fallback.")
                        except Exception:
                            pass
                    print("===========================================")
                except Exception as _ver_e:
                    print(f"[Invite-Verify] skipped due to error: {_ver_e}")

                # Generate polished invitation copy via Gemini
                print("\n===== Generating Invite Copy (Gemini) =====")
                theme_hint = getattr(profile, 'invite_theme', None) or getattr(profile, 'invite_style', None)
                copy_sections = generate_invitation_copy(
                    profile,
                    theme_hint=theme_hint,
                    include_rsvp=getattr(profile, 'include_rsvp', None),
                    include_venue_details=getattr(profile, 'include_venue_details', None),
                    selected_hotel=getattr(profile, 'selected_hotel', None),
                )
                if not _INVITE_COPY_LOGGED:
                    print("===== Final Invite Copy (Gemini) =====")
                    try:
                        import json as _json
                        print(_json.dumps(copy_sections, indent=2, ensure_ascii=False))
                    except Exception:
                        print(copy_sections)
                    _INVITE_COPY_LOGGED = True
                print("[Confirm] Raw field labels not sent to renderer")

                # Render overlay with composed sections only
                invite_overlay = render_invite_sections(
                    background_path=bg_out,
                    sections_payload=copy_sections,
                    out_path=final_out,
                )
                # Single clean render payload print (post-render)
                if not _RENDER_PAYLOAD_LOGGED:
                    print("===== Render Payload (Clean) =====")
                    try:
                        import json as _json
                        print(_json.dumps(invite_overlay.get("render"), indent=2, ensure_ascii=False))
                    except Exception:
                        try:
                            print(invite_overlay.get("render"))
                        except Exception:
                            pass
                    _RENDER_PAYLOAD_LOGGED = True
                invite_path = final_out if invite_overlay.get("ok") else None
                invite_meta = {
                    "file": {"path": final_out, "exists": bool(invite_path and os.path.exists(final_out)), "size": invite_overlay.get("size", 0)},
                    "overlay": invite_overlay,
                    "background": bg_meta,
                }

                # Clean output
                def _img_summary(kind: str, path: str | None, meta: Dict[str, Any]) -> str:
                    file_info = (meta or {}).get("file", {})
                    logs = (meta or {}).get("logs", {})
                    return (
                        f"[{kind}] saved={file_info.get('exists', False)} path={file_info.get('path')} "
                        f"size={file_info.get('size', 0)} model={logs.get('model') or logs.get('used_model')}"
                    )

                print(_img_summary("Logo", logo_path, logo_meta))
                print(_img_summary("Invite", invite_path, invite_meta))
                # Also indicate background art path
                print(f"[Invite-Background] path={bg_out} exists={os.path.exists(bg_out)}")

                # Now that invite generation is complete, collect teaser preferences.
                try:
                    intake.collect_teaser_preferences(profile)
                except Exception:
                    pass

                # Ceremony planning (additive): ask exactly once after logo/invite generation
                try:
                    from app.services.ceremony_planner import CeremonyPlanner

                    planner = CeremonyPlanner()
                    planner.collect_ceremonies(profile)
                    # Per-ceremony teaser visuals (asked only for teaser-included)
                    try:
                        planner.collect_teaser_visuals_per_ceremony(profile)
                    except Exception:
                        pass
                    # Persist a minimal state so later generation can use ceremonies
                    try:
                        storage = Storage()
                        minimal_state = WeddingState(
                            profile=profile,
                            creative=None,
                            logistics=None,
                            financial=None,
                            design_spec=None,
                            media=None,
                            state_status="profile_with_ceremonies",
                            last_updated=datetime.utcnow().isoformat(),
                        )
                        if storage.save_state(minimal_state):
                            print("Saved updated state with ceremonies to data/state.json")
                            # Continue directly into style guide and teaser generation (once)
                            try:
                                router = ModelRouter()
                                # Grounded generation summary (current session only)
                                try:
                                    cers = list(getattr(profile, 'ceremonies', []) or [])
                                    teaser_inc = [c.name for c in cers if getattr(c, 'include_in_teaser', True)]
                                    style_inc = [c.name for c in cers if getattr(c, 'include_in_style_guide', True)]
                                    print("\n===== Generation Summary (Grounded) =====")
                                    print(f"Couple: {profile.bride_name} & {profile.groom_name}")
                                    print(f"Place:  {getattr(profile, 'wedding_place', None) or profile.destination}")
                                    print(f"Dates:  {', '.join(profile.wedding_dates)}")
                                    if getattr(profile, 'selected_hotel', None):
                                        print(f"Hotel:  {profile.selected_hotel}")
                                    print(f"Teaser ceremonies: {', '.join(teaser_inc) if teaser_inc else '-'}")
                                    print(f"Style guide ceremonies: {', '.join(style_inc) if style_inc else '-'}")
                                    print("==================================\n")
                                except Exception:
                                    pass
                                # Build teaser prompt using current profile + ceremonies
                                try:
                                    video_prompt2 = build_video_prompt(profile, None, None)
                                except Exception:
                                    video_prompt2 = "Create a short elegant wedding teaser with native audio."
                                video_out = os.path.join("assets", "video", "teaser.mp4")
                                v_path, v_meta = router.generate_teaser_video(
                                    video_prompt2, out_path=video_out, state=minimal_state
                                )
                                v_status = (v_meta or {}).get("status")
                                if v_status == "generated" and os.path.exists(video_out):
                                    print(f"[Teaser] saved=True path={video_out}")
                                else:
                                    v_err = (
                                        (v_meta or {}).get("teaser_video_error")
                                        or (v_meta or {}).get("logs", {}).get("error")
                                    )
                                    print(f"[Teaser] saved=False path={video_out} error={v_err}")
                            except Exception as te:
                                # Graceful handling: do not crash; keep style guide step independent
                                print(f"[Teaser] saved=False error={te}")

                            # Style guide PDF generation (independent of teaser success)
                            try:
                                pdf_out2 = os.path.join("assets", "style_guides", "style_guide.pdf")
                                pdf_info2 = build_style_guide_pdf(minimal_state, pdf_out2)
                                print(
                                    f"[Style Guide] saved={pdf_info2.get('exists', False)} path={pdf_info2.get('path')}"
                                )
                            except Exception as pe:
                                print(f"[Style Guide] saved=False error={pe}")
                    except Exception as se:
                        print(f"Could not save ceremonies to state: {se}")
                except Exception:
                    # Keep flow resilient
                    pass

            except Exception as gen_err:
                print(f"Generation step skipped due to an error: {gen_err}")
        except Exception as e:
            # Graceful degradation — do not break intake flow
            print(f"Maps-grounded hotel recommendations skipped due to an error: {e}")

        return

    state = _get_state()

    # Router will resolve API key via centralized helper
    router = ModelRouter()

    # Build prompts from structured state (single source of truth)
    profile = getattr(state, "profile", None)
    creative = getattr(state, "creative", None)
    design_spec = getattr(state, "design_spec", None)
    logistics = getattr(state, "logistics", None)

    if profile is None:
        raise RuntimeError("State.profile missing; cannot build media prompts.")

    logo_prompt = build_logo_prompt(profile, creative, design_spec)
    invite_prompt = build_invite_prompt(profile, creative, design_spec)
    # Build structured teaser prompt (global + ceremony blocks)
    teaser_struct = build_teaser_prompt_struct(profile, logistics, design_spec)
    video_prompt = teaser_struct.get("final_teaser_prompt", "")
    # Persist structured teaser prompt for downstream use
    try:
        media = getattr(state, "media", None)
        if media is None:
            media = MediaArtifacts()
            setattr(state, "media", media)
        setattr(media, "teaser_prompt_struct", teaser_struct)
    except Exception:
        pass
    try:
        print("[Teaser] Final prompt constructed (structured builder).")
        print(video_prompt)
    except Exception:
        pass
    # Ensure media state exists and set soundtrack direction guidance
    try:
        media = getattr(state, "media", None)
        if media is None:
            media = MediaArtifacts()
            setattr(state, "media", media)
        # Default soundtrack direction (non-copyrighted guidance)
        if getattr(media, "soundtrack_direction", None) in (None, ""):
            media.soundtrack_direction = (
                "Warm vintage-inspired romantic wedding ballad, soft instrumental or licensed vocal track"
            )
        # Persist the teaser prompt in state for visibility/debugging
        if getattr(media, "teaser_video_prompt", None) in (None, ""):
            media.teaser_video_prompt = video_prompt
    except Exception:
        pass
    # Keep pre-generation debug minimal; print concise summaries after generation

    # PART 1: Images
    logo_path, logo_meta = router.generate_logo_image(logo_prompt, state=state)

    # Invite: background-only generation + composed text overlay
    from app.models.schemas import ConfirmedCreativePayload
    from app.services.invite_text_overlay import render_invite_sections
    from app.services.invite_copy_service import generate_invitation_copy
    initials = (profile.bride_name[:1] + profile.groom_name[:1]).upper()
    payload = ConfirmedCreativePayload(
        bride_name=profile.bride_name,
        groom_name=profile.groom_name,
        initials=initials,
        wedding_dates=list(profile.wedding_dates or []),
        wedding_place=(getattr(profile, 'wedding_place', None) or profile.destination),
        selected_hotel=getattr(profile, 'selected_hotel', None),
        logo_style=getattr(profile, 'logo_style', None),
        logo_colors=getattr(profile, 'logo_colors', None),
        logo_text_preference=getattr(profile, 'logo_text_preference', None),
        logo_motif=getattr(profile, 'logo_motif', None),
        logo_text_mode=getattr(profile, 'logo_text_mode', None),
        logo_palette=getattr(profile, 'logo_palette', None),
        logo_mood=getattr(profile, 'logo_mood', None),
        invite_style=getattr(profile, 'invite_style', None),
        invite_colors=getattr(profile, 'invite_colors', None),
        invite_vibe=getattr(profile, 'invite_vibe', None),
        invite_theme=getattr(profile, 'invite_theme', None),
        invite_background_scene=getattr(profile, 'invite_background_scene', None),
        invite_palette=getattr(profile, 'invite_palette', None),
        invite_mood=getattr(profile, 'invite_mood', None),
        invite_floral_style=getattr(profile, 'invite_floral_style', None),
        invite_frame_style=getattr(profile, 'invite_frame_style', None),
        invite_layout_type=getattr(profile, 'invite_layout_type', None),
        include_rsvp=getattr(profile, 'include_rsvp', None),
        include_venue_details=getattr(profile, 'include_venue_details', None),
    )
    bg_out = os.path.join("assets", "invites", "invite_background.png")
    final_out = os.path.join("assets", "invites", "invite.png")

    # === Debug: Invite background generation visibility ===
    try:
        requested_venue = (
            getattr(profile, 'selected_hotel', None)
            or getattr(profile, 'wedding_place', None)
            or getattr(profile, 'destination', None)
            or '-'
        )
        # Heuristic mode classification (does not affect prompt or generation)
        # - venue_exact_unsupported: exact landmark/location requested, but pipeline cannot guarantee exact match
        # - venue_inspired: a specific hotel/venue name was provided by user
        # - generic_scene: otherwise
        requested_bg = getattr(profile, 'invite_background_scene', None)
        try:
            scene_l = (requested_bg or "").lower()
            exact_requested = any(k in scene_l for k in [
                "atal", "bridge", "riverfront", "gateway of india", "taj mahal", "lake palace", "fort", "temple"
            ])
        except Exception:
            exact_requested = False
        if exact_requested:
            bg_mode = 'venue_exact_unsupported'
        elif getattr(profile, 'selected_hotel', None):
            bg_mode = 'venue_inspired'
        else:
            bg_mode = 'generic_scene'
        print("===== Invite Background Debug =====")
        print(f"Requested venue: {requested_venue}")
        print(f"Requested background: {requested_bg or '-'}")
        print(f"Generation mode: {bg_mode}")
        if exact_requested:
            print("[Note] Exact location rendering is not supported in current pipeline; using scenic/inspired fallback.")
        print("Final prompt (image generation):")
        try:
            import textwrap as _tw
            for line in _tw.wrap(invite_prompt, width=120):
                print(line)
        except Exception:
            print(invite_prompt)
        print("===================================")
    except Exception:
        pass

    _, bg_meta = router.generate_invite_image(invite_prompt, out_path=bg_out, state=state)

    # === Post-generation: Verification step (non-blocking) ===
    try:
        ver = router.verify_invite_background(
            image_path=bg_out,
            venue_name=getattr(profile, 'selected_hotel', None),
            place_name=(getattr(profile, 'wedding_place', None) or getattr(profile, 'destination', None)),
        )
        print("===== Invite Background Verification =====")
        try:
            import json as _json
            print(_json.dumps({k: v for k, v in ver.items() if not str(k).startswith('_')}, indent=2))
        except Exception:
            print(ver)
        if not bool(ver.get('is_match', False)):
            print("[WARNING] Generated image does NOT match requested venue")
            try:
                if exact_requested:
                    print("[Info] Mismatch expected: exact-location rendering unsupported; generated scenic fallback.")
            except Exception:
                pass
        print("===========================================")
    except Exception as _ver_e:
        print(f"[Invite-Verify] skipped due to error: {_ver_e}")
    # Generate polished invitation copy via Gemini
    print("\n===== Generating Invite Copy (Gemini) =====")
    theme_hint = getattr(profile, 'invite_theme', None) or getattr(profile, 'invite_style', None)
    copy_sections = generate_invitation_copy(
        profile,
        theme_hint=theme_hint,
        include_rsvp=getattr(profile, 'include_rsvp', None),
        include_venue_details=getattr(profile, 'include_venue_details', None),
        selected_hotel=getattr(profile, 'selected_hotel', None),
    )
    if not _INVITE_COPY_LOGGED:
        print("===== Final Invite Copy (Gemini) =====")
        try:
            import json as _json
            print(_json.dumps(copy_sections, indent=2, ensure_ascii=False))
        except Exception:
            print(copy_sections)
        _INVITE_COPY_LOGGED = True
    print("[Confirm] Raw field labels not sent to renderer")

    invite_overlay = render_invite_sections(background_path=bg_out, sections_payload=copy_sections, out_path=final_out)
    # Single clean render payload print (post-render)
    if not _RENDER_PAYLOAD_LOGGED:
        print("===== Render Payload (Clean) =====")
        try:
            import json as _json
            print(_json.dumps(invite_overlay.get("render"), indent=2, ensure_ascii=False))
        except Exception:
            try:
                print(invite_overlay.get("render"))
            except Exception:
                pass
        _RENDER_PAYLOAD_LOGGED = True
    invite_path = final_out if invite_overlay.get("ok") else None
    invite_meta = {
        "file": {"path": final_out, "exists": bool(invite_path and os.path.exists(final_out)), "size": invite_overlay.get("size", 0)},
        "overlay": invite_overlay,
        "background": bg_meta,
    }

    # Clean one-line summaries for images (logo/invite)
    def _img_summary(kind: str, path: str | None, meta: Dict[str, Any]) -> str:
        file_info = (meta or {}).get("file", {})
        logs = (meta or {}).get("logs", {})
        return (
            f"[{kind}] saved={file_info.get('exists', False)} path={file_info.get('path')} "
            f"size={file_info.get('size', 0)} model={logs.get('model') or logs.get('used_model')}"
        )

    print(_img_summary("Logo", logo_path, logo_meta))
    print(_img_summary("Invite", invite_path, invite_meta))
    print(f"[Invite-Background] path={bg_out} exists={os.path.exists(bg_out)}")

    # Grounded generation summary before teaser/style guide (current session only)
    try:
        cers = list(getattr(profile, 'ceremonies', []) or [])
        teaser_inc = [c.name for c in cers if getattr(c, 'include_in_teaser', True)]
        style_inc = [c.name for c in cers if getattr(c, 'include_in_style_guide', True)]
        print("\n===== Generation Summary (Grounded) =====")
        print(f"Couple: {profile.bride_name} & {profile.groom_name}")
        print(f"Place:  {getattr(profile, 'wedding_place', None) or profile.destination}")
        print(f"Dates:  {', '.join(profile.wedding_dates)}")
        if getattr(profile, 'selected_hotel', None):
            print(f"Hotel:  {profile.selected_hotel}")
        print(f"Teaser ceremonies: {', '.join(teaser_inc) if teaser_inc else '-'}")
        print(f"Style guide ceremonies: {', '.join(style_inc) if style_inc else '-'}")
        print("==================================\n")
    except Exception:
        pass

    # PART 2: Video (concise output only)

    video_path, video_meta = router.generate_teaser_video(video_prompt, state=state)

    def _video_summary(meta: Dict[str, Any]) -> str:
        file_info = (meta or {}).get("file", {})
        status = (meta or {}).get("status")
        exists_flag = file_info.get("exists", False)
        path = file_info.get("path")
        err = (meta or {}).get("teaser_video_error")
        if status == "generated" and exists_flag:
            return f"[Video] status=generated path={path} exists=True"
        return f"[Video] status=error error={err}"

    print(_video_summary(video_meta))
    try:
        logs = (video_meta or {}).get("logs", {}) or {}
        audio_used = logs.get("audio_kwargs_used")
        if not audio_used:
            print("[Teaser] Music preference captured, but audio embedding is not supported in the current generation path.")
        else:
            print(f"[Teaser] Audio kwargs used by SDK: {audio_used}")
        print(f"[Teaser] saved_path={(video_meta or {}).get('file', {}).get('path')}")
    except Exception:
        pass

    # Ending card: render from structured profile and attempt to append programmatically
    try:
        ending = render_teaser_ending_card(profile, out_path=os.path.join("assets", "video", "ending_card.png"))
        print(f"[Teaser-EndingCard] path={ending.get('path')} exists={ending.get('exists')}")
        if video_meta.get("status") == "generated" and ending.get("exists"):
            append = append_ending_card_to_video(
                video_path=video_meta.get("file", {}).get("path"),
                ending_image_path=ending.get("path"),
                out_path=os.path.join("assets", "video", "teaser_with_ending.mp4"),
                duration_seconds=3,
            )
            if append.get("ok"):
                print(f"[Video] appended_ending=True path={append.get('path')}")
            else:
                reason = append.get("reason") or "append_failed"
                print(f"[Video] appended_ending=False reason={reason}")
    except Exception as e:
        print(f"[Teaser-EndingCard] skipped due to error: {e}")

    # PART 3: Style Guide PDF with generated event moodboards
    pdf_out = os.path.join("assets", "style_guides", "style_guide.pdf")
    # Pass router so the builder can generate/refresh moodboard images per ceremony
    pdf_info = build_style_guide_pdf(state, pdf_out, router=router)
    print(f"[StyleGuide] path={pdf_info.get('path')} exists={pdf_info.get('exists')} pages={pdf_info.get('page_count')}")

    # Final paths (one place)
    try:
        print("\n===== Output Artifacts =====")
        print(f"Logo: {os.path.join('assets','logo','logo.png')}")
        print(f"Final Invite: {final_out}")
        print(f"Style Guide PDF: {pdf_out}")
        print(f"Teaser Video: {video_meta.get('file', {}).get('path')}")
    except Exception:
        pass


if __name__ == "__main__":
    main()
