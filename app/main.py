from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, List

from dotenv import load_dotenv

# Load environment variables before importing project modules
load_dotenv()

# Safe sys.path fix when run as: python app/main.py
if __package__ in (None, ""):
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.model_router import ModelRouter
from app.services.styleguide_pdf import build_style_guide_pdf
from app.services.storage import Storage
from app.models.schemas import WeddingState, MediaArtifacts
from app.prompts.artifact_prompts import (
    build_logo_prompt,
    build_invite_prompt,
    build_video_prompt,
)


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
    state = _get_state()

    api_key = os.environ.get("GEMINI_API_KEY")
    print("[Main] GEMINI_API_KEY present:", bool(api_key))

    router = ModelRouter(api_key=api_key)

    # Build prompts from structured state (single source of truth)
    profile = getattr(state, "profile", None)
    creative = getattr(state, "creative", None)
    design_spec = getattr(state, "design_spec", None)
    logistics = getattr(state, "logistics", None)

    if profile is None:
        raise RuntimeError("State.profile missing; cannot build media prompts.")

    logo_prompt = build_logo_prompt(profile, creative, design_spec)
    invite_prompt = build_invite_prompt(profile, creative, design_spec)
    video_prompt = build_video_prompt(profile, logistics, design_spec)
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
    invite_path, invite_meta = router.generate_invite_image(invite_prompt, state=state)

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

    # PART 3: Style Guide PDF with generated event moodboards
    pdf_out = os.path.join("assets", "style_guides", "style_guide.pdf")
    pdf_info = build_style_guide_pdf(state, pdf_out)
    print(
        f"[StyleGuide] image-only PDF generated path={pdf_info.get('path')} exists={pdf_info.get('exists')}"
    )


if __name__ == "__main__":
    main()
