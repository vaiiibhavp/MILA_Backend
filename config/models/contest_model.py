from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from bson import ObjectId
from core.utils.core_enums import ContestFrequency
from config.models.onboarding_model import GenderEnum
from core.utils.core_enums import *
from config.db_config import contest_collection
from core.utils.leaderboard.leaderboard_helper import LeaderboardRedisHelper
from core.utils.pagination import pagination_params, StandardResultsSetPagination
from api.controller.files_controller import *
from schemas.contest_schema import *
from core.utils.helper import get_user_details, get_admin_id_by_email
from services.notification_service import send_notification, send_topic_notification
from core.utils.helper import unsubscribe_user_from_topic
from config.models.user_models import get_user_token_balance
from config.models.user_token_history_model import create_user_token_history
from schemas.user_token_history_schema import CreateTokenHistory

leaderboard_redis_helper = LeaderboardRedisHelper()

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

    contest_version:str # 1.0.0

    registration_start: datetime
    registration_end: datetime

    voting_start: datetime
    voting_end: datetime

    cycle_key: Optional[str] = None  # "2026-W06", "2026-02", "2026-Q1"
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

class ContestWinnerModel(BaseModel):
    contest_id: str
    contest_history_id: str

    participant_id: str
    user_id: str

    rank: int
    total_votes: int

    username: Optional[str] = None
    avatar_url: Optional[str] = None

    declared_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda v: v.isoformat()
        }

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

async def is_within_registration_period(contest: dict) -> bool:
    now = datetime.utcnow()

    start_date = contest.get("registration_start")
    registration_until = contest.get("registration_end")

    if not start_date or not registration_until:
        return False

    return start_date <= now <= registration_until

async def is_within_voting_period(contest_history) -> bool:
    now = datetime.utcnow()
    voting_starts = contest_history.get("voting_start")
    voting_ends = contest_history.get("voting_end")

    if not voting_starts or not voting_ends:
        return False

    return voting_starts <= now <= voting_ends

async def fetch_latest_contest_history(contest_id: str):
    return await contest_history_collection.find_one(
        {"contest_id": contest_id},
        sort=[("created_at", -1)]
    )

def calculate_visibility_from_history(history: dict) -> ContestVisibility:
    now = datetime.utcnow()

    reg_start = history.get("registration_start")
    reg_end = history.get("registration_end")
    vote_end = history.get("voting_end")

    if not reg_start or not reg_end or not vote_end:
        return ContestVisibility.upcoming  # safe default

    if now < reg_start:
        return ContestVisibility.upcoming

    if reg_start <= now <= vote_end:
        return ContestVisibility.in_progress

    return ContestVisibility.completed

