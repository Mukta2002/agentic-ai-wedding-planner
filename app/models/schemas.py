from __future__ import annotations

from pydantic import BaseModel
from typing import List, Optional


class CeremonyPlanItem(BaseModel):
    """Structured details for each wedding ceremony/function.

    Minimal additive schema kept independent from logistics.event_schedule.
    """
    name: str
    event_date: str  # exact date (from wedding_dates) or Day 1/2/3 label
    time_of_day: Optional[str] = None  # morning/afternoon/evening or specific time
    mood: Optional[str] = None
    palette: Optional[List[str]] = None
    dress_code: Optional[str] = None
    guest_note: Optional[str] = None
    include_in_teaser: bool = True
    include_in_style_guide: bool = True


class WeddingProfile(BaseModel):
    bride_name: str
    groom_name: str
    destination: str
    guest_count: int
    budget: float
    wedding_dates: List[str]
    # Added for intake compatibility without breaking existing fields
    currency: str = "INR"
    wedding_place: Optional[str] = None
    wedding_budget: Optional[float] = None
    # Optional fields to steer hotel recommendation retries (minimal, additive)
    accommodation_budget_share: Optional[float] = None  # e.g., 0.35 means 35% of total budget
    selected_nights_override: Optional[int] = None      # if provided, override nights estimate
    revised_guest_count: Optional[int] = None           # if provided, override guest count for rooms
    prefer_budget_hotels: Optional[bool] = None         # if True, bias Gemini prompt toward budget-conscious options
    # Confirmed breakdown from interactive step (category -> {percentage, amount})
    confirmed_budget_breakdown: Optional[dict] = None
    # ---- Creative preferences (minimal additive fields) ----
    # Logo
    logo_style: Optional[str] = None                   # minimal / royal / floral / modern / traditional / monogram
    logo_colors: Optional[List[str]] = None            # e.g., ["ivory", "gold", "emerald"]
    logo_text_preference: Optional[str] = None         # "initials" or "full names"
    logo_motif: Optional[str] = None                   # lotus / peacock / palace / mandala / etc.
    # Added richer logo fields (additive)
    logo_text_mode: Optional[str] = None               # same as text_preference, preserved for clarity
    logo_palette: Optional[List[str]] = None           # preferred palette names for logo
    logo_mood: Optional[str] = None                    # elegant / bold / regal / soft / contemporary
    # Additional logo intent controls (additive)
    logo_feel: Optional[str] = None                   # romantic / regal / editorial / floral / timeless
    logo_include_destination_symbol: Optional[bool] = None  # include symbolic elements from destination
    logo_gender_balance: Optional[str] = None         # feminine / balanced / gender-neutral
    logo_detailing: Optional[str] = None              # fine-line / bold ornamental
    logo_hidden_motifs: Optional[List[str]] = None    # e.g., ["elephant", "lotus", "peacock", "palace arch", "leaves"]
    # Invite
    invite_style: Optional[str] = None                 # royal / modern / pastel / floral / traditional / luxury
    invite_colors: Optional[List[str]] = None          # e.g., ["blush", "sage", "gold"]
    include_venue_details: Optional[bool] = None
    include_rsvp: Optional[bool] = None
    invite_vibe: Optional[str] = None                  # format/vibe, e.g., "minimal luxe, vertical single card"
    # Added richer invite fields (additive)
    invite_theme: Optional[str] = None                 # royal / floral / pastel / heritage / palace / modern luxury
    invite_background_scene: Optional[str] = None      # lake palace / sunset / garden / heritage architecture / abstract watercolor / no scene
    invite_palette: Optional[List[str]] = None         # explicit palette for invite art
    invite_mood: Optional[str] = None                  # grand & traditional vs soft & elegant
    invite_floral_style: Optional[str] = None          # floral elements description or none
    invite_frame_style: Optional[str] = None           # palace/arch/jharokha framing preference
    invite_layout_type: Optional[str] = None           # main ceremony card vs multi-event style
    # Invite wording preferences (additive)
    invite_wording_style: Optional[str] = None         # formal / warm / royal / modern elegant
    invite_together_with_families: Optional[bool] = None
    invite_include_short_blessing: Optional[bool] = None
    invite_invitation_phrase: Optional[str] = None     # request the honor of your presence / cordially invite you / invite you to celebrate
    invite_rsvp_sentence_style: Optional[str] = None   # short / label
    # Context captured from hotel recommendations (optional, if user selected)
    selected_hotel: Optional[str] = None
    # Teaser preferences (additive, used by teaser prompt)
    teaser_style: Optional[str] = None                 # royal / elegant / cinematic / editorial / modern subtle / traditional luxe
    teaser_pacing: Optional[str] = None                # slow dreamy / balanced / energetic
    teaser_music_vibe: Optional[str] = None            # orchestral / soft instrumental / celebratory / regal
    teaser_feel: Optional[str] = None                  # palace-luxury / intimate-romantic / fashion-forward
    teaser_must_show: Optional[str] = None             # free text: ceremonies or moments to include
    teaser_names_timing: Optional[str] = None          # end-only / throughout / early reveal
    teaser_ending_text_style: Optional[str] = None     # minimal elegant / grand royal / cinematic title card
    # Ceremony plan (additive, used by teaser/style guide)
    ceremonies: Optional[List[CeremonyPlanItem]] = None


