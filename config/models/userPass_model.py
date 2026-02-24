from bson import ObjectId
from datetime import datetime
from pymongo.errors import DuplicateKeyError
from config.db_config import (
    user_collection ,
    favorite_collection ,
    user_like_history ,
    user_match_history ,
    user_passed_hostory,
    user_passed_hostory,
    onboarding_collection,
    file_collection,
    daily_action_history
)
from core.utils.helper import serialize_datetime_fields
from core.utils.response_mixin import CustomResponseMixin
from services.translation import translate_message
from core.utils.core_enums import MembershipType
from core.utils.age_calculation import calculate_age
from api.controller.files_controller import generate_file_url
from core.utils.action_limit import check_daily_action_limit , increment_daily_counter
from core.utils.core_enums import NotificationType, NotificationRecipientType
from services.notification_service import send_notification
from api.controller.onboardingController import get_matched_users_model

response = CustomResponseMixin()


# function help to add user to favorites collection
async def add_to_fav(user_id: str, favorite_user_id: str, lang: str = "en"):
    user = await user_collection.find_one(
        {"_id": ObjectId(user_id)},
        {"membership_type": 1}
    )

    if not user:
        return response.error_message(
            translate_message("USER_NOT_FOUND", lang),
            status_code=404
        )

    can_perform, total, error_key = await check_daily_action_limit(user_id)

    if not can_perform:
        return response.error_message(
            translate_message(error_key, lang),
            data=[{"can_perform_action": False}],
            status_code=400
        )
    # ------------------ SELF CHECK ------------------
    if user_id == favorite_user_id:
        return response.error_message(
            translate_message("CANNOT_ADD_SELF_TO_FAVORITES", lang),
            status_code=400
        )

    favorite_user = await user_collection.find_one(
        {"_id": ObjectId(favorite_user_id)}
    )

    if not favorite_user:
        return response.error_message(
            translate_message("FAVORITE_USER_NOT_FOUND", lang),
            status_code=404
        )

    # ------------------ PASSED USER CHECK (NEW) ------------------
    passed_user = await user_passed_hostory.find_one({
        "user_id": user_id,
        "passed_user_ids": favorite_user_id
    })

    if passed_user:
        return response.error_message(
            translate_message("CANNOT_FAVORITE_PASSED_USER", lang),
            status_code=400
        )

    # ------------------ ALREADY IN FAVORITES ------------------
    existing_fav = await favorite_collection.find_one(
        {
            "user_id": user_id,
            "favorite_user_ids": favorite_user_id
        }
    )

    if existing_fav:
        return response.error_message(
            translate_message("USER_ALREADY_IN_FAVORITES", lang),
            data=[],
            status_code=400
        )

    await favorite_collection.update_one(
        {"user_id": user_id},
        {
            "$addToSet": {"favorite_user_ids": favorite_user_id},
            "$set": {"updated_at": datetime.utcnow()},
            "$setOnInsert": {
                "user_id": user_id,
                "created_at": datetime.utcnow()
            }
        },
        upsert=True
    )

    await increment_daily_counter(user_id, "favorite")

    response_data = serialize_datetime_fields({
        "favorite_user_id": favorite_user_id,
        "can_perform_action": True
    })

    return response.success_message(
        translate_message("USER_ADDED_TO_FAVORITES", lang),
        data=[response_data]
    )


