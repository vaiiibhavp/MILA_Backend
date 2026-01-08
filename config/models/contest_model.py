from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from bson import ObjectId
from core.utils.core_enums import ContestFrequency
from config.models.onboarding_model import GenderEnum
from core.utils.core_enums import *
from config.db_config import contest_collection
from core.utils.pagination import pagination_params, StandardResultsSetPagination
from api.controller.files_controller import *
from schemas.contest_schema import *

class ContestModel(BaseModel):

    title: str
    description: Optional[str] = None
    rules_and_conditions: Optional[str] = None

    banner_file_id: str

    gender_allowed: List[GenderEnum] = []

    vote_cost: int = 25
    max_votes_per_user: int = 3

    max_participants: Optional[int] = None
    images_per_participant: int = 1

    prize_pool_description: Optional[str] = None
    prize_distribution: Optional[List[str]] = None  # ["Top 1", "Top 2", "Top 3"]

    frequency: Optional[ContestFrequency] = None  # weekly / bi-weekly / monthly / 3 months

    is_active: bool = True

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda v: v.isoformat()
        }

class ContestHistoryModel(BaseModel):

    contest_id: str  # reference to ContestModel

    status: ContestStatus  # registration_open / voting_started / winner_announced
    visibility: ContestVisibility  # upcoming / in_progress / completed

    registration_start: datetime
    registration_end: datetime

    voting_start: datetime
    voting_end: datetime

    cycle_key: str  # "2026-W06", "2026-02", "2026-Q1"
    cycle_type: Optional[str] = None  # weekly / monthly / yearly

    total_participants: int = 0
    total_votes: int = 0

    is_active: bool = True

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda v: v.isoformat()
        }

class ContestParticipantModel(BaseModel):
    contest_id: str
    contest_history_id: str
    user_id: str

    uploaded_file_ids: List[str]

    total_votes: int = 0
    rank: Optional[int] = None
    is_winner: bool = False
    winner_position: Optional[int] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)

class ContestVoteModel(BaseModel):
    contest_id: str
    contest_history_id: str
    participant_id: str

    voter_user_id: str
    vote_cost: int
    voted_at: datetime = Field(default_factory=datetime.utcnow)


async def fetch_active_contests():
    return contest_collection.find(
        {
            "is_active": True,
            "visibility": {
                "$in": [
                    ContestVisibility.upcoming.value,
                    ContestVisibility.in_progress.value
                ]
            }
        }
    ).sort("created_at", -1)


async def fetch_past_contests():
    return contest_collection.find(
        {
            "is_active": True,
            "visibility": ContestVisibility.completed.value
        }
    ).sort("created_at", -1)


async def get_contests_paginated(
    contest_type: str,
    pagination: StandardResultsSetPagination
):
    if contest_type == "active":
        query = {
            "is_active": True,
            "visibility": {"$in": ["upcoming", "in_progress"]}
        }
    else:
        query = {
            "is_active": True,
            "visibility": "completed"
        }

    total = await contest_collection.count_documents(query)

    cursor = (
        contest_collection
        .find(query)
        .sort("created_at", -1)
        .skip(pagination.skip)
        .limit(pagination.limit)
    )

    results = []

    async for contest in cursor:
        banner_url = await resolve_banner_url(contest.get("banner_file_id"))

        card = ContestCardResponse(
            contest_id=str(contest["_id"]),
            title=contest["title"],
            banner_url=banner_url,
            status=contest["status"],
            visibility=contest["visibility"],
            registration_end=contest["registration_end"],
            voting_end=contest["voting_end"],
            total_participants=contest.get("total_participants", 0),
            total_votes=contest.get("total_votes", 0),
            prize_pool_description=contest.get("prize_pool_description"),
            voting_start=contest.get("voting_start")
        )

        # Convert Pydantic → dict (THIS FIXES YOUR ERROR)
        results.append(card.dict())

    return results, total
