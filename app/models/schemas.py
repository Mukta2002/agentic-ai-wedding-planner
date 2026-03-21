from __future__ import annotations

from pydantic import BaseModel
from typing import List, Optional


class WeddingProfile(BaseModel):
    bride_name: str
    groom_name: str
    destination: str
    guest_count: int
    budget: float
    wedding_dates: List[str]


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
