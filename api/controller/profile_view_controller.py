#profile_view_controller.py:

from bson import ObjectId
from config.db_config import user_collection, onboarding_collection, file_collection, gift_collection
from core.utils.response_mixin import CustomResponseMixin
from core.utils.age_calculation import calculate_age
from api.controller.files_controller import get_profile_photo_url, generate_file_url
from datetime import date, datetime
from services.translation import translate_message
from core.utils.helper import serialize_datetime_fields
from config.models.user_token_history_model import create_user_token_history
from schemas.user_token_history_schema import CreateTokenHistory
from config.models.user_models import *
from core.utils.core_enums import *
from core.utils.pagination import StandardResultsSetPagination

response = CustomResponseMixin()


async def get_profile_controller(user_id: str, lang: str = "en"):
    """
    Fetch profile using User + Onboarding data
    """
    user = await user_collection.find_one(
        {"_id": ObjectId(user_id)}
    )
    if not user:
        return response.error_message(translate_message("USER_NOT_FOUND", lang=lang), data=[], status_code=404)

    onboarding = await onboarding_collection.find_one(
        {"user_id": str(user["_id"])}
    )
    age = None
    if onboarding and onboarding.get("birthdate"):
        age = calculate_age(onboarding["birthdate"])

    membership_type = user.get("membership_type", "free")
    is_verified = user.get("is_verified", False)

    public_gallery = onboarding.get("public_gallery", []) if onboarding else []
    private_gallery = onboarding.get("private_gallery", []) if onboarding else []

    private_gallery_locked = membership_type == "free"

    profile_photo_url = await get_profile_photo_url({"_id": user["_id"]})

    gifts = []

    if is_verified:
        cursor = gift_collection.find(
            {"status": "active"}
        )

        async for gift in cursor:
            file_doc = await file_collection.find_one(
                {
                    "_id": ObjectId(gift["file_id"]),
                    "is_deleted": False
                }
            )

            if not file_doc:
                continue

            image_url = await generate_file_url(
                file_doc["storage_key"],
                file_doc["storage_backend"]
            )

            gifts.append({
                "gift_id": str(gift["_id"]),
                "name": gift["name"],
                "image_url": image_url,
                "token": gift["token"]
            })

    profile_data = [{
        "name": user.get("username"),
        "age": age,
        "email": user.get("email"),
        "profile_photo": profile_photo_url if profile_photo_url else None,
        "about": onboarding.get("bio"),
        "hobbies": onboarding.get("passions"),
        "gender": onboarding.get("gender"),
        "country": onboarding.get("country"),
        "orientation": onboarding.get("sexual_orientation"),
        "status": onboarding.get("marital_status"),
        "private_gallery": {
            "items": private_gallery,
            "count": len(private_gallery),
            "locked": private_gallery_locked
        },
        "public_gallery": {
            "items": public_gallery,
            "count": len(public_gallery)
        },
        "send_gifts": {
            "enabled": is_verified,
            "items": gifts
        }
    }]

    profile_data = serialize_datetime_fields(profile_data)
    return response.success_message(
        translate_message("PROFILE_FETCHED_SUCCESSFULLY", lang=lang),
        data=profile_data,
        status_code=200
    )

async def get_private_gallery_image(
    profile_user_id: str,
    viewer: dict,
    image_id: str,
    lang: str = "en"
):
    # 1. Find PROFILE OWNER onboarding
    onboarding = await onboarding_collection.find_one(
        {"user_id": profile_user_id}
    )

    if not onboarding:
        return response.error_message(
            translate_message("PROFILE_NOT_FOUND", lang=lang),
            status_code=404
        )

    # 2. Find image in PROFILE OWNER private gallery
    image = next(
        (img for img in onboarding.get("private_gallery", [])
         if img.get("file_id") == image_id),
        None
    )

    if not image:
        return response.error_message(
            translate_message("IMAGE_NOT_FOUND", lang=lang),
            status_code=404
        )

    # 3. Check if VIEWER already unlocked this image
    is_unlocked = image_id in viewer.get("unlocked_images", [])

    # 4. Fetch file
    file_doc = await file_collection.find_one(
        {"_id": ObjectId(image_id), "is_deleted": {"$ne": True}}
    )

    image_url = await generate_file_url(
        file_doc["storage_key"],
        file_doc.get("backend", "LOCAL")
    )

    return response.success_message(
        translate_message("PRIVATE_IMAGE_FETCHED", lang=lang),
        data=[{
            "image_id": image_id,
            "image_url": image_url,
            "price": image.get("price", 0),
            "is_unlocked": is_unlocked,
            "can_buy": not is_unlocked,
            "available_token": int(viewer.get("tokens", 0))
        }]
    )

