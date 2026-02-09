from services.translation import translate_message
from core.utils.response_mixin import CustomResponseMixin
from config.models.contest_model import *
from core.utils.pagination import StandardResultsSetPagination
import asyncio
from core.utils.helper import *
from services.gallery_service import *
from config.basic_config import settings

response = CustomResponseMixin()

async def get_contests_controller(
    current_user: dict,
    contest_type: str,
    pagination: StandardResultsSetPagination,
    lang: str = "en"
):
    # Verification gate
    if current_user.get("is_verified") is not True:
        return response.success_message(
            translate_message("VERIFICATION_PENDING", lang),
            data=[{"verification_required": True}]
        )

    contests, total = await get_contests_paginated(
        contest_type=contest_type,
        pagination=pagination
    )

    return response.success_message(
        translate_message("CONTESTS_FETCHED", lang),
        data=[serialize_datetime_fields(convert_objectid_to_str({
            "results": contests,
            "page": pagination.page,
            "page_size": pagination.page_size,
            "total": total
        }))]
    )

async def get_contest_details_controller(
    contest_id: str,
    current_user: dict,
    lang: str = "en"
):
    # Fetch contest
    contest = await fetch_contest_by_id(contest_id)
    if not contest:
        return response.error_message(
            translate_message("CONTEST_NOT_FOUND", lang),
            status_code=404
        )

    # Fetch active contest history
    contest_history = await fetch_active_contest_history(contest_id)

    if not contest_history:
        contest_history = await fetch_latest_contest_history(contest_id)

    if not contest_history:
        # Contest exists but no cycle created yet
        return response.success_message(
            translate_message("CONTEST_NOT_STARTED_YET", lang),
            data=[{
                "contest_id": contest_id,
                "title": contest["title"],
                "visibility": "upcoming",
                "cta": "coming_soon"
            }]
        )


    contest_history_id = str(contest_history["_id"])

    # Parallel IO operations
    (
        banner_url,
        avatars,
        standings,
        cta
    ) = await asyncio.gather(
        resolve_banner_url(contest["banner_image_id"]),
        fetch_participant_avatars(contest_id, contest_history_id),
        fetch_current_standings(contest_id, contest_history),
        resolve_cta_state(
            contest=contest,
            contest_history=contest_history,
            current_user=current_user
        )
    )

    # Build response payload
    raw_data = {
        "contest_id": contest_id,
        "title": contest["title"],
        "description": contest.get("description"),

        "visibility": contest_history["visibility"],
        "banner_url": banner_url,

        "important_dates": {
            "registration_start": contest_history["registration_start"],
            "registration_end": contest_history["registration_end"],
            "voting_start": contest_history["voting_start"],
            "voting_end": contest_history["voting_end"]
        },

        "prize_pool": {
            "distribution": contest.get("prize_distribution", [])
        },

        "participants": {
            "count": contest_history["total_participants"],
            "avatars": avatars,
            "can_view_all": True
        },

        "judging_criteria": contest.get("judging_criteria", []),
        "rules_and_conditions": contest.get("rules", []),

        "current_standings": standings,
        "cta": cta
    }

    return response.success_message(
        translate_message("CONTEST_DETAILS_FETCHED", lang),
        data=[serialize_datetime_fields(convert_objectid_to_str(raw_data))]
    )

