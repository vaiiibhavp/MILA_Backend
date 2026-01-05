from datetime import datetime, timedelta
from config.db_config import (
    onboarding_collection,
    user_passed_hostory,
    user_match_history
)
from core.utils.response_mixin import CustomResponseMixin
from services.translation import translate_message
from core.utils.age_calculation import calculate_age
from api.controller.onboardingController import fetch_user_by_id
from bson import ObjectId

response = CustomResponseMixin()


async def _get_excluded_user_ids(user_id: str) -> set:
    excluded = {user_id}

    passed = await user_passed_hostory.find_one(
        {"user_id": user_id},
        {"passed_user_ids": 1}
    )
    if passed:
        excluded.update(passed.get("passed_user_ids", []))

    matches = user_match_history.find({"user_ids": user_id})
    async for m in matches:
        excluded.update(m["user_ids"])

    return excluded

async def get_home_suggestions(user_id: str, lang: str = "en"):
    try:
        user = await onboarding_collection.find_one({"user_id": user_id})

        if not user or not user.get("onboarding_completed"):
            return response.success_message(
                translate_message("ONBOARDING_NOT_COMPLETED", lang),
                data=[{
                    "count": 0,
                    "results": []
                }]
            )

        excluded_ids = await _get_excluded_user_ids(user_id)

        #  HARD FILTERS
        query = {
            "onboarding_completed": True,
            "user_id": {"$nin": list(excluded_ids)},
            "interested_in": {"$in": [user.get("gender")]},
        }

        # Sexual preferences
        if user.get("sexual_preferences"):
            query["sexual_preferences"] = {
                "$in": user["sexual_preferences"]
            }

        # Country preference
        if user.get("preferred_country"):
            query["country"] = {
                "$in": user["preferred_country"]
            }

        cursor = onboarding_collection.find(query)

        user_passions = set(user.get("passions", []))
        now = datetime.utcnow()
        results = []

        async for candidate in cursor:
            details = await fetch_user_by_id(candidate["user_id"], lang)
            if not details:
                continue

            priority = {
                "is_online": False,
                "recently_active": False,
                "shared_interests": 0
            }

            # Online / recent activity
            if candidate.get("is_online"):
                priority["is_online"] = True
            elif candidate.get("last_active_at"):
                last_active = candidate["last_active_at"]
                if isinstance(last_active, datetime) and now - last_active <= timedelta(days=7):
                    priority["recently_active"] = True

            # Shared interests
            candidate_passions = set(candidate.get("passions", []))
            priority["shared_interests"] = len(user_passions & candidate_passions)

            details["_priority"] = priority
            results.append(details)

        # 2️ SORTING (ranking only)
        results.sort(
            key=lambda x: (
                x["_priority"]["is_online"],
                x["_priority"]["recently_active"],
                x["_priority"]["shared_interests"],
            ),
            reverse=True
        )

        for r in results:
            r.pop("_priority", None)

        return response.success_message(
            translate_message("HOME_SUGGESTIONS_FETCHED", lang),
            data=[{
                "count": len(results),
                "results": results
            }]
        )

    except Exception as e:
        return response.raise_exception(
            translate_message("ERROR_WHILE_FETCHING_HOME_SUGGESTIONS", lang),
            data=str(e),
            status_code=500
        )
