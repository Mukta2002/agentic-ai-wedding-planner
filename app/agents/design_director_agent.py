from __future__ import annotations

import json
import re
from typing import Any, Dict

from app.models.schemas import (
    WeddingProfile,
    CreativePlan,
    LogisticsPlan,
    DesignDirectionSpec,
)


class DesignDirectorAgent:
    """Produces a cohesive, luxury DesignDirectionSpec for visual artifacts.

    - Consumes WeddingProfile + CreativePlan + LogisticsPlan
    - Uses Gemini text generation via the provided router
    - Returns strictly structured DesignDirectionSpec with robust fallback
    """

    def __init__(self, router_or_llm) -> None:
        # Accept ModelRouter or any object exposing generate_text/generate_structured_json
        self.router = router_or_llm

    def generate_design_spec(
        self,
        profile: WeddingProfile,
        creative: CreativePlan,
        logistics: LogisticsPlan,
    ) -> DesignDirectionSpec:
        """Generate a highly structured design spec with strong prompting."""
        details = self._compose_context(profile, creative, logistics)
        instruction = (
            "You are a world-class wedding design director for luxury destination weddings. "
            "Design a cohesive, premium visual direction for invites, wardrobe/style guide, "
            "logo/monogram, and a short cinematic teaser video. Aim for: colorful, imaginative, "
            "premium destination aesthetics; cohesive visual storytelling; polished luxury feel; "
            "event-aware fashion direction tailored to a Goa celebration across: \n"
            "- Welcome Dinner & Sangeet\n- Wedding Ceremony\n- Reception\n\n"
            "Return ONLY valid JSON with exactly these fields (no commentary):\n"
            "- visual_style_name (string)\n"
            "- mood_keywords (array of 5-10 short words)\n"
            "- palette_names (array of 4-8 short color names)\n"
            "- palette_hex (array of 4-8 hex colors, like #D9C3A3)\n"
            "- motifs (array of 4-8 short visual motifs)\n"
            "- typography_direction (string; premium font families/feels)\n"
            "- logo_direction (string; monogram approach, lockups, texture)\n"
            "- invite_art_direction (string; composition, materials, embellishments)\n"
            "- wardrobe_art_direction (string; brief per event for guests/couple)\n"
            "- video_art_direction (string; teaser look, pacing, shots)\n"
            "- luxury_level (string; e.g., \"modern luxury resort\")\n"
            "- destination_story (string; how Goa is woven into visuals)\n"
        )
        prompt = f"{instruction}\n{details}\nReturn concise JSON matching the schema above."

        # Prefer structured JSON generation if available
        data: Dict[str, Any] | None = None
        try:
            if hasattr(self.router, "generate_structured_json"):
                data = self.router.generate_structured_json(prompt)
            else:
                raw = self.router.generate_text(prompt)
                data = self._extract_json(raw)
        except Exception:
            data = None

        spec = self._parse_spec_json(data, profile, creative, logistics)
        return spec

    # ---- Internal helpers ----
    def _compose_context(
        self, profile: WeddingProfile, creative: CreativePlan, logistics: LogisticsPlan
    ) -> str:
        couple = f"{profile.bride_name} & {profile.groom_name}"
        schedule = getattr(logistics, "event_schedule", []) or []
        schedule_str = ", ".join(
            [f"{e.get('event')} on {e.get('date')} {e.get('time')}" for e in schedule]
        )
        cp = creative
        context = (
            "Wedding Profile:\n"
            f"- Couple: {couple}\n"
            f"- Destination: {profile.destination}\n"
            f"- Guests: {profile.guest_count}\n"
            f"- Budget: {profile.budget}\n"
            f"- Dates: {', '.join(profile.wedding_dates)}\n\n"
            "Creative Plan:\n"
            f"- Theme: {cp.theme_name}\n"
            f"- Theme Description: {cp.theme_description}\n"
            f"- Color Palette: {', '.join(cp.color_palette)}\n"
            f"- Invite Prompt: {cp.invite_design_prompt}\n\n"
            "Logistics Events:\n"
            f"- {schedule_str}\n"
        )
        return context

    def _extract_json(self, text: str) -> Dict[str, Any]:
        try:
            return json.loads(text)
        except Exception:
            pass
        try:
            m = re.search(r"\{[\s\S]*\}", text)
            if m:
                return json.loads(m.group(0))
        except Exception:
            pass
        return {}

    def _parse_spec_json(
        self,
        data: Dict[str, Any] | None,
        profile: WeddingProfile,
        creative: CreativePlan,
        logistics: LogisticsPlan,
    ) -> DesignDirectionSpec:
        if not isinstance(data, dict) or not data:
            return self._fallback_spec(profile, creative, logistics)
        try:
            return DesignDirectionSpec(
                visual_style_name=str(data.get("visual_style_name", "Coastal Heritage Luxe")),
                mood_keywords=[str(x) for x in (data.get("mood_keywords") or [
                    "sunlit", "festive", "romantic", "opulent", "coastal", "heirloom"
                ])],
                palette_names=[str(x) for x in (data.get("palette_names") or [
                    "ivory", "coral", "seafoam", "sandalwood", "antique gold", "midnight"
                ])],
                palette_hex=[str(x) for x in (data.get("palette_hex") or [
                    "#F6F1E9", "#FF7F73", "#7EC8B1", "#C2A276", "#C8A951", "#0B2239"
                ])],
                motifs=[str(x) for x in (data.get("motifs") or [
                    "konkan florals", "shell inlay", "wave filigree", "brass lattice"
                ])],
                typography_direction=str(data.get("typography_direction", 
                    "High-contrast serif for headlines (Didone/classic), humanist sans for body; micro-kerning, spacious leading.")),
                logo_direction=str(data.get("logo_direction", 
                    "Interlocked monogram of initials with Goa shell/filigree accents; foil-stamped or debossed lockups.")),
                invite_art_direction=str(data.get("invite_art_direction", 
                    "Layered invite with textured ivory stock, antique-gold foil, blind deboss shell lattice, coral edge-paint; coastal botanical vignette.")),
                wardrobe_art_direction=str(data.get("wardrobe_art_direction", 
                    "Welcome Dinner & Sangeet: jewel-toned lehengas/kurta sets with mirrorwork; breezy fabrics, coral/teal accents. "
                    "Wedding Ceremony: ivory/sand with antique-gold zari; classic silhouettes, jasmine garlands. "
                    "Reception: midnight/navy with metallic sheen; sleek gowns/bandhgalas, minimal jewelry.")),
                video_art_direction=str(data.get("video_art_direction", 
                    "Golden-hour coastal establishing shots, slow-motion sangeet dance energy, intimate vows under swaying palms, "
                    "macro details of foil/patterns; orchestral-electronic score; 20-30s cinematic pacing.")),
                luxury_level=str(data.get("luxury_level", "modern luxury resort")),
                destination_story=str(data.get("destination_story", 
                    "Blends Goa's Portuguese mansions, shell craft, and Konkan botanicals with contemporary seaside minimalism.")),
            )
        except Exception:
            return self._fallback_spec(profile, creative, logistics)

    def _fallback_spec(
        self, profile: WeddingProfile, creative: CreativePlan, logistics: LogisticsPlan
    ) -> DesignDirectionSpec:
        destination = (profile.destination or "Destination").strip()
        initials = (profile.bride_name[:1] + profile.groom_name[:1]).upper()
        return DesignDirectionSpec(
            visual_style_name=f"{destination} Coastal Heritage Luxe",
            mood_keywords=["sunlit", "festive", "romantic", "opulent", "coastal", "heirloom"],
            palette_names=["ivory", "coral", "seafoam", "sandalwood", "antique gold", "midnight"],
            palette_hex=["#F6F1E9", "#FF7F73", "#7EC8B1", "#C2A276", "#C8A951", "#0B2239"],
            motifs=["konkan florals", "shell inlay", "wave filigree", "brass lattice"],
            typography_direction=(
                "High-contrast serif for headlines (Didone/classic), humanist sans for body; micro-kerning, spacious leading."
            ),
            logo_direction=(
                f"Interlocked monogram '{initials}' with shell/filigree accents; foil-stamped or debossed lockups on textured stock."
            ),
            invite_art_direction=(
                "Layered invite with textured ivory stock, antique-gold foil, blind deboss shell lattice, coral edge-paint; coastal botanical vignette."
            ),
            wardrobe_art_direction=(
                "Welcome Dinner & Sangeet: jewel-toned lehengas/kurta sets with mirrorwork; breezy fabrics, coral/teal accents. "
                "Wedding Ceremony: ivory/sand with antique-gold zari; classic silhouettes, jasmine garlands. "
                "Reception: midnight/navy with metallic sheen; sleek gowns/bandhgalas, minimal jewelry."
            ),
            video_art_direction=(
                "Golden-hour coastal establishing shots, slow-motion sangeet dance energy, intimate vows under swaying palms, "
                "macro details of foil/patterns; orchestral-electronic score; 20-30s cinematic pacing."
            ),
            luxury_level="modern luxury resort",
            destination_story=(
                f"Blends {destination}'s heritage mansions, shell craft, and Konkan botanicals with contemporary seaside minimalism."
            ),
        )
