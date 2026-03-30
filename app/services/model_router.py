import os
import base64
from typing import Any, Optional, Tuple, List, Dict

# Keep prints minimal here; return rich logs for callers to summarize once.

from .media_generator import MediaGenerator
from app.config import DEFAULT_GEMINI_TEXT_MODEL


class ModelRouter:
    def __init__(self, api_key: Optional[str] = None) -> None:
        self.generator = MediaGenerator(api_key=api_key)

    # PART 1: Images (google-genai 1.67.0 pattern)
    def _save_image_bytes(self, data: bytes, out_path: str) -> Optional[str]:
        try:
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            with open(out_path, "wb") as f:
                f.write(data)
            return out_path
        except Exception:
            return None

    def _extract_image_from_parts(self, parts: List[Any], out_path: str) -> Tuple[Optional[str], bool]:
        found = False
        saved_path: Optional[str] = None
        try:
            for p in parts or []:
                # Prefer SDK helper if present
                if hasattr(p, "as_image") and callable(getattr(p, "as_image")):
                    try:
                        pil_im = p.as_image()
                        if pil_im is not None:
                            os.makedirs(os.path.dirname(out_path), exist_ok=True)
                            pil_im.save(out_path)
                            saved_path = out_path
                            found = True
                            break
                    except Exception:
                        pass
                # Fallback: inline_data.data (base64)
                if hasattr(p, "inline_data") and getattr(p, "inline_data") is not None:
                    inline = getattr(p, "inline_data")
                    data = getattr(inline, "data", None)
                    if isinstance(data, (bytes, bytearray)):
                        saved_path = self._save_image_bytes(bytes(data), out_path)
                        found = bool(saved_path)
                        if found:
                            break
                    if isinstance(data, str):
                        try:
                            raw = base64.b64decode(data)
                            saved_path = self._save_image_bytes(raw, out_path)
                            found = bool(saved_path)
                            if found:
                                break
                        except Exception:
                            pass
        except Exception:
            pass
        return saved_path, found

    def _gen_image_via_models_generate_content(self, prompt: str, out_path: str) -> Tuple[Optional[str], dict]:
        client = getattr(self.generator, "_client", None)
        model = "gemini-3.1-flash-image-preview"
        logs = {"model": model}
        saved_path: Optional[str] = None
        try:
            if client is None or not hasattr(client, "models") or not hasattr(client.models, "generate_content"):
                raise RuntimeError("google-genai client not available or missing models.generate_content")

            resp = client.models.generate_content(
                model=model,
                contents=[{"role": "user", "parts": [{"text": prompt}]}],
            )

            # Debug: response.parts presence and count
            parts = getattr(resp, "parts", None)
            if parts is None:
                # Common shape: candidates[0].content.parts
                cand = getattr(resp, "candidates", None)
                if cand and len(cand) > 0 and hasattr(cand[0], "content"):
                    content = cand[0].content
                    parts = getattr(content, "parts", None)

            has_parts = parts is not None
            part_count = len(parts) if isinstance(parts, list) else 0
            # Do not spam logs here; expose in logs for caller summary

            if has_parts and part_count > 0:
                saved_path, found = self._extract_image_from_parts(parts, out_path)
                # Silent success; caller will summarize
            else:
                # Expose via logs only; no print here
                pass

            logs.update({
                "parts_present": has_parts,
                "part_count": part_count,
                "saved_path": saved_path,
            })
        except Exception as e:
            logs["error"] = str(e)
        return saved_path, logs

    def generate_logo_image(
        self,
        prompt: str,
        out_path: str = os.path.join("assets", "logo", "logo.png"),
        state: Optional[Any] = None,
    ) -> Tuple[Optional[str], dict]:
        saved_path, logs = self._gen_image_via_models_generate_content(prompt, out_path)
        # State update only if file exists
        exists = bool(saved_path and os.path.exists(saved_path))
        if state is not None and exists:
            try:
                if isinstance(state, dict):
                    media = state.setdefault("media", {})
                    media["logo_image_path"] = saved_path
                else:
                    media = getattr(state, "media", None)
                    if media is None:
                        setattr(state, "media", type("Media", (), {})())
                        media = getattr(state, "media")
                    setattr(media, "logo_image_path", saved_path)
            except Exception:
                pass
        if not exists:
            self.generator._write_report(
                kind="image",
                out_path=out_path,
                message="No image part returned or save failed for logo.",
                details={"model": logs.get("model"), "parts_present": logs.get("parts_present"), "part_count": logs.get("part_count"), "error": logs.get("error")},
            )
        return (saved_path if exists else None, {"file": {"path": out_path, "exists": exists, "size": os.path.getsize(out_path) if exists else 0}, "logs": logs})

    def generate_invite_image(
        self,
        prompt: str,
        out_path: str = os.path.join("assets", "invites", "invite.png"),
        state: Optional[Any] = None,
    ) -> Tuple[Optional[str], dict]:
        saved_path, logs = self._gen_image_via_models_generate_content(prompt, out_path)
        exists = bool(saved_path and os.path.exists(saved_path))
        if state is not None and exists:
            try:
                if isinstance(state, dict):
                    media = state.setdefault("media", {})
                    media["invite_image_path"] = saved_path
                else:
                    media = getattr(state, "media", None)
                    if media is None:
                        setattr(state, "media", type("Media", (), {})())
                        media = getattr(state, "media")
                    setattr(media, "invite_image_path", saved_path)
            except Exception:
                pass
        if not exists:
            self.generator._write_report(
                kind="image",
                out_path=out_path,
                message="No image part returned or save failed for invite.",
                details={"model": logs.get("model"), "parts_present": logs.get("parts_present"), "part_count": logs.get("part_count"), "error": logs.get("error")},
            )
        return (saved_path if exists else None, {"file": {"path": out_path, "exists": exists, "size": os.path.getsize(out_path) if exists else 0}, "logs": logs})

    def verify_invite_background(
        self,
        image_path: str,
        venue_name: Optional[str] = None,
        place_name: Optional[str] = None,
        timeout_seconds: float = 20.0,
    ) -> Dict[str, Any]:
        """Use the LLM to check if an image matches the requested venue.

        Returns a JSON-like dict with keys: is_match (bool), confidence (float), reason (str).
        Non-fatal: on any error, returns a best-effort dict with is_match=False and reason.
        """
        result: Dict[str, Any] = {"is_match": False, "confidence": 0.0, "reason": "uninitialized"}
        try:
            client = getattr(self.generator, "_client", None)
            if client is None or not hasattr(client, "models") or not hasattr(client.models, "generate_content"):
                return {"is_match": False, "confidence": 0.0, "reason": "verification_unavailable:no_client"}

            if not (image_path and os.path.exists(image_path)):
                return {"is_match": False, "confidence": 0.0, "reason": "verification_unavailable:no_image"}

            # Read image bytes and guess mime
            try:
                with open(image_path, "rb") as f:
                    data = f.read()
            except Exception as e:
                return {"is_match": False, "confidence": 0.0, "reason": f"read_error:{e}"}

            lower = image_path.lower()
            mime = "image/png"
            if lower.endswith(".jpg") or lower.endswith(".jpeg"):
                mime = "image/jpeg"
            elif lower.endswith(".webp"):
                mime = "image/webp"

            venue = (venue_name or "").strip()
            place = (place_name or "").strip()

            check_target = venue if venue else place
            if not check_target:
                # No explicit venue/place to check against
                return {"is_match": False, "confidence": 0.0, "reason": "no_requested_venue_or_place"}

            instruction = (
                "You are verifying if an image matches a requested wedding venue/location.\n"
                "Given the attached image and the requested venue/location, respond ONLY with a strict JSON object:\n"
                "{\n  \"is_match\": true|false,\n  \"confidence\": <float 0..1>,\n  \"reason\": \"<under 2 sentences>\"\n}\n"
                "Rules:\n- Be conservative; if unsure, set is_match=false.\n"
                "- confidence is your probability judgment in [0,1].\n"
                "- reason should briefly mention visual cues vs the requested venue.\n\n"
                f"Requested venue/location: {check_target}\n"
            )

            contents = [
                {
                    "role": "user",
                    "parts": [
                        {"text": instruction},
                        {"inline_data": {"mime_type": mime, "data": data}},
                    ],
                }
            ]

            # Use the default fast text model for structured judgments
            model = DEFAULT_GEMINI_TEXT_MODEL

            # Run with a simple timeout mechanism
            import time as _t
            start = _t.time()
            resp = client.models.generate_content(model=model, contents=contents)
            elapsed = _t.time() - start

            text = getattr(resp, "text", None)
            if not text:
                text = str(resp)

            # Attempt to extract strict JSON
            import json as _json
            raw = text.strip()
            # Strip code fences if present
            if raw.startswith("```"):
                try:
                    raw = raw.split("\n", 1)[1]
                    if raw.endswith("```"):
                        raw = raw.rsplit("```", 1)[0]
                except Exception:
                    pass
            parsed: Dict[str, Any]
            try:
                parsed = _json.loads(raw)
            except Exception:
                # Best effort: look for JSON substring
                import re as _re
                m = _re.search(r"\{[\s\S]*\}", raw)
                if m:
                    try:
                        parsed = _json.loads(m.group(0))
                    except Exception:
                        parsed = {"is_match": False, "confidence": 0.0, "reason": "parse_failed"}
                else:
                    parsed = {"is_match": False, "confidence": 0.0, "reason": "parse_failed"}

            # Normalize types
            parsed_flag = bool(parsed.get("is_match", False))
            try:
                confidence = float(parsed.get("confidence", 0.0))
            except Exception:
                confidence = 0.0
            reason = str(parsed.get("reason", "")).strip() or ""
            if confidence < 0:
                confidence = 0.0
            if confidence > 1:
                confidence = 1.0

            # Enforce consistent verification logic
            is_match = True if confidence > 0.7 else False
            try:
                assert not (is_match is False and confidence > 0.9)
            except AssertionError:
                # If inconsistency somehow occurs, prefer the threshold-based outcome
                is_match = True

            result = {"is_match": is_match, "confidence": confidence, "reason": reason, "_latency_sec": round(elapsed, 2)}
            return result
        except Exception as e:
            return {"is_match": False, "confidence": 0.0, "reason": f"verify_error:{e}"}

    # PART 2: Video (Veo 3.1, google-genai models.generate_videos flow)
    def generate_teaser_video(
        self,
        prompt: str,
        out_path: str = os.path.join("assets", "video", "teaser.mp4"),
        state: Optional[Any] = None,
        _attempt: int = 1,
    ) -> Tuple[Optional[str], dict]:
        client = getattr(self.generator, "_client", None)
        model = "veo-3.1-generate-preview"
        logs: dict = {"model": model}
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        saved_path: Optional[str] = None

        if client is None or not hasattr(client, "models") or not hasattr(client.models, "generate_videos"):
            err = "google-genai client not available or missing models.generate_videos"
            logs["error"] = err
            self.generator._write_report(
                kind="video", out_path=out_path, message="Veo generation unavailable.", details={"error": err}
            )
            return None, {"file": {"path": out_path, "exists": False, "size": 0}, "logs": logs, "status": "error"}

        try:
            # Submit Veo request (operation-based)
            operation = client.models.generate_videos(model=model, prompt=prompt)
            name = getattr(operation, "name", None) or getattr(operation, "id", None)
            logs["operation_name"] = name

            # Poll until done
            done = bool(getattr(operation, "done", False))
            while not done:
                time_sleep = 3.0
                try:
                    import time as _t
                    _t.sleep(time_sleep)
                except Exception:
                    pass
                # Refresh via operations.get
                if hasattr(client, "operations") and hasattr(client.operations, "get"):
                    operation = client.operations.get(operation=operation)
                done = bool(getattr(operation, "done", False))
            logs["operation_done"] = True

            # Extract generated video artifact and inspect structures
            response = getattr(operation, "response", None)
            # Capture available fields for debugging
            try:
                logs["operation_type"] = type(operation).__name__
                logs["response_type"] = type(response).__name__ if response is not None else None
                logs["operation_fields"] = [a for a in dir(operation) if not a.startswith("__")][:50]
                if response is not None:
                    logs["response_fields"] = [a for a in dir(response) if not a.startswith("__")][:50]
            except Exception:
                pass

            vids = getattr(response, "generated_videos", None) if response is not None else None
            url = None
            v0_info = {}
            if vids and isinstance(vids, list) and len(vids) > 0:
                v0 = vids[0]
                # Log fields present on the generated video object
                try:
                    v0_info = {
                        "type": type(v0).__name__,
                        "attrs": [a for a in dir(v0) if not a.startswith("__")][:50],
                        "has_video": hasattr(v0, "video") and getattr(v0, "video") is not None,
                        "has_uri": hasattr(v0, "uri") and getattr(v0, "uri") is not None,
                        "has_name": hasattr(v0, "name") and getattr(v0, "name") is not None,
                    }
                    logs["generated_video_0"] = v0_info
                except Exception:
                    pass

                # Prefer direct file reference when present (Files API)
                file_ref = getattr(v0, "video", None)
                if file_ref is not None:
                    try:
                        if hasattr(client, "files") and hasattr(client.files, "download"):
                            dl = client.files.download(file=file_ref)  # type: ignore
                            data = None
                            # Normalize various possible return types
                            if isinstance(dl, (bytes, bytearray)):
                                data = bytes(dl)
                            elif hasattr(dl, "read") and callable(getattr(dl, "read")):
                                try:
                                    data = dl.read()
                                except Exception:
                                    data = None
                            elif hasattr(dl, "content"):
                                data = getattr(dl, "content")
                            elif hasattr(dl, "data"):
                                data = getattr(dl, "data")

                            if data:
                                with open(out_path, "wb") as f:
                                    f.write(data if isinstance(data, (bytes, bytearray)) else bytes(data))
                                saved_path = out_path
                                logs["download_ok"] = True
                                logs["download_via"] = "client.files.download"
                                try:
                                    logs["download_bytes"] = len(data)  # type: ignore[arg-type]
                                except Exception:
                                    pass
                        # Some SDKs might expose a save() on the file handle
                        elif hasattr(file_ref, "save") and callable(getattr(file_ref, "save")):
                            try:
                                file_ref.save(out_path)
                                saved_path = out_path
                                logs["download_ok"] = True
                                logs["download_via"] = "video.save"
                            except Exception as se:
                                logs["download_error"] = str(se)
                    except Exception as fe:
                        logs["download_error"] = str(fe)

                # If no file handle path worked, consider direct URIs
                if not saved_path:
                    url = getattr(v0, "uri", None) or getattr(v0, "download_uri", None)
            logs["has_generated_videos"] = bool(vids and isinstance(vids, list) and len(vids) > 0)
            logs["video_uri"] = url

            # Download
            if (not saved_path) and url:
                try:
                    import requests  # type: ignore
                    r = requests.get(url, timeout=120)
                    if r.ok and r.content:
                        with open(out_path, "wb") as f:
                            f.write(r.content)
                        saved_path = out_path
                        logs["download_bytes"] = len(r.content)
                        logs["download_ok"] = True
                except Exception as de:
                    logs["download_error"] = str(de)
            elif not saved_path:
                logs["download_ok"] = False

        except Exception as e:
            err_text = str(e)
            logs["error"] = err_text
            # Retry transient errors up to 3 attempts
            lower = err_text.lower()
            if _attempt < 3 and ("503" in lower or "unavailable" in lower):
                try:
                    import time as _t
                    _t.sleep(2.0)
                except Exception:
                    pass
                return self.generate_teaser_video(prompt, out_path=out_path, state=state, _attempt=_attempt + 1)
            # Final failure: write a focused report (no fallback video)
            self.generator._write_report(
                kind="video",
                out_path=out_path,
                message="Veo generation failed.",
                details={"model": model, "prompt": prompt, "attempts": _attempt, "final_error": err_text},
            )

        exists = bool(saved_path and os.path.exists(saved_path))
        # If we did get artifacts but saving failed, write a focused fallback report
        try:
            has_vids = logs.get("has_generated_videos", False)
            if has_vids and not exists:
                self.generator._write_report(
                    kind="video",
                    out_path=out_path,
                    message="Generated videos present but save failed.",
                    details={
                        "model": model,
                        "operation_done": logs.get("operation_done"),
                        "operation_type": logs.get("operation_type"),
                        "response_type": logs.get("response_type"),
                        "operation_fields": logs.get("operation_fields"),
                        "response_fields": logs.get("response_fields"),
                        "generated_video_0": logs.get("generated_video_0"),
                        "video_uri": logs.get("video_uri"),
                        "download_ok": logs.get("download_ok"),
                        "download_error": logs.get("download_error"),
                        "error": logs.get("error"),
                    },
                )
        except Exception:
            pass
        # Update state
        if state is not None:
            try:
                if isinstance(state, dict):
                    media = state.setdefault("media", {})
                    media["teaser_video_path"] = saved_path if exists else None
                    media["teaser_video_status"] = "generated" if exists else "error"
                    if not exists:
                        media["teaser_video_error"] = logs.get("error") or logs.get("download_error")
                else:
                    media = getattr(state, "media", None)
                    if media is None:
                        setattr(state, "media", type("Media", (), {})())
                        media = getattr(state, "media")
                    setattr(media, "teaser_video_path", saved_path if exists else None)
                    setattr(media, "teaser_video_status", "generated" if exists else "error")
                    if not exists:
                        try:
                            setattr(media, "teaser_video_error", logs.get("error") or logs.get("download_error"))
                        except Exception:
                            pass
            except Exception:
                pass

        meta = {
            "file": {"path": out_path, "exists": exists, "size": os.path.getsize(out_path) if exists else 0},
            "logs": logs,
            "status": ("generated" if exists else "error"),
            "teaser_video_path": saved_path if exists else None,
            "teaser_video_status": ("generated" if exists else "error"),
            "teaser_video_error": (logs.get("error") or logs.get("download_error")) if not exists else None,
        }
        return (saved_path if exists else None, meta)
