from __future__ import annotations

import os
from typing import Optional, Tuple

from dotenv import load_dotenv


# Load environment variables from a local .env if present (no-op if missing)
load_dotenv()


# Centralized default Gemini text model used across the app (e.g., Maps-grounded
# hotel recommendations and generic text tasks). Note: the previous default
# "gemini-2.0-flash" is no longer available to new users; use this instead.
DEFAULT_GEMINI_TEXT_MODEL = "gemini-2.5-flash"


def get_env(name: str, required: bool = False) -> Optional[str]:
    """Return an environment variable, optionally enforcing presence.

    Args:
        name: The environment variable name.
        required: If True, raise ValueError when missing.

    Returns:
        The environment variable value or None.
    """
    val = os.getenv(name)
    if required and (val is None or val == ""):
        raise ValueError(f"Missing required environment variable: {name}")
    return val


_gemini_key_debug_logged = False


def _mask_key(value: str) -> str:
    try:
        v = value.strip()
        if len(v) <= 6:
            return "***"
        return f"{v[:3]}***{v[-3:]}"
    except Exception:
        return "***"


def _pick_first_env(names: Tuple[str, ...]) -> Tuple[Optional[str], Optional[str]]:
    for n in names:
        v = os.getenv(n)
        if v is not None and v.strip() != "":
            return v.strip(), n
    return None, None


def get_gemini_api_key(required: bool = True) -> Optional[str]:
    """Resolve the Google Gemini API key using common variable names.

    Precedence:
    - GEMINI_API_KEY
    - GOOGLE_API_KEY
    - GOOGLE_APIKEY

    Prints a masked debug message once indicating which variable name was used.
    If `required` is True and nothing is found, raises a clean ValueError.
    """
    global _gemini_key_debug_logged
    key, used_name = _pick_first_env(("GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_APIKEY"))

    if not _gemini_key_debug_logged:
        if key:
            print(f"[config] Gemini API key loaded from {used_name}: {_mask_key(key)}")
        else:
            print(
                "[config] No Gemini API key found (checked: GEMINI_API_KEY, GOOGLE_API_KEY, GOOGLE_APIKEY)."
            )
        _gemini_key_debug_logged = True

    if required and (key is None or key == ""):
        raise ValueError(
            "No Gemini API key found. Set GEMINI_API_KEY (or GOOGLE_API_KEY) in your .env."
        )
    return key
