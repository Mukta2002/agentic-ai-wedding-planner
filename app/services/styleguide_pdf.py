import os
from typing import Any, Dict, List

from PIL import Image


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
    """Generate an image-only PDF from assets/style_guides/generated.

    Each page contains exactly one image, centered and scaled.
    No titles, captions, or text blocks are added.
    """
    # Support legacy/new signatures; we only need the output path.
    out_path = state_or_out if isinstance(state_or_out, str) else out_path_or_events
    _ensure_dir(out_path)

    generated_dir = os.path.join("assets", "style_guides", "generated")
    try:
        names = sorted(
            [n for n in os.listdir(generated_dir) if n.lower().endswith((".png", ".jpg", ".jpeg"))]
        )
    except Exception:
        names = []

    pages: List[Image.Image] = []
    W, H = 1240, 1754  # A4-ish at ~150dpi
    for n in names:
        p = os.path.join(generated_dir, n)
        try:
            with Image.open(p) as im:
                im = im.convert("RGB")
                page = Image.new("RGB", (W, H), (255, 255, 255))
                # Center and scale preserving aspect
                box_w, box_h = W - 120, H - 120
                ratio = min(box_w / max(1, im.width), box_h / max(1, im.height))
                new_w = max(1, int(im.width * ratio))
                new_h = max(1, int(im.height * ratio))
                im_resized = im.resize((new_w, new_h))
                x = (W - new_w) // 2
                y = (H - new_h) // 2
                page.paste(im_resized, (x, y))
                pages.append(page)
        except Exception:
            continue

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

