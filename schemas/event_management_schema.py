from pydantic import BaseModel, Field , field_validator
from typing import Optional, List
from datetime import datetime
from bson import ObjectId
from config.models.user_models import PyObjectId
from core.utils.core_enums import ContestFrequency ,ContestVisibility

class PrizeDistribution(BaseModel):
    first_place: int = Field(..., gt=0)
    second_place: int = Field(..., gt=0)
    third_place: int = Field(..., gt=0)

class PrizeDistributionUpdate(BaseModel):
    first_place: Optional[int] = Field(None, gt=0)
    second_place: Optional[int] = Field(None, gt=0)
    third_place: Optional[int] = Field(None, gt=0)



class ContestCreateSchema(BaseModel):
    title: str = Field(..., min_length=3)
    banner_image_id: str = Field(..., min_length=5)

    description: str = Field(..., min_length=5)
    rules: List[str] = Field(..., min_length=1)

    start_date: datetime
    end_date: datetime

    # Pydantic v2 uses pattern instead of regex
    launch_time: str = Field(..., pattern=r"^\d{2}:\d{2}$")

    frequency: ContestFrequency

    prize_distribution: PrizeDistribution

    cost_per_vote: int = Field(..., gt=0)
    max_votes_per_user: int = Field(..., gt=0)

    participant_limit: int = Field(..., gt=0)
    photos_per_participant: int = Field(..., gt=0)

    # ---------------- STRING SANITIZATION ----------------
    @field_validator("title", "banner_image_id", "description", "launch_time", mode="before")
    @classmethod
    def not_empty_string(cls, v: str):
        if not v or not str(v).strip():
            raise ValueError("Field cannot be empty")
        return v.strip()

    @field_validator("rules", mode="before")
    @classmethod
    def rules_not_empty(cls, v: List[str]):
        if not v or not isinstance(v, list):
            raise ValueError("Rules are required")

        cleaned = [r.strip() for r in v if r and r.strip()]

        if not cleaned:
            raise ValueError("Rules cannot be empty")

        return cleaned

    # ---------------- DATE LOGIC ----------------
    @field_validator("end_date")
    @classmethod
    def validate_dates(cls, end_date: datetime, info):
        start_date = info.data.get("start_date")
        if start_date and start_date >= end_date:
            raise ValueError("End date must be after start date")
        return end_date

class ContestUpdateSchema(BaseModel):
    title: Optional[str] = None
    banner_image_id: Optional[str] = None

    description: Optional[str] = None
    rules: Optional[List[str]] = None

    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    launch_time: Optional[str] = None

    frequency: Optional[ContestFrequency] = None

    prize_distribution: Optional[PrizeDistributionUpdate] = None

    cost_per_vote: Optional[int] = Field(None, gt=0)
    max_votes_per_user: Optional[int] = Field(None, gt=0)

    participant_limit: Optional[int] = Field(None, gt=0)
    photos_per_participant: Optional[int] = Field(None, gt=0)

    # =====================================================
    # STRING FIELD PROTECTION (BLOCK " " AND "")
    # =====================================================
    @field_validator(
        "title",
        "banner_image_id",
        "description",
        "launch_time",
        mode="before"
    )
    @classmethod
    def not_empty_string(cls, v):
        if v is None:
            return v  # allow missing fields in PATCH

        if not str(v).strip():
            raise ValueError("Field cannot be empty")

        return str(v).strip()

    # =====================================================
    # RULES LIST PROTECTION
    # =====================================================
    @field_validator("rules", mode="before")
    @classmethod
    def rules_not_empty(cls, v):
        if v is None:
            return v  # PATCH allows skipping field

        if not isinstance(v, list):
            raise ValueError("Rules must be a list")

        cleaned = [r.strip() for r in v if r and r.strip()]

        if not cleaned:
            raise ValueError("Rules cannot be empty")

        return cleaned

    # =====================================================
    # DATE LOGIC (PATCH SAFE)
    # =====================================================
    @field_validator("end_date")
    @classmethod
    def validate_dates(cls, end_date, info):
        start_date = info.data.get("start_date")

        if start_date and end_date and start_date >= end_date:
            raise ValueError("End date must be after start date")

        return end_date

    class Config:
        extra = "forbid"