async def get_contest_participants_controller(
    contest_id: str,
    pagination: StandardResultsSetPagination,
    current_user: dict,
    lang: str
):
    contest_history = await fetch_active_contest_history(contest_id)

    if not contest_history:
        contest_history = await fetch_latest_contest_history(contest_id)

    if not contest_history:
        return response.error_message(
            translate_message("CONTEST_HISTORY_NOT_FOUND", lang),
            status_code=404
        )

    voting_active = is_within_voting_period(contest_history)


    viewer_id = str(current_user["_id"])

    # Fetch contest (for max_votes_per_user)
    contest = await fetch_contest_by_id(contest_id)

    votes_casted = 0
    voted_participant_ids = set()

    if voting_active:
        votes_casted = await contest_vote_collection.count_documents({
            "contest_id": contest_id,
            "contest_history_id": str(contest_history["_id"]),
            "voter_user_id": viewer_id
        })

        async for v in contest_vote_collection.find(
            {
                "contest_id": contest_id,
                "contest_history_id": str(contest_history["_id"]),
                "voter_user_id": viewer_id
            },
            {"participant_id": 1}
        ):
            voted_participant_ids.add(v["participant_id"])

    participants = await fetch_contest_participants(
        contest_id=contest_id,
        contest_history_id=str(contest_history["_id"]),
        skip=pagination.skip,
        limit=pagination.limit
    )

    response_items = []

    for participant in participants:
        user = await get_user_details(
            {"_id": ObjectId(participant["user_id"]), "is_deleted": {"$ne": True}},
            fields=["username", "is_verified"]
        )

        if not user:
            continue

        avatar = await resolve_user_avatar(participant["user_id"])

        # ----- can_vote logic -----
        can_vote = True
        vote_disabled_reason = None

        if not voting_active:
            can_vote = False
            vote_disabled_reason = "VOTING_NOT_STARTED"

        elif participant["user_id"] == viewer_id:
            can_vote = False
            vote_disabled_reason = "SELF_PARTICIPANT"

        elif str(participant["_id"]) in voted_participant_ids:
            can_vote = False
            vote_disabled_reason = "ALREADY_VOTED"

        elif votes_casted >= contest["max_votes_per_user"]:
            can_vote = False
            vote_disabled_reason = "VOTE_LIMIT_REACHED"

        response_items.append({
            "participant_id": str(participant["_id"]),
            "user_id": participant["user_id"],
            "name": user.get("username"),
            "profile_photo": avatar["avatar_url"] if avatar else None,
            "is_verified": user.get("is_verified", False),
            "can_vote": can_vote,
            "vote_disabled_reason": vote_disabled_reason
        })

    return response.success_message(
        translate_message("CONTEST_PARTICIPANTS_FETCHED_SUCCESSFULLY", lang),
        data=[{
            "participants": response_items,
            "page": pagination.page,
            "page_size": pagination.page_size
        }],
        status_code=200
    )