# Function to handle like of the users.
async def like_user(user_id: str, liked_user_id: str, lang: str = "en"):

    can_perform, total, error_key = await check_daily_action_limit(user_id)

    if not can_perform:
        return response.error_message(
            translate_message(error_key, lang),
            data=[{"can_perform_action": False}],
            status_code=400
        )

    # Cannot like self
    if user_id == liked_user_id:
        return response.error_message(
            translate_message("CANNOT_LIKE_SELF", lang),
            data=[],
            status_code=400
        )

    #  Check liked user exists
    liked_user = await user_collection.find_one(
        {"_id": ObjectId(liked_user_id)}
    )

    if not liked_user:
        return response.error_message(
            translate_message("USER_NOT_FOUND", lang),
            data=[],
            status_code=404
        )

    passed_user = await user_passed_hostory.find_one({
        "user_id": user_id,
        "passed_user_ids": liked_user_id
    })

    if passed_user:
        return response.error_message(
            translate_message("CANNOT_LIKE_PASSED_USER", lang),
            data=[],
            status_code=400
        )

    # Already liked check (idempotent)
    already_liked = await user_like_history.find_one({
        "user_id": liked_user_id,
        "liked_by_user_ids": user_id
    })

    if already_liked:
        return response.error_message(
            translate_message("USER_ALREADY_LIKED", lang),
            data=[{
                "liked_user_id": liked_user_id,
                "is_match": False
            }],
            status_code=400
        )

    # Add like
    await user_like_history.update_one(
        {"user_id": liked_user_id},
        {
            "$addToSet": {"liked_by_user_ids": user_id},
            "$set": {"updated_at": datetime.utcnow()},
            "$setOnInsert": {
                "user_id": liked_user_id,
                "created_at": datetime.utcnow()
            }
        },
        upsert=True
    )

    await increment_daily_counter(user_id,"like")

    # --------------------------------------------------
    # 2 CHECK MUTUAL LIKE
    # --------------------------------------------------
    user_liked_them = await user_like_history.find_one({
        "user_id": user_id,
        "liked_by_user_ids": liked_user_id
    })

    they_liked_user = await user_like_history.find_one({
        "user_id": liked_user_id,
        "liked_by_user_ids": user_id
    })

    is_match = False

    # --------------------------------------------------
    # 3 CREATE MATCH (ATOMIC & SAFE)
    # --------------------------------------------------
    if user_liked_them and they_liked_user:
        # Sorted pair ensures consistency
        user_pair = sorted([user_id, liked_user_id])
        pair_key = f"{user_pair[0]}_{user_pair[1]}"

        try:
            result = await user_match_history.update_one(
                {"pair_key": pair_key},
                {
                    "$setOnInsert": {
                        "pair_key": pair_key,
                        "user_ids": user_pair,
                        "created_at": datetime.utcnow()
                    }
                },
                upsert=True
            )

            # True only if match was created now
            is_match = bool(result.upserted_id)
            if is_match:
                # Fetch language preferences
                user_1 = await user_collection.find_one(
                    {"_id": ObjectId(user_id)},
                    {"language": 1}
                )
                user_2 = await user_collection.find_one(
                    {"_id": ObjectId(liked_user_id)},
                    {"language": 1}
                )

                user_1_lang = user_1.get("language", "en")
                user_2_lang = user_2.get("language", "en")

                # Notify user who was liked
                await send_notification(
                    recipient_id=liked_user_id,
                    recipient_type=NotificationRecipientType.USER,
                    notification_type=NotificationType.MATCH,
                    title="PUSH_TITLE_MATCHED",
                    message="PUSH_MESSAGE_MATCHED",
                    reference={
                        "entity": "match",
                        "entity_id": user_id
                    },
                    sender_user_id=user_id,
                    send_push=True
                )

                # Notify current user
                await send_notification(
                    recipient_id=user_id,
                    recipient_type=NotificationRecipientType.USER,
                    notification_type=NotificationType.MATCH,
                    title="PUSH_TITLE_MATCHED",
                    message="PUSH_MESSAGE_MATCHED",
                    reference={
                        "entity": "match",
                        "entity_id": liked_user_id
                    },
                    sender_user_id=liked_user_id,
                    send_push=True
                )


        except DuplicateKeyError:
            # Another request already created the match
            is_match = False

    # --------------------------------------------------
    # 5. FINAL RESPONSE
    # --------------------------------------------------

    return response.success_message(
        translate_message(
            "MATCH_CREATED" if is_match else "USER_LIKED_SUCCESSFULLY",
            lang
        ),
        data=[{
            "liked_user_id": liked_user_id,
            "is_match": is_match,
            "can_perform_action": True
        }]
    )

# Function to pass the user.
async def pass_user(user_id: str, passed_user_id: str, lang: str = "en"):

    can_perform, total, error_key = await check_daily_action_limit(user_id)

    if not can_perform:
        return response.error_message(
            translate_message(error_key, lang),
            data=[{"can_perform_action": False}],
            status_code=400
        )

    # Cannot pass self
    if user_id == passed_user_id:
        return response.error_message(
            translate_message("CANNOT_PASS_SELF", lang),
            data = [],
            status_code=400
        )

    #  Check user exists
    passed_user = await user_collection.find_one(
        {"_id": ObjectId(passed_user_id)}
    )

    if not passed_user:
        return response.error_message(
            translate_message("USER_NOT_FOUND", lang),
            data =[],
            status_code=404
        )

    #  Already passed?
    already_passed = await user_passed_hostory.find_one({
        "user_id": user_id,
        "passed_user_ids": passed_user_id
    })

    if already_passed:
        return response.error_message(
            translate_message("USER_ALREADY_PASSED", lang),
            data = [],
            status_code=200
        )

    # Store pass
    await user_passed_hostory.update_one(
        {"user_id": user_id},
        {
            "$addToSet": {"passed_user_ids": passed_user_id},
            "$set": {"updated_at": datetime.utcnow()},
            "$setOnInsert": {
                "user_id": user_id,
                "created_at": datetime.utcnow()
            }
        },
        upsert=True
    )

    await increment_daily_counter(user_id,"pass")

    return response.success_message(
        translate_message("USER_PASSED_SUCCESSFULLY", lang),
        data=[{
            "passed_user_id": passed_user_id,
            "can_perform_action": True
        }]
    )

