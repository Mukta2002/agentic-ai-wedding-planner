import os
import io
import json
import time
import base64
from datetime import datetime
from typing import Any, Dict, Optional, Tuple


def _ensure_dir(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)


def _file_info(path: str) -> Dict[str, Any]:
    return {
        "path": path,
        "exists": os.path.exists(path),
        "size": os.path.getsize(path) if os.path.exists(path) else 0,
    }


class MediaGenerator:
    def __init__(self, api_key: Optional[str] = None) -> None:
        # Prefer the new google-genai client. Avoid depending on google-generativeai
        # unless absolutely necessary.
        self._client = None  # google-genai client
        self._legacy_genai = None  # google-generativeai module (optional)
        self._sdk_used = None  # "google-genai" or "google-generativeai"
        self._import_notes: Dict[str, Any] = {}

        # API key precedence: GEMINI_API_KEY (new) then GOOGLE_API_KEY
        self._api_key = (
            api_key
            or os.environ.get("GEMINI_API_KEY")
            or os.environ.get("GOOGLE_API_KEY")
            or os.environ.get("GOOGLE_APIKEY")
        )

        # Try new SDK first
        try:
            from google import genai as genai_new  # type: ignore

            self._client = genai_new.Client(api_key=self._api_key)
            self._sdk_used = "google-genai"
            self._import_notes["google-genai"] = "ok"
        except Exception as e:
            self._client = None
            self._import_notes["google-genai"] = f"import_failed: {e}"

        # Optionally detect legacy SDK, but do not require it.
        try:
            import google.generativeai as genai_legacy  # type: ignore

            # Only configure if we have a key; keep as optional fallback.
            if self._api_key:
                try:
                    genai_legacy.configure(api_key=self._api_key)
                except Exception:
                    pass
            self._legacy_genai = genai_legacy
            self._import_notes["google-generativeai"] = "available"
        except Exception as e:
            self._legacy_genai = None
            self._import_notes["google-generativeai"] = f"not_available: {e}"

    def get_sdk_debug_info(self) -> Dict[str, Any]:
        versions: Dict[str, Any] = {}
        try:
            from importlib.metadata import version, PackageNotFoundError  # type: ignore

            for pkg in ("google-genai", "google-generativeai"):
                try:
                    versions[pkg] = version(pkg)
                except PackageNotFoundError:
                    versions[pkg] = None
        except Exception:
            pass

        return {
            "sdk_used": self._sdk_used,
            "client_available": bool(self._client),
            "legacy_available": bool(self._legacy_genai),
            "import_notes": self._import_notes,
            "versions": versions,
            "client_type": type(self._client).__name__ if self._client is not None else None,
        }

    # ---------- REPORTING ----------
    def _write_report(self, kind: str, out_path: str, message: str, details: Dict[str, Any]) -> str:
        try:
            reports_dir = os.path.join("assets", "reports")
            os.makedirs(reports_dir, exist_ok=True)
            ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
            fname = f"{kind}_fallback_{ts}.txt"
            fpath = os.path.join(reports_dir, fname)
            blob = {
                "message": message,
                "kind": kind,
                "target_out_path": out_path,
                "sdk": self.get_sdk_debug_info(),
                "details": {**details, "timestamp": ts},
            }
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(json.dumps(blob, indent=2, default=str))
            return fpath
        except Exception:
            return ""

    # ---------- IMAGE GENERATION ----------
    def _inspect_image_response(self, resp: Any) -> Dict[str, Any]:
        info: Dict[str, Any] = {
            "response_type": type(resp).__name__,
            "has_dict": hasattr(resp, "to_dict"),
            "has_json": hasattr(resp, "to_json"),
            "attributes": [],
            "found": {
                "bytes": False,
                "inline_data": False,
                "pil_image": False,
                "urls": [],
                "metadata": False,
            },
        }
        try:
            info["attributes"] = sorted([a for a in dir(resp) if not a.startswith("__")])[:100]
        except Exception:
            info["attributes"] = []

        # Heuristics to detect content
        try:
            # Parts-based (generate_content) shape
            parts = None
            if hasattr(resp, "candidates") and resp.candidates:
                cand = resp.candidates[0]
                if hasattr(cand, "content") and hasattr(cand.content, "parts"):
                    parts = cand.content.parts
            if parts:
                for p in parts:
                    # Inline data style
                    if hasattr(p, "inline_data"):
                        info["found"]["inline_data"] = True
                        idd = p.inline_data
                        if hasattr(idd, "data") and idd.data:
                            info["found"]["bytes"] = True
                    # PIL images are unlikely here, but check
                    if hasattr(p, "image"):
                        info["found"]["pil_image"] = True

            # Images API style
            if hasattr(resp, "images") and resp.images:
                for im in resp.images:
                    if hasattr(im, "bytes") and im.bytes:
                        info["found"]["bytes"] = True
                    if hasattr(im, "data") and im.data:
                        info["found"]["bytes"] = True
                    if hasattr(im, "uri") and im.uri:
                        info["found"]["urls"].append(getattr(im, "uri"))

            # Generic url locations
            if hasattr(resp, "uri") and getattr(resp, "uri"):
                info["found"]["urls"].append(getattr(resp, "uri"))

            # Metadata
            if hasattr(resp, "model_version") or hasattr(resp, "usage_metadata"):
                info["found"]["metadata"] = True
        except Exception:
            pass

        return info

    def _extract_image_bytes(self, resp: Any) -> Optional[bytes]:
        # 1) New Images API shapes
        try:
            if hasattr(resp, "images") and resp.images:
                for im in resp.images:
                    if hasattr(im, "bytes") and im.bytes:
                        return im.bytes
                    if hasattr(im, "data") and im.data:
                        data = im.data
                        if isinstance(data, (bytes, bytearray)):
                            return bytes(data)
                        if isinstance(data, str):
                            try:
                                return base64.b64decode(data)
                            except Exception:
                                pass
        except Exception:
            pass

        # 2) generate_content: inline_data in parts
        try:
            if hasattr(resp, "candidates") and resp.candidates:
                cand = resp.candidates[0]
                if hasattr(cand, "content") and hasattr(cand.content, "parts"):
                    for p in cand.content.parts:
                        if hasattr(p, "inline_data") and p.inline_data:
                            idd = p.inline_data
                            if hasattr(idd, "data") and idd.data:
                                data = idd.data
                                if isinstance(data, (bytes, bytearray)):
                                    return bytes(data)
                                if isinstance(data, str):
                                    try:
                                        return base64.b64decode(data)
                                    except Exception:
                                        pass
        except Exception:
            pass

        # 3) Dict/JSON fallbacks
        try:
            d = None
            if hasattr(resp, "to_dict"):
                d = resp.to_dict()  # type: ignore
            elif hasattr(resp, "to_json"):
                d = json.loads(resp.to_json())  # type: ignore
            if d:
                # Common nested shapes
                # images -> [ { bytes|data|base64_data } ]
                images = d.get("images") if isinstance(d, dict) else None
                if images and isinstance(images, list):
                    for im in images:
                        for key in ("bytes", "data", "base64_data"):
                            if key in im and im[key]:
                                val = im[key]
                                if isinstance(val, (bytes, bytearray)):
                                    return bytes(val)
                                if isinstance(val, str):
                                    try:
                                        return base64.b64decode(val)
                                    except Exception:
                                        pass

                # candidates[0].content.parts[*].inline_data.data
                candidates = d.get("candidates") if isinstance(d, dict) else None
                if candidates and isinstance(candidates, list) and candidates:
                    cont = candidates[0].get("content")
                    if cont and isinstance(cont, dict):
                        parts = cont.get("parts")
                        if parts and isinstance(parts, list):
                            for p in parts:
                                idd = p.get("inline_data") if isinstance(p, dict) else None
                                if idd and isinstance(idd, dict) and idd.get("data"):
                                    val = idd.get("data")
                                    if isinstance(val, str):
                                        try:
                                            return base64.b64decode(val)
                                        except Exception:
                                            pass
        except Exception:
            pass
        return None

    def generate_image(
        self,
        prompt: str,
        out_path: str,
        model_name: Optional[str] = None,
        state: Optional[Any] = None,
        state_attr: Optional[str] = None,
    ) -> Tuple[Optional[str], Dict[str, Any]]:
        # Reduce terminal noise: avoid prints here; caller summarizes once
        _ensure_dir(out_path)
        result: Any = None
        used_model: Optional[str] = None
        used_path: Optional[str] = None
        config_used: Dict[str, Any] = {}
        error: Optional[str] = None

        logs: Dict[str, Any] = {
            "stage": "start",
            "requested_model": model_name,
            "sdk": self.get_sdk_debug_info(),
        }

        # Choose a single best-supported path based on installed SDKs
        try:
            if self._client is not None and hasattr(self._client, "images") and hasattr(self._client.images, "generate"):
                # New google-genai Images API
                used_model = model_name or "imagen-3.5-generate-002"
                used_path = "client.images.generate"
                config_used = {"model": used_model, "prompt": prompt}
                print(
                    f"[Image Debug] sdk=google-genai method={used_path} model={used_model} config={{keys:{list(config_used.keys())}}}"
                )
                result = self._client.images.generate(model=used_model, prompt=prompt)
            elif self._legacy_genai is not None:
                # Legacy google-generativeai with image support
                # Avoid generate_content with image mime; only use generate_image if available
                used_model = model_name or "imagen-3.5"
                model = self._legacy_genai.GenerativeModel(used_model)
                if not hasattr(model, "generate_image"):
                    raise RuntimeError(
                        "Legacy SDK available but generate_image is not supported on this model."
                    )
                used_path = "GenerativeModel.generate_image"
                config_used = {"model": used_model, "prompt": prompt}
                print(
                    f"[Image Debug] sdk=google-generativeai method={used_path} model={used_model} config={{keys:{list(config_used.keys())}}}"
                )
                result = model.generate_image(prompt=prompt)
            else:
                raise RuntimeError(
                    "No compatible image-generation path available. Install/update google-genai with Images API support."
                )
        except Exception as e:
            error = str(e)
            logs["error"] = error
            result = None

        # Inspect and log response shape
        inspection = self._inspect_image_response(result) if result is not None else {"error": error}
        try:
            print(
                "[Image Debug] response=",
                json.dumps(
                    {
                        "response_type": inspection.get("response_type"),
                        "attributes": inspection.get("attributes"),
                        "found": inspection.get("found"),
                    },
                    default=str,
                ),
            )
        except Exception:
            pass

        # Attempt to extract and save bytes
        image_bytes = self._extract_image_bytes(result) if result is not None else None
        saved_path: Optional[str] = None
        if image_bytes:
            try:
                with open(out_path, "wb") as f:
                    f.write(image_bytes)
                saved_path = out_path
            except Exception as e:
                logs["save_error"] = str(e)
        else:
            # No image bytes produced; write a fallback report for visibility.
            details = {
                "prompt": prompt,
                "attempted_method": used_path,
                "used_model": used_model,
                "reason": error or "image bytes not found in response",
            }
            self._write_report(
                kind="image",
                out_path=out_path,
                message=(
                    "Image generation did not produce PNG bytes. Either the installed SDK lacks image support "
                    "or the selected method/model is incompatible."
                ),
                details=details,
            )

        finfo = _file_info(out_path)

        if state is not None and state_attr and finfo["exists"]:
            try:
                # Support dict or attribute state containers
                if isinstance(state, dict):
                    media = state.setdefault("media", {})
                    media[state_attr] = out_path
                else:
                    media = getattr(state, "media", None)
                    if media is None:
                        setattr(state, "media", type("Media", (), {})())
                        media = getattr(state, "media")
                    setattr(media, state_attr, out_path)
            except Exception:
                pass

        meta = {
            "inspection": inspection,
            "file": finfo,
            "logs": {
                **logs,
                "used_model": used_model,
                "used_path": used_path,
                "config": config_used,
            },
        }
        return (saved_path if finfo["exists"] else None, meta)

    # ---------- VIDEO GENERATION (VEO 3.1) ----------
    def _try_download(self, url: str) -> Optional[bytes]:
        try:
            import requests  # type: ignore

            r = requests.get(url, timeout=60)
            if r.ok:
                return r.content
        except Exception:
            return None
        return None

    def _extract_video_artifacts(self, op: Any) -> Dict[str, Any]:
        out: Dict[str, Any] = {"urls": [], "bytes": None}
        try:
            res = getattr(op, "result", None)
            if callable(res):
                res = res()
            if res is None:
                res = getattr(op, "response", None)

            # Common shapes
            if res is not None:
                if hasattr(res, "videos") and res.videos:
                    vids = res.videos
                    # Prefer first
                    v0 = vids[0]
                    if hasattr(v0, "bytes") and v0.bytes:
                        out["bytes"] = v0.bytes
                    if hasattr(v0, "uri") and v0.uri:
                        out["urls"].append(v0.uri)

                # files list with uri
                if hasattr(res, "files") and res.files:
                    for f in res.files:
                        if hasattr(f, "uri") and f.uri:
                            out["urls"].append(f.uri)

                if hasattr(res, "uri") and res.uri:
                    out["urls"].append(res.uri)
        except Exception:
            pass
        return out

    def generate_video(
        self,
        prompt: str,
        out_path: str,
        model_name: str = "veo-3.1",
        poll_interval: float = 5.0,
        timeout_seconds: int = 900,
        state: Optional[Any] = None,
    ) -> Tuple[Optional[str], Dict[str, Any]]:
        # Pre-generation debug logging
        # Keep preflight logs minimal; callers will print summaries
        try:
            if state is not None:
                prof = getattr(state, "profile", None) if hasattr(state, "profile") else None
                if prof is not None:
                    _ = (
                        getattr(prof, "bride_name", None),
                        getattr(prof, "groom_name", None),
                        getattr(prof, "destination", None),
                        getattr(prof, "wedding_dates", None),
                    )
            _ = str(prompt)[:200]
        except Exception:
            pass
        _ensure_dir(out_path)
        # Capability inspection
        caps = {
            "client_models_generate_video": bool(
                self._client is not None
                and hasattr(self._client, "models")
                and hasattr(getattr(self._client, "models"), "generate_video")
            ),
            "client_videos_generate": bool(
                self._client is not None
                and hasattr(self._client, "videos")
                and hasattr(getattr(self._client, "videos"), "generate")
            ),
            "legacy_generate_video": bool(
                self._legacy_genai is not None
            ),
        }

        logs: Dict[str, Any] = {
            "stage": "start",
            "model": model_name,
            "sdk": self.get_sdk_debug_info(),
            "capabilities": caps,
        }
        status: str = "init"
        saved_path: Optional[str] = None
        error: Optional[str] = None

        try:
            op = None
            used_path = None
            audio_kwargs_used = None
            audio_kw_candidates = [
                {"include_audio": True},
                {"enable_audio": True},
                {"background_audio": "native"},
                {"audio": "background"},
                {"audio": {"mode": "background", "style": "romantic wedding"}},
                {"soundtrack": {"enable": True, "style": "romantic wedding"}},
            ]

            # Prefer new google-genai client
            if self._client is not None:
                # Path A: direct models.generate_video if available
                if hasattr(self._client, "models") and hasattr(self._client.models, "generate_video"):
                    # Attempt to include audio-related kwargs if the SDK supports them
                    for ak in audio_kw_candidates:
                        try:
                            op = self._client.models.generate_video(model=model_name, prompt=prompt, **ak)
                            audio_kwargs_used = ak
                            break
                        except TypeError:
                            continue
                        except Exception:
                            continue
                    if op is None:
                        op = self._client.models.generate_video(model=model_name, prompt=prompt)
                    used_path = "client.models.generate_video"
                # Path B: some SDKs expose videos.generate
                elif hasattr(self._client, "videos") and hasattr(self._client.videos, "generate"):
                    for ak in audio_kw_candidates:
                        try:
                            op = self._client.videos.generate(model=model_name, prompt=prompt, **ak)
                            audio_kwargs_used = ak
                            break
                        except TypeError:
                            continue
                        except Exception:
                            continue
                    if op is None:
                        op = self._client.videos.generate(model=model_name, prompt=prompt)
                    used_path = "client.videos.generate"

            # Optional fallback to legacy SDK only if new path not available
            if op is None and self._legacy_genai is not None:
                print(f"[Video] Using SDK=google-generativeai path=GenerativeModel.generate_video model={model_name}")
                model = self._legacy_genai.GenerativeModel(model_name)
                if not hasattr(model, "generate_video"):
                    raise RuntimeError(
                        "Model does not support generate_video on google-generativeai; need Veo 3.1"
                    )
                # Try audio kwargs on legacy path as well
                for ak in audio_kw_candidates:
                    try:
                        op = model.generate_video(prompt=prompt, **ak)
                        audio_kwargs_used = ak
                        break
                    except TypeError:
                        continue
                    except Exception:
                        continue
                if op is None:
                    op = model.generate_video(prompt=prompt)
                used_path = "GenerativeModel.generate_video"

            if op is None:
                raise RuntimeError(
                    "Video generation path not available in installed SDKs. Install/update google-genai with Veo support."
                )
            status = "submitted"
            start = time.time()
            # Poll until complete
            while True:
                done = False
                try:
                    if hasattr(op, "done"):
                        done = bool(getattr(op, "done"))
                    elif hasattr(op, "status"):
                        done = str(getattr(op, "status")).lower() in {"succeeded", "completed", "done"}
                    else:
                        # Try calling .result() non-blocking
                        getattr(op, "result")()
                        done = True
                except Exception:
                    pass

                if done:
                    status = "completed"
                    break
                if time.time() - start > timeout_seconds:
                    status = "timeout"
                    break
                time.sleep(poll_interval)

            artifacts = self._extract_video_artifacts(op)
            logs["artifacts"] = artifacts
            logs["audio_kwargs_used"] = audio_kwargs_used

            video_bytes: Optional[bytes] = artifacts.get("bytes")
            if not video_bytes and artifacts.get("urls"):
                for u in artifacts["urls"]:
                    if isinstance(u, str) and u.startswith("http"):
                        video_bytes = self._try_download(u)
                        if video_bytes:
                            break

            if video_bytes:
                with open(out_path, "wb") as f:
                    f.write(video_bytes)
                saved_path = out_path
                status = "generated"
            else:
                status = status if status != "completed" else "no-bytes"
                if not error:
                    # Provide an explicit reason for callers
                    error = "no video bytes or downloadable URLs returned"
        except Exception as e:
            error = str(e)
            logs["error"] = error
            # Write a fallback report with actionable guidance
            self._write_report(
                kind="video",
                out_path=out_path,
                message=(
                    "Video generation failed or path unavailable. Ensure google-genai is installed and supports Veo 3.1."
                ),
                details={
                    "prompt": prompt,
                    "model": model_name,
                    "error": error,
                },
            )

        finfo = _file_info(out_path)
        # Do not print here; expose in return for a single summary at top level

        if state is not None:
            try:
                if isinstance(state, dict):
                    media = state.setdefault("media", {})
                    media["teaser_video_path"] = out_path if finfo["exists"] else None
                    media["teaser_video_status"] = status
                    # Persist the prompt for traceability
                    media["teaser_video_prompt"] = prompt
                    if not finfo["exists"] and error:
                        media["teaser_video_error"] = error
                else:
                    media = getattr(state, "media", None)
                    if media is None:
                        setattr(state, "media", type("Media", (), {})())
                        media = getattr(state, "media")
                    setattr(media, "teaser_video_path", out_path if finfo["exists"] else None)
                    setattr(media, "teaser_video_status", status)
                    try:
                        setattr(media, "teaser_video_prompt", prompt)
                    except Exception:
                        pass
                    if not finfo["exists"] and error:
                        try:
                            setattr(media, "teaser_video_error", error)
                        except Exception:
                            pass
            except Exception:
                pass

        # If no explicit audio kwargs were used, add a clear note for callers
        try:
            if logs.get("audio_kwargs_used") is None:
                logs["audio_note"] = (
                    "No explicit audio parameter accepted by SDK; relying on prompt language to include native background audio."
                )
        except Exception:
            pass

        return (saved_path if finfo["exists"] else None, {"status": status, "file": finfo, "logs": logs, "error": error})