async def buy_private_gallery_image(
    profile_user_id: str,
    image_id: str,
    viewer: dict,
    lang: str = "en"
):
    # 1. Fetch profile owner onboarding
    onboarding = await onboarding_collection.find_one(
        {"user_id": profile_user_id}
    )

    if not onboarding:
        return response.error_message(
            translate_message("PROFILE_NOT_FOUND", lang),
            status_code=404
        )

    # 2. Find image
    image = next(
        (img for img in onboarding.get("private_gallery", [])
         if img.get("file_id") == image_id),
        None
    )

    if not image:
        return response.error_message(
            translate_message("IMAGE_NOT_FOUND", lang),
            status_code=404
        )

    price = int(image.get("price", 0))

    # 3. FETCH FRESH VIEWER DATA
    viewer_db = await user_collection.find_one({"_id": viewer["_id"]})

    available_tokens = int(viewer_db.get("tokens", 0))
    unlocked_images = viewer_db.get("unlocked_images", [])

    # 4. Already unlocked
    if image_id in unlocked_images:
        return response.success_message(
            translate_message("IMAGE_ALREADY_UNLOCKED", lang),
            data={
                "image_id": image_id,
                "remaining_tokens": available_tokens,
                "is_unlocked": True
            }
        )

    # 5. Insufficient balance
    if available_tokens < price:
        return response.error_message(
            translate_message("INSUFFICIENT_TOKENS", lang),
            status_code=400
        )

    # 6. Deduct tokens
    new_token_balance = available_tokens - price

    await user_collection.update_one(
        {"_id": viewer["_id"]},
        {
            "$set": {"tokens": new_token_balance},
            "$addToSet": {"unlocked_images": image_id}
        }
    )

    # 7. Record token history
    await create_user_token_history(
        CreateTokenHistory(
            user_id=str(viewer["_id"]),
            delta=-price,
            type="DEBIT",
            reason="PRIVATE_IMAGE_UNLOCK",
            balance_before=str(available_tokens),
            balance_after=str(new_token_balance)
        )
    )

    return response.success_message(
        translate_message("IMAGE_UNLOCKED_SUCCESSFULLY", lang),
        data=[{
            "image_id": image_id,
            "remaining_tokens": new_token_balance,
            "is_unlocked": True
        }]
    )

async def get_profile_gallery(
    profile_user_id: str,
    viewer: dict,
    lang: str = "en"
):
    onboarding = await onboarding_collection.find_one(
        {"user_id": profile_user_id}
    )

    if not onboarding:
        return response.error_message("PROFILE_NOT_FOUND", status_code=404)

    unlocked_images = set(viewer.get("unlocked_images", []))

    # Public gallery
    public_gallery = []
    for img in onboarding.get("public_gallery", []):
        file_doc = await file_collection.find_one({"_id": ObjectId(img["file_id"])})
        url = await generate_file_url(file_doc["storage_key"], file_doc["storage_backend"])
        public_gallery.append({
            "image_id": img["file_id"],
            "image_url": url,
            "type": "public"
        })

    # Private gallery
    private_gallery = []
    for img in onboarding.get("private_gallery", []):
        file_doc = await file_collection.find_one({"_id": ObjectId(img["file_id"])})
        url = await generate_file_url(file_doc["storage_key"], file_doc["storage_backend"])

        private_gallery.append({
            "image_id": img["file_id"],
            "image_url": url,
            "price": int(img.get("price", 0)),
            "is_unlocked": img["file_id"] in unlocked_images
        })

    return response.success_message(
        translate_message("GALLERY_FETCHED_SUCCESSFULLY", lang),
        data=[{
            "public_gallery": public_gallery,
            "private_gallery": private_gallery
        }]
    )