# Function to return the list of the favorites users.
async def get_my_favorites(user_id: str, lang: str = "en"):
    fav_doc = await favorite_collection.find_one(
        {"user_id": user_id},
        {"_id": 0, "favorite_user_ids": 1}
    )

    favorite_user_ids = fav_doc.get("favorite_user_ids", []) if fav_doc else []

    if not favorite_user_ids:
        return response.success_message(
            translate_message("NO_FAVORITES_FOUND", lang),
            data=[]
        )

    # -------- 2. Get Passed Users --------
    passed_doc = await user_passed_hostory.find_one(
        {"user_id": user_id},
        {"_id": 0, "passed_user_ids": 1}
    )

    passed_user_ids = passed_doc.get("passed_user_ids", []) if passed_doc else []

    # -------- 3. Remove Passed Users from Favorites --------
    filtered_favorite_ids = [
        uid for uid in favorite_user_ids
        if uid not in passed_user_ids
    ]

    if not filtered_favorite_ids:
        return response.success_message(
            translate_message("NO_FAVORITES_FOUND", lang),
            data=[]
        )

    # -------- 4. Fetch Users --------
    users_cursor = user_collection.find(
        {"_id": {"$in": [ObjectId(uid) for uid in filtered_favorite_ids]}},
        {"_id": 1, "username": 1, "is_verified": 1}
    )

    users = []
    async for user in users_cursor:
        uid = str(user["_id"])

        onboarding = await onboarding_collection.find_one(
            {"user_id": uid},
            {"birthdate": 1, "images": 1}
        )

        # -------- Age --------
        age = None
        if onboarding and onboarding.get("birthdate"):
            age = calculate_age(onboarding["birthdate"].date())

        # -------- Profile Photo --------
        profile_photo_id = None
        profile_photo_url = None

        image_ids = onboarding.get("images", []) if onboarding else []
        if image_ids:
            file_doc = await file_collection.find_one(
                {"_id": ObjectId(image_ids[0])},
                {"storage_key": 1, "storage_backend": 1}
            )

            if file_doc:
                profile_photo_id = str(file_doc["_id"])
                profile_photo_url = await generate_file_url(
                    file_doc["storage_key"],
                    file_doc.get("storage_backend")
                )

        users.append({
            "user_id": uid,
            "username": user.get("username"),
            "is_verified": user.get("is_verified"),
            "age": age,
            "profile_photo_id": profile_photo_id,
            "profile_photo_url": profile_photo_url
        })

    return response.success_message(
        translate_message("FAVORITES_FETCHED", lang),
        data=users
    )

async def get_liked_user_ids(user_id: str) -> list[str]:
    """
    Returns list of user_ids who liked the given user
    """
    like_doc = await user_like_history.find_one(
        {"user_id": user_id},
        {"liked_by_user_ids": 1}
    )

    return like_doc.get("liked_by_user_ids", []) if like_doc else []

#function to return the liked user list .
async def get_users_who_liked_me(user_id: str, lang: str = "en"):
    liked_by_user_ids = await get_liked_user_ids(user_id)

    if not liked_by_user_ids:
        return response.success_message(
            translate_message("NO_LIKES_FOUND", lang),
            data=[]
        )

    users_cursor = user_collection.find(
        {"_id": {"$in": [ObjectId(uid) for uid in liked_by_user_ids]}},
        {"_id": 1, "username": 1, "is_verified": 1, "profile_photo_id": 1}
    )

    users = []
    async for user in users_cursor:
        users.append({
            "user_id": str(user["_id"]),
            "username": user.get("username"),
            "is_verified": user.get("is_verified"),
            "profile_photo_id": user.get("profile_photo_id")
        })

    return response.success_message(
        translate_message("LIKED_USERS_FETCHED", lang),
        data=users,
        status_code=200
    )


async def get_user_login_status_internal(user_id: str, lang: str = "en"):
    """
    Internal function to fetch login status of a user
    """

    # Validate ObjectId
    try:
        obj_id = ObjectId(user_id)
    except Exception:
        return response.error_message(
            translate_message("INVALID_USER_ID", lang),
            data = [],
            status_code=400
        )

    user = await user_collection.find_one(
        {"_id": obj_id},
        {"_id": 0, "login_status": 1}
    )

    if not user:
        return response.error_message(
            translate_message("USER_NOT_FOUND", lang),
            status_code=404
        )

    return response.success_message(
        translate_message("USER_STATUS_FETCHED", lang),
        data=[{
            "user_id": user_id,
            "login_status": user.get("login_status")
        }]
    )


async def get_matched_users_controller(current_user, lang: str = "en"):
    try:
        user_id = str(current_user["_id"])

        matched_users = await get_matched_users_model(user_id, lang)

        return response.success_message(
            translate_message("MATCHED_USERS_FETCHED", lang),
            data=matched_users,
            status_code=200
        )

    except Exception as e:
        return response.error_message(
            translate_message("SOMETHING_WENT_WRONG", lang),
            data=[str(e)],
            status_code=500
        )
