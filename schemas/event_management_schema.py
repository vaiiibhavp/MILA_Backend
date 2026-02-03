from pydantic import BaseModel, Field , field_validator
from typing import Optional, List
import re
from datetime import datetime , date ,time
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
    title: str
    banner_image_id: str

    badge: str

    description: str

    registration_until : str
    voting_starts: str
    voting_ends: str
    rules: List[str] = None

    start_date: str
    end_date: str
    
    judging_criteria: List[str] = None
    launch_time: str

    frequency: Optional[ContestFrequency] = None
    prize_distribution: PrizeDistribution

    cost_per_vote: int = Field(..., gt=0)
    max_votes_per_user: int = Field(..., gt=0)

    min_participant: int = Field(..., gt=0)
    max_participant: int = Field(..., gt=0)
    photos_per_participant: int = Field(..., gt=0)


class ContestUpdateSchema(BaseModel):
    title: Optional[str] = None
    banner_image_id: Optional[str] = None

    badge: str

    description: Optional[str] = None
    rules: Optional[List[str]] = None

    registration_until: Optional[str] = None
    voting_starts: Optional[str] = None
    voting_ends: Optional[str] = None

    start_date: Optional[str] = None
    end_date: Optional[str] = None

    judging_criteria: Optional[List[str]] = None

    launch_time: Optional[str] = None
    frequency: Optional[ContestFrequency] = None

    prize_distribution: Optional[PrizeDistributionUpdate] = None

    cost_per_vote: Optional[int] = Field(None, gt=0)
    max_votes_per_user: Optional[int] = Field(None, gt=0)

    min_participant: Optional[int] = Field(None, gt=0)
    max_participant: Optional[int] = Field(None, gt=0)

    photos_per_participant: Optional[int] = Field(None, gt=0)

    class Config:
        extra = "forbid"

