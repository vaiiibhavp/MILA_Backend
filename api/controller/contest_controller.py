from services.translation import translate_message
from core.utils.response_mixin import CustomResponseMixin
from config.models.contest_model import *
from core.utils.pagination import StandardResultsSetPagination
import asyncio
from core.utils.helper import *
from services.gallery_service import *

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
        return response.error_message(
            translate_message("CONTEST_HISTORY_NOT_FOUND", lang),
            status_code=404
        )

    contest_history_id = str(contest_history["_id"])

    # Parallel IO operations
    (
        banner_url,
        avatars,
        standings,
        cta
    ) = await asyncio.gather(
        resolve_banner_url(contest["banner_file_id"]),
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

        "status": contest_history["status"],
        "visibility": contest_history["visibility"],
        "banner_url": banner_url,

        "important_dates": {
            "registration_start": contest_history["registration_start"],
            "registration_end": contest_history["registration_end"],
            "voting_start": contest_history["voting_start"],
            "voting_end": contest_history["voting_end"]
        },

        "prize_pool": {
            "description": contest.get("prize_pool_description"),
            "distribution": contest.get("prize_distribution", [])
        },

        "participants": {
            "count": contest_history["total_participants"],
            "avatars": avatars,
            "can_view_all": True
        },

        "judging_criteria": contest.get("judging_criteria", []),
        "rules_and_conditions": contest.get("rules_and_conditions", []),

        "current_standings": standings,
        "cta": cta
    }

    return response.success_message(
        translate_message("CONTEST_DETAILS_FETCHED", lang),
        data=[serialize_datetime_fields(convert_objectid_to_str(raw_data))]
    )

async def get_contest_participants_controller(
    contest_id: str,
    pagination,
    lang: str
):
    participants = await fetch_contest_participants(
        contest_id=contest_id,
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

        response_items.append({
            "user_id": participant["user_id"],
            "name": user.get("username"),
            "profile_photo": avatar["avatar_url"] if avatar else None,
            "is_verified": user.get("is_verified", False)
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
    images: list,
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
    contest_history = await fetch_active_contest_history(contest_id)

    if not contest or not contest_history:
        return response.error_message(
            translate_message("CONTEST_NOT_FOUND", lang),
            status_code=404
        )

    if contest_history["status"] != ContestStatus.registration_open:
        return response.error_message(
            translate_message("CONTEST_REGISTRATION_CLOSED", lang),
            status_code=400
        )

    # Image count validation
    allowed_images = contest.get("images_per_participant", 1)
    if len(images) != allowed_images:
        return response.error_message(
            translate_message(
                "INVALID_IMAGE_COUNT",
                lang
            ),
            data={"allowed": allowed_images},
            status_code=400
        )

    # Already participated check
    already = await is_user_already_participant(
        contest_id,
        contest_history_id,
        user_id
    )
    if already:
        return response.error_message(
            translate_message("ALREADY_PARTICIPATED", lang),
            status_code=409
        )

    # Upload images
    uploaded_file_ids = []
    for img in images:
        file_doc = await create_and_store_file(
            file_obj=img,
            user_id=user_id,
            file_type=FileType.CONTEST
        )
        uploaded_file_ids.append(file_doc["file_id"])

    # Save participant
    participant_data = {
        "contest_id": contest_id,
        "contest_history_id": contest_history_id,
        "user_id": user_id,
        "uploaded_file_ids": uploaded_file_ids,
        "total_votes": 0,
        "created_at": datetime.utcnow()
    }

    participant_id = await create_contest_participant(participant_data)

    await increment_participant_count(contest_history_id)

    return response.success_message(
        translate_message("CONTEST_PARTICIPATION_SUCCESSFUL", lang),
        data=[{
            "participant_id": participant_id,
            "total_images": len(uploaded_file_ids)
        }],
        status_code=200
    )