async def get_contests_paginated(
    contest_type: ContestType,
    pagination: StandardResultsSetPagination
):
    now = datetime.utcnow()

    if contest_type == ContestType.active:
        history_query = {
            "is_active": True,
            "voting_end": {"$gte": now}
        }
    else:
        history_query = {
            "is_active": True,
            "voting_end": {"$lt": now}
        }

    total = await contest_history_collection.count_documents(history_query)

    cursor = (
        contest_history_collection
        .find(history_query)
        .sort("created_at", -1)
    )

    if pagination.limit:
        cursor = cursor.skip(pagination.skip).limit(pagination.limit)

    results = []

    async for history in cursor:
        contest = await contest_collection.find_one({
            "_id": ObjectId(history["contest_id"]),
            "is_deleted": {"$ne": True}
        })
        if not contest:
            continue

        banner_url = await resolve_banner_url(contest.get("banner_image_id"))

        prize_distribution = contest.get("prize_distribution", {})
        prize_pool_total = (
            prize_distribution.get("first_place", 0)
            + prize_distribution.get("second_place", 0)
            + prize_distribution.get("third_place", 0)
        )

        visibility = calculate_visibility_from_history(history)

        registration_started = await is_within_registration_period(history)
        voting_started = await is_within_voting_period(history)

        card = ContestCardResponse(
            contest_id=history["contest_id"],
            contest_history_id=str(history["_id"]),
            title=contest["title"],
            badge=contest.get("badge"),
            banner_url=banner_url,
            visibility=visibility,
            total_participants=history.get("total_participants", 0),
            total_votes=history.get("total_votes", 0),
            prize_distribution=prize_pool_total,
            registration_until=history.get("registration_end"),
            voting_ends=history.get("voting_end"),
            registration_started=registration_started,
            voting_started=voting_started
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


async def fetch_participant_avatars(contest_id, contest_history_id):
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

    return avatars

async def fetch_current_standings(
    contest_id: str,
    contest_history
):
    voting_period = is_within_voting_period(contest_history)
    if not voting_period:
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
    contest_id = str(contest["_id"])
    contest_history_id = str(contest_history["_id"])

    registration_open = await is_within_registration_period(contest_history)
    voting_open = await is_within_voting_period(contest_history)

    if registration_open:

        already_participated = await contest_participant_collection.find_one({
            "contest_id": contest_id,
            "contest_history_id": contest_history_id,
            "user_id": user_id
        })

        if already_participated:
            return {
                "can_participate": False,
                "can_vote": False,
                "reason": "ALREADY_PARTICIPATED"
            }

        return {
            "can_participate": True,
            "can_vote": False
        }

    if voting_open:

        # Participant cannot vote
        is_participant = await is_user_participant(
            user_id,
            contest_history_id
        )

        if is_participant:
            return {
                "can_participate": False,
                "can_vote": False,
                "reason": "PARTICIPANT_CANNOT_VOTE"
            }

        return {
            "can_participate": False,
            "can_vote": True
        }

    visibility = calculate_visibility_from_history(contest_history)

    if visibility == ContestVisibility.upcoming:
        return {
            "can_participate": False,
            "can_vote": False,
            "reason": "CONTEST_NOT_STARTED"
        }

    return {
        "can_participate": False,
        "can_vote": False,
        "reason": "CONTEST_ENDED"
    }

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
    query = {
        "contest_id": contest_id,
        "contest_history_id": str(contest_history_id)
    }

    total_participants = await contest_participant_collection.count_documents(query)

    # If less than 3 participants → no standings
    if total_participants < 3:
        return []

    cursor = (
        contest_participant_collection
        .find(query)
        .sort("total_votes", -1)
        .limit(limit)
    )

    leaderboard = []
    rank = 1

    async for participant in cursor:
        avatar = await resolve_user_avatar(participant["user_id"])

        user = await get_user_details(
            {"_id": ObjectId(participant["user_id"]), "is_deleted": {"$ne": True}},
            fields=["username"]
        )

        leaderboard.append({
            "rank": rank,
            "user_id": participant["user_id"],
            "username": user.get("username") if user else None,
            "total_votes": participant.get("total_votes", 0),
            "avatar": avatar
        })
        rank += 1

    return leaderboard

async def fetch_contest_participants(
    contest_id: str,
    contest_history_id: str,
    skip: int = 0,
    limit: Optional[int] = None
):
    cursor = contest_participant_collection.find(
        {
            "contest_id": contest_id,
            "contest_history_id": contest_history_id,
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

def clean_uploaded_images(images: List[UploadFile]) -> List[UploadFile]:
    return [
        img for img in images
        if img
        and img.filename
        and "." in img.filename
    ]

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
    await leaderboard_redis_helper.add_vote(str(participant_id))

async def auto_declare_winners(contest_id: str):

    contest_history = await fetch_latest_contest_history(contest_id)

    if not contest_history:
        return

    voting_end = contest_history.get("voting_end")
    if not voting_end:
        return

    now = datetime.utcnow()

    if now <= voting_end:
        return

    contest_history_id = str(contest_history["_id"])

    # Prevent duplicate declaration
    existing_winner = await contest_winner_collection.find_one({
        "contest_id": contest_id,
        "contest_history_id": contest_history_id
    })

    if existing_winner:
        return

    # Fetch contest to get prize distribution
    contest = await contest_collection.find_one({
        "_id": ObjectId(contest_id)
    })

    if not contest:
        return

    contest_name = contest.get("title", "Contest")
    prize_distribution = contest.get("prize_distribution", {})

    total_participants = await contest_participant_collection.count_documents({
        "contest_id": contest_id,
        "contest_history_id": contest_history_id
    })

    if total_participants < 3:
        return

    cursor = (
        contest_participant_collection
        .find({
            "contest_id": contest_id,
            "contest_history_id": contest_history_id
        })
        .sort("total_votes", -1)
        .limit(3)
    )

    winner_user_ids = []
    rank = 1

    async for participant in cursor:

        if rank == 1:
            prize_amount = prize_distribution.get("first_place", 0)
        elif rank == 2:
            prize_amount = prize_distribution.get("second_place", 0)
        elif rank == 3:
            prize_amount = prize_distribution.get("third_place", 0)
        else:
            prize_amount = 0

        winner_user_ids.append(participant["user_id"])

        # Insert winner record
        winner_doc = {
            "contest_id": contest_id,
            "contest_history_id": contest_history_id,
            "participant_id": str(participant["_id"]),
            "user_id": participant["user_id"],
            "rank": rank,
            "total_votes": participant.get("total_votes", 0),
            "prize_amount": prize_amount,
            "declared_at": datetime.utcnow()
        }

        await contest_winner_collection.insert_one(winner_doc)

        # Update participant record
        await contest_participant_collection.update_one(
            {"_id": participant["_id"]},
            {
                "$set": {
                    "rank": rank,
                    "is_winner": True,
                    "winner_position": rank
                }
            }
        )

        # Credit prize tokens to user
        winner_user_id = participant["user_id"]

        balance_before = await get_user_token_balance(winner_user_id)
        balance_after = balance_before + prize_amount

        # Credit prize into main tokens (withdrawable)
        await user_collection.update_one(
            {"_id": ObjectId(winner_user_id)},
            {
                "$inc": {"tokens": prize_amount},
                "$set": {"updated_at": datetime.utcnow()}
            }
        )

        # Create token history
        await create_user_token_history(
            CreateTokenHistory(
                user_id=str(winner_user_id),
                delta=prize_amount,
                type=TokenTransactionType.CREDIT,
                reason=TokenTransactionReason.CONTEST_PRIZE,
                balance_before=str(balance_before),
                balance_after=str(balance_after)
            )
        )
        recipient_lang = participant.get("language", "en")
        admin_id = await get_admin_id_by_email()
        if not admin_id:
            return response.error_message(
                translate_message("ADMIN_CRED"),
                data=[],
                status_code=404
            )
        # Send WINNER notification
        translated_title = translate_message(
            "WINNER_NOTIFICATION_TITLE",
            recipient_lang
        )

        translated_message_template = translate_message(
            "WINNER_NOTIFICATION_MESSAGE",
            recipient_lang
        )

        translated_message = translated_message_template.format(
            rank=rank,
            contest_name=contest_name,
            amount=prize_amount
        )

        await send_notification(
            recipient_id=participant["user_id"],
            recipient_type=NotificationRecipientType.USER,
            notification_type=NotificationType.CONTEST_RESULT,
            title=translated_title,
            message=translated_message,
            sender_user_id=admin_id,
            reference={
                "contest_id": contest_id,
                "rank": rank
            },
            send_push=True
        )
        rank += 1

    # Unsubscribe winners from topic first
    for winner_id in winner_user_ids:
        await unsubscribe_user_from_topic(
            user_id=winner_id,
            topic=f"contest_{contest_history_id}_participants"
        )

    # Send topic notification to non-winners
    distinct_languages = await user_collection.distinct("language")  # or fetch dynamically

    for lang in distinct_languages:

        translated_title = translate_message(
            "PARTICIPATION_NOTIFICATION_TITLE",
            lang
        )

        translated_message_template = translate_message(
            "PARTICIPATION_NOTIFICATION_MESSAGE",
            lang
        )

        translated_message = translated_message_template.format(
            contest_name=contest_name
        )

        await send_topic_notification(
            topic=f"contest_{contest_history_id}_participants_{lang}",
            title=translated_title,
            body=translated_message,
            data={
                "contest_id": contest_id,
                "contest_name": contest_name
            }
        )