async def send_gift_to_profile(
    profile_user_id: str,
    gift_id: str,
    viewer: dict,
    lang: str = "en"
):
    # Cannot send gift to self
    if str(viewer["_id"]) == profile_user_id:
        return response.error_message(
            translate_message("CANNOT_SEND_GIFT_TO_SELF", lang=lang),
            status_code=400
        )

    # Fetch receiver (only what we need)
    receiver = await get_user_details(
        condition={"_id": ObjectId(profile_user_id)},
        fields=["_id", "tokens"]
    )
    if not receiver:
        return response.error_message(
            translate_message("PROFILE_NOT_FOUND", lang=lang),
            status_code=404
        )

    # Fetch gift
    gift = await gift_collection.find_one(
        {"_id": ObjectId(gift_id), "status": "active"}
    )
    if not gift:
        return response.error_message(
            translate_message("GIFT_NOT_FOUND", lang=lang),
            status_code=404
        )

    gift_price = int(gift["token"])

    # Fetch fresh sender data
    sender = await get_user_details(
        condition={"_id": viewer["_id"]},
        fields=["_id", "tokens"]
    )
    if not sender:
        return response.error_message(
            translate_message("USER_NOT_FOUND", lang=lang),
            status_code=404
        )

    sender_tokens = int(sender.get("tokens", 0))
    receiver_tokens = int(receiver.get("tokens", 0))

    # Validate balance
    if sender_tokens < gift_price:
        return response.error_message(
            translate_message("INSUFFICIENT_TOKENS", lang=lang),
            status_code=400
        )

    # Calculate balances
    sender_new_balance = sender_tokens - gift_price
    receiver_new_balance = receiver_tokens + gift_price

    # Update users
    await user_collection.update_one(
        {"_id": viewer["_id"]},
        {"$set": {"tokens": sender_new_balance}}
    )

    await user_collection.update_one(
        {"_id": ObjectId(profile_user_id)},
        {"$set": {"tokens": receiver_new_balance}}
    )

    # Token history — sender
    await create_user_token_history(
        CreateTokenHistory(
            user_id=str(viewer["_id"]),
            delta=-gift_price,
            type="DEBIT",
            reason="GIFT_SENT",
            balance_before=str(sender_tokens),
            balance_after=str(sender_new_balance)
        )
    )

    # Token history — receiver
    await create_user_token_history(
        CreateTokenHistory(
            user_id=str(profile_user_id),
            delta=gift_price,
            type="CREDIT",
            reason="GIFT_RECEIVED",
            balance_before=str(receiver_tokens),
            balance_after=str(receiver_new_balance)
        )
    )

    return response.success_message(
        translate_message("GIFT_SENT_SUCCESSFULLY", lang=lang),
        data=[{
            "gift_id": gift_id,
            "gift_name": gift["name"],
            "tokens_deducted": gift_price,
            "sender_remaining_tokens": sender_new_balance
        }]
    )

async def search_profiles_controller(
    payload: dict,
    current_user: dict,
    pagination: StandardResultsSetPagination,
    lang: str = "en"
):
    user_membership = current_user.get("membership_type", MembershipType.FREE)
    is_premium = user_membership == MembershipType.PREMIUM

    query = {"onboarding_completed": True}

    # APPLY FREE FILTERS
    for payload_key, (db_field, operator) in FREE_FILTERS.items():
        if payload.get(payload_key):
            query[db_field] = {operator: payload[payload_key]}

    # APPLY PREMIUM FILTERS
    used_premium_filter = any(payload.get(k) for k in PREMIUM_FILTERS)

    if used_premium_filter and not is_premium:
        return response.error_message(
            translate_message("PREMIUM_REQUIRED_FOR_FILTERS", lang),
            status_code=403,
            data={"premium_required": True}
        )

    if is_premium:
        for payload_key, (db_field, operator) in PREMIUM_FILTERS.items():
            value = payload.get(payload_key)
            if not value:
                continue

            if operator == "$in":
                query[db_field] = {"$in": value}

            elif operator == "range":
                today = date.today()
                birthdate_query = {}

                if value.get("min"):
                    birthdate_query["$lte"] = today.replace(
                        year=today.year - value["min"]
                    )

                if value.get("max"):
                    birthdate_query["$gte"] = today.replace(
                        year=today.year - value["max"]
                    )

                if birthdate_query:
                    query[db_field] = birthdate_query

    # QUERY WITH PAGINATION
    cursor = (
        onboarding_collection
        .find(query)
        .skip(pagination.skip)
        .limit(pagination.limit)
    )

    results = []

    async for onboarding in cursor:
        user = await user_collection.find_one(
            {"_id": ObjectId(onboarding["user_id"]), "is_deleted": {"$ne": True}}
        )
        if not user:
            continue

        birthdate = onboarding.get("birthdate")

        age = calculate_age(birthdate) if birthdate else None

        results.append({
            "user_id": str(user["_id"]),
            "name": user.get("username"),
            "age": age,
            "city": onboarding.get("country"),
            "profile_photo": await get_profile_photo_url({"_id": user["_id"]}),
            "is_verified": user.get("is_verified", False),
            "login_status": user.get("login_status")
        })

    return response.success_message(
        translate_message("SEARCH_RESULTS_FETCHED", lang),
        data=[{
            "results": results,
            "page": pagination.page,
            "page_size": pagination.page_size,
            "premium_required": False
        }]
    )
