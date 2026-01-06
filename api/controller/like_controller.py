#like_controller.py

from services.translation import translate_message
from bson import ObjectId
from core.utils.core_enums import *
from core.utils.age_calculation import calculate_age
from api.controller.files_controller import get_profile_photo_url
from core.utils.pagination import StandardResultsSetPagination
from config.models.onboarding_model import *
from core.utils.response_mixin import CustomResponseMixin
from config.models.userPass_model import get_liked_user_ids
from config.db_config import *
from services.premium_guard import require_premium
from config.models.user_models import *
from core.utils.helper import *
from api.controller.files_controller import *

response = CustomResponseMixin()

async def get_users_who_liked_me_for_premium(
    current_user: dict,
    pagination: StandardResultsSetPagination,
    lang: str = "en"
):
    # Premium guard
    premium_error = require_premium(current_user, lang)
    if premium_error:
        return premium_error

    liked_by_user_ids = await get_liked_user_ids(str(current_user["_id"]))

    if not liked_by_user_ids:
        return response.success_message(
            translate_message("NO_LIKES_FOUND", lang),
            data=[{
                "results": [],
                "page": pagination.page,
                "page_size": pagination.page_size
            }]
        )

    cursor = (
        user_collection.find(
            {"_id": {"$in": [ObjectId(uid) for uid in liked_by_user_ids]}},
            {"username": 1, "is_verified": 1, "login_status": 1}
        )
        .skip(pagination.skip)
        .limit(pagination.limit)
    )

    results = []

    async for user in cursor:
        onboarding = await asyncio.gather(
            get_onboarding_details(
                {"user_id": str(user["_id"])},
                fields=["birthdate", "country"]
            ),
        )

        birthdate = onboarding.get("birthdate") if onboarding else None
        age = calculate_age(birthdate) if birthdate else None
        profile_photo = await profile_photo_from_onboarding(onboarding)

        results.append({
            "user_id": str(user["_id"]),
            "name": user.get("username"),
            "age": age,
            "city": onboarding.get("country") if onboarding else None,
            "profile_photo": profile_photo,
            "is_verified": user.get("is_verified", False),
            "login_status": user.get("login_status")
        })

    response_data = serialize_datetime_fields({
        "results": results,
        "page": pagination.page,
        "page_size": pagination.page_size
    })

    return response.success_message(
        translate_message("LIKED_USERS_FETCHED", lang),
        data=[response_data],
        status_code=200
    )

async def get_users_who_visited_my_profile(
    current_user: dict,
    pagination: StandardResultsSetPagination,
    lang: str = "en"
):
    """
    Premium-only API
    Fetch users who visited logged-in user's profile (paginated)
    """

    # PREMIUM GUARD
    premium_error = require_premium(current_user, lang)
    if premium_error:
        return premium_error

    # FETCH PROFILE VIEW HISTORY
    history = await profile_view_history.find_one(
        {"user_id": str(current_user["_id"])},
        {"_id": 0, "viewed_by_user_ids": 1}
    )

    views = history.get("viewed_by_user_ids", []) if history else []

    if not views:
        return response.success_message(
            translate_message("NO_PROFILE_VIEWS_FOUND", lang),
            data=[{
                "results": [],
                "page": pagination.page,
                "page_size": pagination.page_size,
                "total": 0
            }],
            status_code=200
        )

    # SORT (LATEST FIRST)
    views.sort(
        key=lambda x: x.get("viewed_at", datetime.min),
        reverse=True
    )

    # PAGINATION
    total = len(views)
    start = pagination.skip
    end = start + pagination.limit
    paginated_views = views[start:end]

    results = []

    # BUILD RESPONSE (PARALLEL FETCH)
    for view in paginated_views:
        viewer_id = view.get("user_id")
        viewed_at = view.get("viewed_at")

        user, onboarding = await asyncio.gather(
            get_user_details(
                condition={
                    "_id": ObjectId(viewer_id),
                    "is_deleted": {"$ne": True}
                },
                fields=["_id", "username", "is_verified", "login_status"]
            ),
            get_onboarding_details(
                {"user_id": viewer_id},
                fields=["birthdate", "country", "images"]
            ),
        )

        if not user:
            continue

        profile_photo = await profile_photo_from_onboarding(onboarding)

        birthdate = onboarding.get("birthdate") if onboarding else None
        age = calculate_age(birthdate) if birthdate else None

        results.append({
            "user_id": viewer_id,
            "name": user.get("username"),
            "age": age,
            "city": onboarding.get("country") if onboarding else None,
            "profile_photo": profile_photo,
            "is_verified": user.get("is_verified", False),
            "login_status": user.get("login_status"),
            "viewed_at": viewed_at
        })

    response_data = serialize_datetime_fields({
        "results": results,
        "page": pagination.page,
        "page_size": pagination.page_size,
        "total": total
    })

    return response.success_message(
        translate_message("PROFILE_VISITS_FETCHED", lang),
        data=[response_data],
        status_code=200
    )
