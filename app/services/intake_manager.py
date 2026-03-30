from __future__ import annotations

from typing import List

from app.models.schemas import WeddingProfile


class IntakeManager:
    """Interactive CLI intake for core wedding details.

    Keeps prompts simple and robust with basic validation and re-prompts.
    Produces a populated WeddingProfile, preserving existing field names while
    also setting newly added aliases for compatibility (wedding_place, wedding_budget).
    """

    def _prompt_nonempty(self, label: str) -> str:
        while True:
            value = input(f"{label}: ").strip()
            if value:
                return value
            print("Please enter a value.")

    def _prompt_int(self, label: str, min_value: int = 0) -> int:
        while True:
            raw = input(f"{label}: ").strip()
            try:
                num = int(raw.replace(",", "").strip())
                if num >= min_value:
                    return num
                print(f"Please enter a number >= {min_value}.")
            except Exception:
                print("Please enter a whole number (e.g., 150).")

    def _prompt_budget_float(self, label: str) -> float:
        """Parse a budget like '10,00,000' or '1000000' or '1,000,000.50'."""
        while True:
            raw = input(f"{label}: ").strip()
            cleaned = raw.replace(",", "").replace("₹", "").replace("$", "").strip()
            try:
                return float(cleaned)
            except Exception:
                print("Please enter a numeric amount (e.g., 1000000).")

    def _prompt_dates(self) -> List[str]:
        """Ask for comma-separated dates; light validation only (non-empty)."""
        while True:
            raw = input("Date(s) of wedding (comma-separated, e.g., 2026-12-10, 2026-12-11): ").strip()
            parts = [p.strip() for p in raw.split(",") if p.strip()]
            if parts:
                return parts
            print("Please enter at least one date.")

    def collect_basic_details(self) -> WeddingProfile:
        """Collect and return a populated WeddingProfile."""
        bride = self._prompt_nonempty("Name of bride")
        groom = self._prompt_nonempty("Name of groom")
        place = self._prompt_nonempty("Place of wedding")
        dates = self._prompt_dates()
        budget = self._prompt_budget_float("Total budget of wedding")
        guests = self._prompt_int("Total guests anticipated", min_value=0)

        # Construct using existing canonical fields for maximum compatibility.
        profile = WeddingProfile(
            bride_name=bride,
            groom_name=groom,
            destination=place,
            guest_count=guests,
            budget=budget,
            wedding_dates=dates,
        )

        # Populate added/alias fields to satisfy the intake requirement.
        try:
            profile.wedding_place = place  # type: ignore[attr-defined]
        except Exception:
            pass
        try:
            profile.wedding_budget = float(budget)  # type: ignore[attr-defined]
        except Exception:
            pass

        # Currency defaults to INR via schema; no prompt yet to keep flow minimal.
        return profile

    # ---- Additive creative preference questions ----
    def collect_logo_preferences(self, profile: WeddingProfile) -> None:
        """Ask a short sequence of logo preferences and store on profile."""
        try:
            # If already populated, avoid asking again in the same run
            if any(
                getattr(profile, k, None)
                for k in (
                    "logo_style",
                    "logo_colors",
                    "logo_text_preference",
                    "logo_motif",
                    "logo_text_mode",
                    "logo_palette",
                    "logo_mood",
                    "logo_feel",
                    "logo_include_destination_symbol",
                    "logo_gender_balance",
                    "logo_detailing",
                    "logo_hidden_motifs",
                )
            ):
                print("\n===== Logo Preferences =====\nUsing previously provided values.")
                return
            print("\n===== Logo Preferences =====")
            style = input(
                "What logo style do you prefer? (minimal / royal / floral / monogram / traditional / modern): "
            ).strip()
            if style:
                profile.logo_style = style

            text_mode = input("Should the logo use initials or full names? ").strip().lower()
            if text_mode:
                profile.logo_text_mode = text_mode
                # keep compatibility with existing field
                profile.logo_text_preference = text_mode

            motif = input(
                "What motif would you like in the logo? (peacock / lotus / mandala / palace / floral / none): "
            ).strip()
            if motif:
                profile.logo_motif = motif

            palette_raw = input("What color palette should the logo use? (comma-separated): ").strip()
            if palette_raw:
                palette = [c.strip() for c in palette_raw.split(",") if c.strip()]
                if palette:
                    profile.logo_palette = palette
                    # keep compatibility with existing field name
                    profile.logo_colors = list(palette)

            mood = input("Should the logo feel elegant, bold, regal, soft, or contemporary? ").strip()
            if mood:
                profile.logo_mood = mood

            # Additive premium-intent questions
            feel = input(
                "Do you want the logo to feel more romantic, regal, editorial, floral, or timeless? "
            ).strip()
            if feel:
                profile.logo_feel = feel

            dest_sym = input(
                "Should it include symbolic elements from the wedding destination? (y/n): "
            ).strip().lower()
            if dest_sym in ("y", "yes"):
                profile.logo_include_destination_symbol = True
            elif dest_sym in ("n", "no"):
                profile.logo_include_destination_symbol = False

            gender = input(
                "Should it feel more feminine, balanced, or gender-neutral? "
            ).strip()
            if gender:
                profile.logo_gender_balance = gender

            detailing = input(
                "Do you want fine-line detailing or bold ornamental detailing? "
            ).strip()
            if detailing:
                profile.logo_detailing = detailing

            hidden = input(
                "Any hidden motifs? (e.g., elephant, lotus, peacock, palace arch, leaves; comma-separated or leave blank): "
            ).strip()
            if hidden:
                profile.logo_hidden_motifs = [h.strip() for h in hidden.split(",") if h.strip()]
        except Exception:
            # Keep flow resilient; skip on any input issues
            pass

    def collect_invite_preferences(self, profile: WeddingProfile) -> None:
        """Ask a short sequence of invite preferences and store on profile."""
        try:
            # If already populated, avoid asking again in the same run
            if any(
                getattr(profile, k, None)
                for k in (
                    "invite_style",
                    "invite_colors",
                    "invite_vibe",
                    "include_venue_details",
                    "include_rsvp",
                    "invite_theme",
                    "invite_background_scene",
                    "invite_palette",
                    "invite_mood",
                    "invite_floral_style",
                    "invite_frame_style",
                    "invite_layout_type",
                )
            ):
                print("\n===== Invite Preferences =====\nUsing previously provided values.")
                return
            print("\n===== Invite Preferences =====")
            style = input("What invite theme do you want? (royal / floral / pastel / heritage / palace / modern luxury): ").strip()
            if style:
                profile.invite_theme = style
                # keep compatibility
                profile.invite_style = style

            bg_scene = input(
                "What background scene do you prefer? (lake palace / sunset / garden / heritage architecture / abstract watercolor / no scene): "
            ).strip()
            if bg_scene:
                profile.invite_background_scene = bg_scene

            colors_raw = input("What colors should the invite use? (comma-separated): ").strip()
            if colors_raw:
                colors = [c.strip() for c in colors_raw.split(",") if c.strip()]
                if colors:
                    profile.invite_palette = colors
                    profile.invite_colors = list(colors)

            mood = input("Should the invite look more grand and traditional, or soft and elegant? ").strip()
            if mood:
                profile.invite_mood = mood

            floral = input("Do you want floral elements? If yes, what type? (or 'no'): ").strip()
            if floral:
                profile.invite_floral_style = floral

            frame = input("Do you want palace/arch/jharokha style framing? (yes/no or describe): ").strip()
            if frame:
                profile.invite_frame_style = frame

            include_venue = input("Should venue details be shown? (y/n): ").strip().lower()
            if include_venue in ("y", "yes"):
                profile.include_venue_details = True
            elif include_venue in ("n", "no"):
                profile.include_venue_details = False

            include_rsvp = input("Should RSVP details be shown? (y/n): ").strip().lower()
            if include_rsvp in ("y", "yes"):
                profile.include_rsvp = True
            elif include_rsvp in ("n", "no"):
                profile.include_rsvp = False

            layout = input(
                "Do you want one main ceremony card style or a multi-event invitation style? "
            ).strip()
            if layout:
                profile.invite_layout_type = layout

            # Optional: explicit format/vibe (kept for compatibility)
            vibe = input("(Optional) Invite format or vibe (e.g., minimal luxe vertical card): ").strip()
            if vibe:
                profile.invite_vibe = vibe
        except Exception:
            # Keep flow resilient; skip on any input issues
            pass

    def collect_invite_wording_preferences(self, profile: WeddingProfile) -> None:
        """Ask minimal questions so the invite reads like a real wedding invitation."""
        try:
            if any(
                getattr(profile, k, None)
                for k in (
                    "invite_wording_style",
                    "invite_together_with_families",
                    "invite_include_short_blessing",
                    "invite_invitation_phrase",
                    "invite_rsvp_sentence_style",
                )
            ):
                print("\n===== Invite Wording =====\nUsing previously provided values.")
                return

            print("\n===== Invite Wording =====")
            style = input(
                "What invite wording style do you prefer? (formal / warm / royal / modern elegant): "
            ).strip()
            if style:
                profile.invite_wording_style = style

            fam = input("Should it say 'Together with their families'? (y/n): ").strip().lower()
            if fam in ("y", "yes"):
                profile.invite_together_with_families = True
            elif fam in ("n", "no"):
                profile.invite_together_with_families = False

            bless = input("Include a short celebratory sentence or blessing line? (y/n): ").strip().lower()
            if bless in ("y", "yes"):
                profile.invite_include_short_blessing = True
            elif bless in ("n", "no"):
                profile.invite_include_short_blessing = False

            phrase = input(
                "Invitation phrase (request the honor of your presence / cordially invite you / invite you to celebrate): "
            ).strip()
            if phrase:
                profile.invite_invitation_phrase = phrase

            rsvp = input("RSVP style (short sentence / label-only): ").strip().lower()
            if rsvp.startswith("short"):
                profile.invite_rsvp_sentence_style = "short"
            elif rsvp in ("label", "label-only", "just rsvp"):
                profile.invite_rsvp_sentence_style = "label"
        except Exception:
            pass

    def collect_teaser_preferences(self, profile: WeddingProfile) -> None:
        """Ask only global teaser direction. Ceremony visuals are asked later per-ceremony."""
        try:
            print("\n===== Teaser Preferences (Global) =====")
            if not getattr(profile, "teaser_style", None):
                style = input(
                    "Overall teaser style (royal / elegant / cinematic / editorial / modern subtle / traditional luxe): "
                ).strip()
                if style:
                    profile.teaser_style = style

            if not getattr(profile, "teaser_pacing", None):
                pacing = input("Preferred pacing (slow dreamy / balanced / energetic): ").strip()
                if pacing:
                    profile.teaser_pacing = pacing

            if not getattr(profile, "teaser_music_vibe", None):
                mv = input("Music vibe (orchestral / soft instrumental / celebratory / regal): ").strip()
                if mv:
                    profile.teaser_music_vibe = mv

            if not getattr(profile, "teaser_feel", None):
                feel = input("Overall feel (palace-luxury / intimate-romantic / fashion-forward): ").strip()
                if feel:
                    profile.teaser_feel = feel

            if not getattr(profile, "teaser_names_timing", None):
                names_timing = input(
                    "Show names/dates only at end, or also earlier? (end-only / throughout / early reveal): "
                ).strip()
                if names_timing:
                    profile.teaser_names_timing = names_timing

            if not getattr(profile, "teaser_ending_text_style", None):
                ending = input(
                    "Preferred ending text style (minimal elegant / grand royal / cinematic title card): "
                ).strip()
                if ending:
                    profile.teaser_ending_text_style = ending

            if not getattr(profile, "teaser_type", None):
                tty = input("Teaser type (save-the-date / event teaser / cinematic wedding trailer): ").strip()
                if tty:
                    profile.teaser_type = tty
        except Exception:
            pass
