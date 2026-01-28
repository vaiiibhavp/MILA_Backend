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

CONTEST_TYPE_VISIBILITY_MAP = {
    ContestType.active: [
        ContestVisibility.upcoming.value,
        ContestVisibility.in_progress.value,
    ],
    ContestType.past: ContestVisibility.completed.value,
}

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
    contest_type: ContestType,
    pagination: StandardResultsSetPagination
):
    visibility_filter = CONTEST_TYPE_VISIBILITY_MAP[contest_type]

    if isinstance(visibility_filter, list):
        query = {
            "is_active": True,
            "visibility": {"$in": visibility_filter}
        }
    else:
        query = {
            "is_active": True,
            "visibility": visibility_filter
        }

    total = await contest_collection.count_documents(query)

    cursor = (
        contest_collection
        .find(query)
        .sort("created_at", -1)
    )

    if pagination.limit is not None:
        cursor = cursor.skip(pagination.skip).limit(pagination.limit)
        
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

        results.append(card.dict())

    return results, total

async def fetch_contest_by_id(contest_id: str):
    return await contest_collection.find_one(
        {"_id": ObjectId(contest_id), "is_active": True}
    )

async def fetch_active_contest_history(contest_id: str):
    return await contest_history_collection.find_one(
        {"contest_id": contest_id, "is_active": True}
    )


async def fetch_participant_avatars(contest_id, contest_history_id, limit=5):
    cursor = contest_participant_collection.find(
        {
            "contest_id": contest_id,
            "contest_history_id": contest_history_id
        }
    )

    seen_users = set()
    avatars = []

    async for p in cursor:
        if p["user_id"] in seen_users:
            continue

        avatar = await resolve_user_avatar(p["user_id"])
        if avatar:
            avatars.append(avatar)
            seen_users.add(p["user_id"])

        if len(avatars) == limit:
            break

    return avatars

async def fetch_current_standings(
    contest_id: str,
    contest_history
):
    if contest_history["status"] not in [
        ContestStatus.voting_started,
        ContestStatus.winner_announced
    ]:
        return []

    return await get_leaderboard(
        contest_id,
        str(contest_history["_id"])
    )


async def is_user_participant(user_id: str, contest_history_id: str):
    return await contest_participant_collection.find_one({
        "contest_history_id": contest_history_id,
        "user_id": user_id
    })

async def resolve_cta_state(contest, contest_history, current_user):
    user_id = str(current_user["_id"])

    if contest_history["status"] == ContestStatus.registration_open:
        already_participated = await contest_participant_collection.find_one({
            "contest_id": str(contest["_id"]),
            "user_id": user_id
        })

        if already_participated:
            return {
                "can_participate": False,
                "can_vote": False,
                "reason": "ALREADY_PARTICIPATED"
            }

        return {"can_participate": True, "can_vote": False}

    if contest_history["status"] == ContestStatus.voting_started:
        if await is_user_participant(user_id, str(contest_history["_id"])):
            return {
                "can_participate": False,
                "can_vote": False,
                "reason": "PARTICIPANT_CANNOT_VOTE"
            }

        return {"can_participate": False, "can_vote": True}

    return {"can_participate": False, "can_vote": False}

async def resolve_user_avatar(user_id: str) -> dict | None:
    onboarding = await onboarding_collection.find_one(
        {"user_id": user_id},
        {"profile_photo": 1, "selfie_image": 1}
    )

    file_id = (
        onboarding.get("profile_photo")
        or onboarding.get("selfie_image")
        if onboarding else None
    )

    if not file_id:
        return None

    file_doc = await file_collection.find_one(
        {"_id": ObjectId(file_id)},
        {"storage_key": 1, "storage_backend": 1}
    )

    if not file_doc:
        return None

    url = await generate_file_url(
        storage_key=file_doc["storage_key"],
        backend=file_doc["storage_backend"]
    )

    return {
        "user_id": user_id,
        "avatar_url": url
    }

async def get_leaderboard(
    contest_id: str,
    contest_history_id: str,
    limit: int = 3
):
    cursor = (
        contest_participant_collection
        .find(
            {
                "contest_id": contest_id,
                "contest_history_id": str(contest_history_id)
            }
        )
        .sort("total_votes", -1)
        .limit(limit)
    )

    leaderboard = []
    rank = 1

    async for participant in cursor:
        avatar = await resolve_user_avatar(participant["user_id"])

        leaderboard.append({
            "rank": rank,
            "user_id": participant["user_id"],
            "total_votes": participant.get("total_votes", 0),
            "avatar": avatar
        })
        rank += 1

    return leaderboard

async def fetch_contest_participants(
    contest_id: str,
    skip: int = 0,
    limit: Optional[int] = None
):
    cursor = contest_participant_collection.find(
        {
            "contest_id": contest_id,
            "is_deleted": {"$ne": True}
        }
    )

    # Apply pagination ONLY when page_size is provided
    if limit is not None:
        cursor = cursor.skip(skip).limit(limit)

    participants = []
    async for p in cursor:
        participants.append(p)

    return participants

async def is_user_already_participant(
    contest_id: str,
    contest_history_id: str,
    user_id: str
):
    return await contest_participant_collection.find_one({
        "contest_id": contest_id,
        "contest_history_id": contest_history_id,
        "user_id": user_id
    })

async def create_contest_participant(data: dict):
    result = await contest_participant_collection.insert_one(data)
    return str(result.inserted_id)

async def increment_participant_count(contest_history_id: str):
    await contest_history_collection.update_one(
        {"_id": ObjectId(contest_history_id)},
        {"$inc": {"total_participants": 1}}
    )

def resolve_badge(rank: int | None):
    if rank == 1:
        return {"type": "gold", "label": "Top 1"}
    if rank == 2:
        return {"type": "silver", "label": "Top 2"}
    if rank == 3:
        return {"type": "bronze", "label": "Top 3"}
    return None

async def get_participant_by_user(
    contest_id: str,
    contest_history_id: str,
    participant_user_id: str
):
    return await contest_participant_collection.find_one({
        "contest_id": contest_id,
        "contest_history_id": contest_history_id,
        "user_id": participant_user_id
    })

async def get_user_vote_count(
    contest_id: str,
    contest_history_id: str,
    voter_user_id: str
) -> int:
    return await contest_vote_collection.count_documents({
        "contest_id": contest_id,
        "contest_history_id": contest_history_id,
        "voter_user_id": voter_user_id
    })

async def has_user_voted_for_participant(
    contest_id: str,
    contest_history_id: str,
    participant_id: str,
    voter_user_id: str
):
    return await contest_vote_collection.find_one({
        "contest_id": contest_id,
        "contest_history_id": contest_history_id,
        "participant_id": participant_id,
        "voter_user_id": voter_user_id
    })

async def create_vote_entry(data: dict):
    await contest_vote_collection.insert_one(data)

async def increment_vote_counts(
    participant_id: ObjectId,
    contest_history_id: str
):
    await contest_participant_collection.update_one(
        {"_id": participant_id},
        {"$inc": {"total_votes": 1}}
    )

    await contest_history_collection.update_one(
        {"_id": ObjectId(contest_history_id)},
        {"$inc": {"total_votes": 1}}
    )
