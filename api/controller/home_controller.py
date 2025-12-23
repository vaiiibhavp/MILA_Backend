from datetime import datetime, timedelta
from config.db_config import (
    onboarding_collection,
    user_passed_hostory,
    user_match_history
)
from core.utils.age_calculation import calculate_age
from api.controller.onboardingController import fetch_user_by_id
from bson import ObjectId

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
    user = await onboarding_collection.find_one({"user_id": user_id})

    if not user or not user.get("onboarding_completed"):
        return {
            "count": 0,
            "results": [],
            "message": "Onboarding not completed"
        }

    excluded_ids = await _get_excluded_user_ids(user_id)

    # 1️ HARD FILTERS (Core preferences)
    query = {
        "onboarding_completed": True,
        "user_id": {"$nin": list(excluded_ids)},
        "interested_in": {"$in": [user.get("gender")]},
    }

    # Sexual preferences → hard filter
    if user.get("sexual_preferences"):
        query["sexual_preferences"] = {
            "$in": user["sexual_preferences"]
        }

    # Country
    if user.get("preferred_country"):
        query["country"] = {
            "$in": user["preferred_country"]
        }

    cursor = onboarding_collection.find(query)

    # 3️ Prioritization signals ONLY

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

        # Activity status
        if candidate.get("is_online"):
            priority["is_online"] = True
        elif candidate.get("last_active_at"):
            last_active = candidate["last_active_at"]
            if isinstance(last_active, datetime) and now - last_active <= timedelta(days=7):
                priority["recently_active"] = True

        # Shared interests (ranking only)
        candidate_passions = set(candidate.get("passions", []))
        priority["shared_interests"] = len(user_passions & candidate_passions)

        details["_priority"] = priority
        results.append(details)

    # 4️ Ordering (NO filtering)
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

    return {
        "count": len(results),
        "results": results
    }