async def participate_in_contest_controller(
    contest_id: str,
    contest_history_id: str,
    images: List[UploadFile],
    current_user: dict,
    lang: str
):
    user_id = str(current_user["_id"])

    # Verified check
    if not current_user.get("is_verified"):
        return response.error_message(
            translate_message("VERIFY_PROFILE_TO_PARTICIPATE", lang),
            status_code=403
        )

    # Contest & history validation
    contest = await fetch_contest_by_id(contest_id)
    if not contest:
        return response.error_message(
            translate_message("CONTEST_NOT_FOUND_OR_INACTIVE", lang),
            status_code=404
        )

    # Fetch active contest history
    contest_history = await fetch_active_contest_history(contest_id)
    if not contest_history or contest_history["contest_id"] != contest_id:
        return response.error_message(
            translate_message("INVALID_CONTEST_HISTORY", lang),
            status_code=400
        )

    if not await is_within_registration_period(contest_history):
        now = datetime.utcnow()

        if now < contest_history["registration_start"]:
            return response.error_message(
                translate_message("REGISTRATION_NOT_STARTED", lang),
                data={
                    "registration_starts_at": contest_history["registration_start"].isoformat()
                },
                status_code=403
            )

        return response.error_message(
            translate_message("REGISTRATION_CLOSED", lang),
            data={
                "registration_ended_at": contest_history["registration_end"].isoformat()
            },
            status_code=403
        )
    # Prevent duplicate participation
    if await is_user_already_participant(
        contest_id,
        contest_history_id,
        user_id
    ):
        return response.error_message(
            translate_message("ALREADY_PARTICIPATED", lang),
            status_code=400
        )

    # Enforce image limit
    images = clean_uploaded_images(images)

    images_allowed = contest.get("images_per_participant", 1)

    if not images:
        return response.error_message(
            translate_message("IMAGE_REQUIRED", lang),
            status_code=400
        )

    if len(images) != images_allowed:
        return response.error_message(
            translate_message("IMAGES_UPLOADING_LIMIT_EXCEEDED", lang),
            data={
                "allowed": images_allowed,
                "received": len(images)
            },
            status_code=400
        )

    # Token check using contest vote_cost
    vote_cost = settings.CONTEST_TOKEN_COST
    current_tokens = await get_user_token_balance(user_id)

    if current_tokens < vote_cost:
        return response.error_message(
            translate_message("INSUFFICIENT_TOKENS", lang),
            data={
                "required": vote_cost,
                "available": current_tokens
            },
            status_code=403
        )

    uploaded_images = []
    uploaded_file_ids = []

    # Upload images
    for image in images:
        contest_item = await create_and_store_file(
            file_obj=image,
            user_id=user_id,
            file_type=FileType.CONTEST
        )

        uploaded_file_ids.append(contest_item["file_id"])

        file_doc = await file_collection.find_one(
            {"_id": ObjectId(contest_item["file_id"]), "is_deleted": {"$ne": True}}
        )

        image_url = None
        if file_doc:
            image_url = await generate_file_url(
                storage_key=file_doc["storage_key"],
                backend=file_doc["storage_backend"]
            )

        uploaded_images.append({
            "file_id": contest_item["file_id"],
            "url": image_url,
            "uploaded_at": contest_item.get("uploaded_at")
        })

    # Debit tokens ONCE
    balance_after, _ = await debit_user_tokens(
        user_id=user_id,
        amount=vote_cost,
        reason=f"Contest participation: {contest_id}"
    )

    if balance_after is None:
        return response.error_message(
            translate_message("TOKEN_DEBIT_FAILED", lang),
            status_code=500
        )

    # Save participant (using helper)
    await create_contest_participant({
        "contest_id": contest_id,
        "contest_history_id": contest_history_id,
        "user_id": user_id,
        "uploaded_file_ids": uploaded_file_ids,
        "total_votes": 0,
        "created_at": datetime.utcnow()
    })

    # Increment participant count
    await increment_participant_count(contest_history_id)

    # Response
    response_payload = {
        "contest_id": contest_id,
        "contest_history_id": contest_history_id,
        "tokens_deducted": vote_cost,
        "balance_after": balance_after,
        "images": uploaded_images
    }

    response_payload = serialize_datetime_fields(
        convert_objectid_to_str(response_payload)
    )

    return response.success_message(
        translate_message("CONTEST_PARTICIPATION_SUCCESSFUL", lang),
        data=[response_payload],
        status_code=200
    )

async def get_full_leaderboard_controller(
    contest_id: str,
    pagination: StandardResultsSetPagination,
    lang: str
):
    contest_history = await fetch_latest_contest_history(contest_id)

    if not contest_history:
        return response.error_message(
            translate_message("CONTEST_HISTORY_NOT_FOUND", lang),
            status_code=404
        )

    query = {
        "contest_id": contest_id,
        "contest_history_id": str(contest_history["_id"])
    }

    cursor = (
        contest_participant_collection
        .find(query)
        .sort("total_votes", -1)
    )

    if pagination.page and pagination.page_size:
        cursor = cursor.skip(pagination.skip).limit(pagination.page_size)

    total = await contest_participant_collection.count_documents(query)

    leaderboard = []
    rank_counter = pagination.skip + 1 if pagination.page else 1

    async for participant in cursor:
        user_id = participant["user_id"]

        user = await get_user_details(
            {"_id": ObjectId(user_id)},
            fields=["username"]
        )

        avatar = await resolve_user_avatar(user_id)
        badge = resolve_badge(rank_counter)

        leaderboard.append({
            "rank": rank_counter,
            "user_id": user_id,
            "username": user.get("username") if user else None,
            "total_votes": participant.get("total_votes", 0),
            "avatar": avatar,
            "badge": badge
        })

        rank_counter += 1

    return response.success_message(
        translate_message("LEADERBOARD_FETCHED_SUCCESSFULLY", lang),
        data=[{
            "contest_id": contest_id,
            "contest_history_id": str(contest_history["_id"]),
            "pagination": (
                {
                    "page": pagination.page,
                    "page_size": pagination.page_size,
                    "total": total
                }
                if pagination.page and pagination.page_size
                else None
            ),
            "results": leaderboard
        }]
    )

