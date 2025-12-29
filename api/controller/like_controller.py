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

response = CustomResponseMixin()

async def get_users_who_liked_me_for_premium(
    current_user: dict,
    pagination: StandardResultsSetPagination,
    lang: str = "en"
):
    # Premium guard
    if current_user.get("membership_type") != MembershipType.PREMIUM:
        return response.error_message(
            translate_message("PREMIUM_REQUIRED", lang),
            status_code=403,
            data={"premium_required": True}
        )

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
        onboarding = await get_onboarding_details(
            {"user_id": str(user["_id"])},
            fields=["birthdate", "country"]
        )

        birthdate = onboarding.get("birthdate") if onboarding else None
        age = calculate_age(birthdate) if birthdate else None

        results.append({
            "user_id": str(user["_id"]),
            "name": user.get("username"),
            "age": age,
            "city": onboarding.get("country") if onboarding else None,
            "profile_photo": await get_profile_photo_url({"_id": user["_id"]}),
            "is_verified": user.get("is_verified", False),
            "login_status": user.get("login_status")
        })

    return response.success_message(
        translate_message("LIKED_USERS_FETCHED", lang),
        data=[{
            "results": results,
            "page": pagination.page,
            "page_size": pagination.page_size
        }],
        status_code=200
    )
