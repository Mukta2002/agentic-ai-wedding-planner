from __future__ import annotations

import os
import subprocess
from typing import Any, Dict, Optional

from PIL import Image, ImageDraw, ImageFont


def _ensure_dir(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)


def render_teaser_ending_card(profile: Any, out_path: str = os.path.join("assets", "video", "ending_card.png")) -> Dict[str, Any]:
    """Render a cinematic closing card image using structured profile data only.

    Text:
    - line 1: "Bride & Groom"
    - line 2: "12 December 2026" style human-readable if dates exist, else join raw

    Returns metadata with path and existence flag.
    """
    bride = (getattr(profile, "bride_name", "") or "").strip()
    groom = (getattr(profile, "groom_name", "") or "").strip()
    couple = f"{bride} & {groom}".strip(" &")
    dates = list(getattr(profile, "wedding_dates", []) or [])
    # Prefer the first date in a nicer display if it's ISO-like
    def _human(d: str) -> str:
        try:
            from datetime import datetime
            for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
                try:
                    dt = datetime.strptime(d, fmt)
                    return dt.strftime("%d %B %Y")
                except Exception:
                    pass
            return d
        except Exception:
            return d

    readable = ""
    if dates:
        readable = _human(dates[0])
    _ensure_dir(out_path)

    # 16:9 frame, neutral luxe
    W, H = 1920, 1080
    img = Image.new("RGB", (W, H), (6, 8, 10))
    draw = ImageDraw.Draw(img)
    try:
        f1 = ImageFont.load_default()
        f2 = ImageFont.load_default()
    except Exception:
        f1 = f2 = None

    def _center(text: str, y: int, font) -> int:
        if not text:
            return y
        w = int(draw.textlength(text, font=font))
        x = (W - w) // 2
        draw.text((x, y), text, fill=(235, 235, 232), font=font)
        return y + 48

    y = H // 2 - 40
    y = _center(couple, y, f1)
    _center(readable, y, f2)

    img.save(out_path)
    return {"path": out_path, "exists": os.path.exists(out_path), "size": os.path.getsize(out_path) if os.path.exists(out_path) else 0}


def _have_ffmpeg() -> bool:
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        return True
    except Exception:
        return False


def append_ending_card_to_video(video_path: str, ending_image_path: str, out_path: Optional[str] = None, duration_seconds: int = 3) -> Dict[str, Any]:
    """Attempt to append a short ending card clip (from image) to an existing MP4 using ffmpeg.

    - If ffmpeg is not available, returns a metadata dict noting skip.
    - On success, writes a new MP4 (default next to original with suffix _with_ending.mp4).
    """
    if not os.path.exists(video_path) or not os.path.exists(ending_image_path):
        return {"ok": False, "reason": "missing_input", "video": video_path, "ending_image": ending_image_path}

    if not _have_ffmpeg():
        return {"ok": False, "reason": "ffmpeg_not_found", "video": video_path, "ending_image": ending_image_path}

    base_dir = os.path.dirname(video_path)
    name, ext = os.path.splitext(os.path.basename(video_path))
    out_path = out_path or os.path.join(base_dir, f"{name}_with_ending{ext}")

    # Build a short clip ending.ts from the image, same base format
    part1 = os.path.join(base_dir, "__part1.ts")
    part2 = os.path.join(base_dir, "__part2.ts")

    cmds = [
        [
            "ffmpeg", "-y", "-hide_banner", "-i", video_path,
            "-c", "copy", "-bsf:v", "h264_mp4toannexb", "-f", "mpegts", part1,
        ],
        [
            "ffmpeg", "-y", "-hide_banner", "-loop", "1", "-t", str(int(max(1, duration_seconds))), "-i", ending_image_path,
            "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-f", "mpegts", part2,
        ],
        [
            "ffmpeg", "-y", "-hide_banner", "-i", f"concat:{part1}|{part2}", "-c", "copy", "-bsf:a", "aac_adtstoasc", out_path,
        ],
    ]

    logs: Dict[str, Any] = {"steps": []}
    ok = True
    for c in cmds:
        try:
            r = subprocess.run(c, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            logs["steps"].append({"cmd": c, "code": r.returncode})
            if r.returncode != 0:
                ok = False
                break
        except Exception as e:
            logs["steps"].append({"cmd": c, "error": str(e)})
            ok = False
            break

    # cleanup
    for p in (part1, part2):
        try:
            if os.path.exists(p):
                os.remove(p)
        except Exception:
            pass

    exists = ok and os.path.exists(out_path)
    return {"ok": exists, "path": out_path, "logs": logs}

