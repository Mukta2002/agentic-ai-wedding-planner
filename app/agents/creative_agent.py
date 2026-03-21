from __future__ import annotations

import json
import re
from typing import Any, Dict

from app.prompts.creative_prompts import THEME_PROMPT
from app.models.schemas import CreativePlan, WeddingProfile


class CreativeAgent:
    """Creative tasks use text generation by default.

    - Uses the centralized router/client for text generation.
    - Backwards compatible with any object exposing `generate_text`.
    - Can optionally request images via the router if available.
    """

    def __init__(self, router_or_llm) -> None:
        # Accept either ModelRouter or a legacy LLM-like with generate_text
        self.router = router_or_llm

    # ---- Structured creative plan generation ----
    def generate_creative_plan(self, profile: WeddingProfile) -> CreativePlan:
        """Generate a structured creative plan for the wedding.

        Instructs the model to return clean JSON with required fields.
        Provides a deterministic fallback if parsing fails.
        """
        couple_names = f"{profile.bride_name} & {profile.groom_name}"
        details = (
            "Wedding Profile:\n"
            f"- Bride: {profile.bride_name}\n"
            f"- Groom: {profile.groom_name}\n"
            f"- Destination: {profile.destination}\n"
            f"- Guest Count: {profile.guest_count}\n"
            f"- Budget: {profile.budget}\n"
            f"- Wedding Dates: {', '.join(profile.wedding_dates)}\n"
        )

        instruction = (
            "You are a wedding creative director. Based on the profile, craft a cohesive,"
            " tasteful concept suitable for modern couples. Return ONLY valid JSON with"
            " exactly these fields (no extra commentary):\n"
            "- theme_name (string)\n"
            "- theme_description (string)\n"
            "- color_palette (array of 3-6 short color names or hex codes)\n"
            "- hashtags (array of 4-8 short social hashtags without spaces)\n"
            "- invitation_text (string; 3-4 sentences; no specific addresses)\n"
            "- guest_style_guide (string; attire + tone in 2-3 sentences)\n"
            "- invite_design_prompt (string; clear visual prompt for a designer/model)\n"
        )

        prompt = (
            f"{instruction}\n\n{details}\n"
            f"Return concise, clean JSON with the fields above."
        )

        try:
            raw = self.router.generate_text(prompt)
            return self._parse_plan_json(raw, profile)
        except Exception:
            return self._fallback_plan(profile)

    # ---- Compatibility helpers (legacy tests) ----
    def suggest_theme(self, couple_names: str) -> str:
        """Suggest wedding theme ideas using text generation (compat)."""
        prompt = THEME_PROMPT.format(couple=couple_names)
        return self.router.generate_text(prompt)

    def generate_invitation_text(self, couple_names: str) -> str:
        """Generate invitation wording using text generation (compat)."""
        prompt = (
            f"Write a warm, elegant wedding invitation for {couple_names}. "
            "3-4 sentences, welcoming tone, no specific date/location, suitable for modern invitations."
        )
        return self.router.generate_text(prompt)

    # Optional media capability
    def generate_invitation_image(self, couple_names: str, output_path: str | None = None):
        """Generate an invitation/moodboard concept image via router if available."""
        visual_prompt = (
            f"Elegant wedding invitation for {couple_names}. Neutral palette, minimal "
            "serif typography, subtle floral accents, warm natural light, fine-grain paper mockup."
        )
        if hasattr(self.router, "generate_image"):
            return self.router.generate_image(visual_prompt, output_path=output_path)
        raise RuntimeError("Image generation not available on provided router.")

    # ---- Internal helpers ----
    def _parse_plan_json(self, text: str, profile: WeddingProfile) -> CreativePlan:
        """Attempt to parse the model response into CreativePlan with safety."""
        # Try direct parse first
        data: Dict[str, Any] | None = None
        try:
            data = json.loads(text)
        except Exception:
            pass

        if data is None:
            # Extract the first JSON object heuristically
            try:
                m = re.search(r"\{[\s\S]*\}", text)
                if m:
                    data = json.loads(m.group(0))
            except Exception:
                data = None

        if not isinstance(data, dict):
            return self._fallback_plan(profile)

        try:
            return CreativePlan(
                theme_name=str(data.get("theme_name", "Timeless Elegance")),
                theme_description=str(data.get("theme_description", "An elegant, modern celebration.")),
                color_palette=[str(x) for x in (data.get("color_palette") or ["ivory", "sage", "gold"])],
                hashtags=[str(x) for x in (data.get("hashtags") or ["#TimelessLove", "#ModernElegance"])],
                invitation_text=str(data.get("invitation_text", "You are warmly invited to celebrate.")),
                guest_style_guide=str(data.get("guest_style_guide", "Dress code: formal or cocktail.")),
                invite_design_prompt=str(
                    data.get(
                        "invite_design_prompt",
                        "Minimal serif typography, soft neutral palette, subtle floral emboss, premium paper mockup.",
                    )
                ),
            )
        except Exception:
            return self._fallback_plan(profile)

    def _fallback_plan(self, profile: WeddingProfile) -> CreativePlan:
        couple = f"{profile.bride_name} & {profile.groom_name}"
        destination = profile.destination or "your chosen destination"
        return CreativePlan(
            theme_name=f"Modern Elegance in {destination}",
            theme_description=(
                f"A refined, contemporary celebration for {couple} blending clean lines with soft textures, "
                f"subtle florals, and warm lighting inspired by {destination}."
            ),
            color_palette=["ivory", "champagne", "sage", "gold", "slate"],
            hashtags=["#ModernElegance", "#TimelessVows", f"#{profile.bride_name}{profile.groom_name}Wedding"],
            invitation_text=(
                f"Together with their families, {couple} invite you to share in their joy "
                f"as they celebrate their wedding. Your presence is the greatest gift."
            ),
            guest_style_guide=(
                "Dress code: formal or cocktail. Gentle neutrals and elegant silhouettes encouraged; "
                "comfortable shoes for evening dancing."
            ),
            invite_design_prompt=(
                "Minimal serif typography, soft ivory and champagne palette, subtle botanical line art, "
                "textured premium paper mockup, natural light, clean composition."
            ),
        )

