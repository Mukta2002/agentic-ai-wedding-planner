from __future__ import annotations

import os
from typing import Optional

from dotenv import load_dotenv


# Load environment variables from a local .env if present (no-op if missing)
load_dotenv()


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


def get_gemini_api_key(required: bool = True) -> Optional[str]:
    """Resolve the Google Gemini API key using common variable names.

    Precedence:
    - GEMINI_API_KEY
    - GOOGLE_API_KEY
    - GOOGLE_APIKEY

    If `required` is True and nothing is found, raises ValueError.
    """
    key = (
        os.getenv("GEMINI_API_KEY")
        or os.getenv("GOOGLE_API_KEY")
        or os.getenv("GOOGLE_APIKEY")
    )
    if required and (key is None or key == ""):
        raise ValueError("Missing required environment variable: GEMINI_API_KEY")
    return key