class CreativePlan(BaseModel):
    theme_name: str
    theme_description: str
    color_palette: List[str]
    hashtags: List[str]
    invitation_text: str
    guest_style_guide: str
    invite_design_prompt: str


class LogisticsPlan(BaseModel):
    confirmed_guest_count: int
    pending_guest_count: int
    declined_guest_count: int
    catering_headcount: int
    room_allocation: List[dict]
    event_schedule: List[dict]
    logistics_summary: str


class DesignDirectionSpec(BaseModel):
    """Single source-of-truth for visual direction across all artifacts.

    Used by invite images, style guide PDFs, logo/monogram, and teaser video.
    Keeps fields compact and explicit to enable deterministic downstream prompts.
    """

    visual_style_name: str
    mood_keywords: List[str]
    palette_names: List[str]
    palette_hex: List[str]
    motifs: List[str]
    typography_direction: str
    logo_direction: str
    invite_art_direction: str
    wardrobe_art_direction: str
    video_art_direction: str
    luxury_level: str
    destination_story: str


class BudgetBreakdown(BaseModel):
    total_budget: float
    currency: str
    guest_count: int
    venue_cost: float
    catering_cost: float
    decor_cost: float
    accommodation_cost: float
    photography_cost: float
    entertainment_cost: float
    misc_cost: float
    total_estimated: float
    remaining_balance: float
    budget_summary: str


class WeddingState(BaseModel):
    profile: WeddingProfile
    creative: Optional[CreativePlan] = None
    logistics: Optional[LogisticsPlan] = None
    financial: Optional[BudgetBreakdown] = None
    # Design direction drives downstream visual/media generation
    design_spec: Optional[DesignDirectionSpec] = None
    # Optional media artifacts generated after planning
    media: Optional["MediaArtifacts"] = None
    state_status: str
    last_updated: str


class Guest(BaseModel):
    name: str
    email: str | None = None
    group: str | None = None


class Room(BaseModel):
    room_id: str
    capacity: int


class BudgetItem(BaseModel):
    item: str
    cost: float
    category: str | None = None


class MediaArtifacts(BaseModel):
    """Paths/prompts for generated media.

    Created in a separate media step so the planning pipeline remains runnable
    even without image/video APIs. All fields are optional to avoid breaking
    existing JSON/CSV/state workflows.
    """

    logo_image_path: str | None = None
    invite_image_path: str | None = None
    style_guide_pdf_path: str | None = None
    teaser_video_prompt: str | None = None
    teaser_video_status: str | None = None
    teaser_video_metadata_path: str | None = None
    # Direction for soundtrack selection (non-copyrighted guidance only)
    soundtrack_direction: str | None = None


class ConfirmedCreativePayload(BaseModel):
    """Minimal, confirmed payload used to strictly ground logo/invite.

    Only includes fields that are factual or explicitly confirmed by the user.
    Used to ensure the final invite text is programmatically rendered without drift.
    """

    # Core couple + event
    bride_name: str
    groom_name: str
    initials: str
    wedding_dates: List[str]
    wedding_place: str
    selected_hotel: Optional[str] = None

    # Logo prefs
    logo_style: Optional[str] = None
    logo_colors: Optional[List[str]] = None
    logo_text_preference: Optional[str] = None  # "initials" or "full names"
    logo_motif: Optional[str] = None
    logo_text_mode: Optional[str] = None
    logo_palette: Optional[List[str]] = None
    logo_mood: Optional[str] = None

    # Invite prefs
    invite_style: Optional[str] = None
    invite_colors: Optional[List[str]] = None
    invite_vibe: Optional[str] = None
    include_rsvp: Optional[bool] = None
    include_venue_details: Optional[bool] = None
    invite_theme: Optional[str] = None
    invite_background_scene: Optional[str] = None
    invite_palette: Optional[List[str]] = None
    invite_mood: Optional[str] = None
    invite_floral_style: Optional[str] = None
    invite_frame_style: Optional[str] = None
    invite_layout_type: Optional[str] = None
    # Invite wording (for grounded text overlay)
    invite_wording_style: Optional[str] = None
    invite_together_with_families: Optional[bool] = None
    invite_include_short_blessing: Optional[bool] = None
    invite_invitation_phrase: Optional[str] = None
    invite_rsvp_sentence_style: Optional[str] = None
    # Optional compact ceremony summary for invite multi-event block
    ceremony_summary_lines: Optional[List[str]] = None
