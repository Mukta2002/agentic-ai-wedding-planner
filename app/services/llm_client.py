from __future__ import annotations

import os

from dotenv import load_dotenv
from google import genai
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from typing import Callable, TypeVar
import time


class LLMClient:
    """Low-level Google GenAI client wrapper.

    Purpose:
    - Central place to load `GEMINI_API_KEY` from `.env` and construct the
      underlying google-genai `Client`.
    - Keeps a minimal surface area so higher-level routers can compose
      specialized calls (text, embeddings, image, tts, video) as needed.

    Notes:
    - Default text model is `gemini-2.5-flash` for fast, general text tasks.
    - Agents should not instantiate this directly; they should depend on a
      centralized router. This class remains importable for legacy code and
      tests and provides `generate_text` for compatibility.
    """

    def __init__(self, model: str | None = None, timeout_seconds: float = 20.0) -> None:
        # Ensure environment variables from .env are available
        try:
            load_dotenv()  # no-op if .env is missing
        except Exception:
            # Proceed even if dotenv is unavailable; env may already be set
            pass

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not set. Add it to your .env or environment."
            )

        # Keep a default text model for legacy/compat compatibility.
        self.model = model or "gemini-2.5-flash"
        self.client = genai.Client(api_key=api_key)
        self.timeout_seconds = timeout_seconds

    def _with_timeout(self, fn: Callable[[], object], timeout: float | None = None):
        to = timeout if timeout is not None else self.timeout_seconds
        with ThreadPoolExecutor(max_workers=1) as ex:
            fut = ex.submit(fn)
            return fut.result(timeout=to)

    def generate_text(self, prompt: str) -> str:
        """Generate text from Gemini and return the response text.

        Args:
            prompt: The input prompt string.
        Returns:
            The model's textual response.
        """
        print(f"[LLMClient] generate_text -> model={self.model}")
        start = time.time()
        def _call():
            return self.client.models.generate_content(
                model=self.model,
                contents=prompt,
            )
        try:
            resp = self._with_timeout(_call)
        except FuturesTimeout:
            raise TimeoutError(f"LLMClient.generate_text timed out after {self.timeout_seconds}s")
        finally:
            elapsed = time.time() - start
            print(f"[LLMClient] generate_text completed in {elapsed:.2f}s")
        # google-genai responses expose a `.text` convenience property
        text = getattr(resp, "text", None)
        if text is None:
            # Fallback: stringify the response to avoid returning placeholders
            text = str(resp)
        return text.strip()

    # Backwards compatibility: route any existing calls through the real model
    def generate(self, prompt: str) -> str:
        return self.generate_text(prompt)
