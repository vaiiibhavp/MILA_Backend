
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

    # Mandatory minimal filters
    query = {
        "onboarding_completed": True,
        "user_id": {"$nin": list(excluded_ids)},
        "interested_in": {"$in": [user.get("gender")]}
    }

    cursor = onboarding_collection.find(query)

    # Logged-in user sets
    user_interested_in = set(user.get("interested_in", []))
    user_passions = set(user.get("passions", []))
    user_sexual_prefs = set(user.get("sexual_preferences", []))
    user_preferred_city = set(user.get("preferred_city", []))

    results = []

    for candidate in await cursor.to_list(length=100):
        details = await fetch_user_by_id(candidate["user_id"], lang)
        if not details:
            continue

        candidate_interested_in = set(candidate.get("interested_in", []))
        candidate_passions = set(candidate.get("passions", []))
        candidate_sexual_prefs = set(candidate.get("sexual_preferences", []))
        candidate_preferred_city = set(candidate.get("preferred_city", []))

        if user_preferred_city:
            if not (user_preferred_city & candidate_preferred_city):
                continue

        has_other_match = (
            user_interested_in & candidate_interested_in
            or user_passions & candidate_passions
            or user_sexual_prefs & candidate_sexual_prefs
        )

        if not has_other_match:
            continue

        results.append(details)

    return {
        "count": len(results),
        "results": results
    }