async def cast_vote_controller(
    contest_id: str,
    participant_user_id: str,
    current_user: dict,
    lang: str
):
    if not participant_user_id:
        return response.error_message(
            translate_message("PARTICIPANT_USER_ID_REQUIRED", lang),
            status_code=400
        )

    user_id = str(current_user["_id"])

    contest_history = await fetch_active_contest_history(contest_id)
    if not contest_history:
        return response.error_message(
            translate_message("CONTEST_NOT_ACTIVE", lang),
            status_code=400
        )

    now = datetime.utcnow()

    if not await is_within_voting_period(contest_history):
        if now < contest_history["voting_start"]:
            return response.error_message(
                translate_message("VOTING_NOT_STARTED", lang),
                data={
                    "voting_starts_at": contest_history["voting_start"].isoformat()
                },
                status_code=403
            )

        return response.error_message(
            translate_message("VOTING_ENDED", lang),
            data={
                "voting_ended_at": contest_history["voting_end"].isoformat()
            },
            status_code=403
        )

    contest_history_id = str(contest_history["_id"])

    participant = await get_participant_by_user(
        contest_id,
        contest_history_id,
        participant_user_id
    )
    if not participant:
        return response.error_message(
            translate_message("PARTICIPANT_NOT_FOUND", lang),
            status_code=404
        )

    if participant_user_id == user_id:
        return response.error_message(
            translate_message("PARTICIPANT_CANNOT_VOTE", lang),
            status_code=400
        )

    contest = await fetch_contest_by_id(contest_id)

    votes_casted = await get_user_vote_count(
        contest_id,
        contest_history_id,
        user_id
    )

    if votes_casted >= contest["max_votes_per_user"]:
        return response.error_message(
            translate_message("VOTING_LIMIT_REACHED", lang),
            status_code=400
        )

    already_voted = await has_user_voted_for_participant(
        contest_id,
        contest_history_id,
        str(participant["_id"]),
        user_id
    )
    if already_voted:
        return response.error_message(
            translate_message("ALREADY_VOTED_FOR_PARTICIPANT", lang),
            status_code=400
        )

    balance_after, balance_before = await debit_user_tokens(
        user_id=user_id,
        amount=contest["cost_per_vote"],
        reason=f"contest_vote:{contest_id}"
    )

    if balance_after is None:
        return response.error_message(
            translate_message("INSUFFICIENT_TOKENS", lang),
            data={
                "required": contest["vote_cost"],
                "available": balance_before
            },
            status_code=400
        )

    await create_vote_entry({
        "contest_id": contest_id,
        "contest_history_id": contest_history_id,
        "participant_id": str(participant["_id"]),
        "voter_user_id": user_id,
        "vote_cost": contest["cost_per_vote"],
        "voted_at": datetime.utcnow()
    })

    await increment_vote_counts(
        participant["_id"],
        contest_history_id
    )

    return response.success_message(
        translate_message("VOTE_CAST_SUCCESSFULLY", lang),
        data={
            "participant_user_id": participant_user_id,
            "remaining_votes": contest["max_votes_per_user"] - (votes_casted + 1),
            "tokens_left": balance_after
        }
    )
