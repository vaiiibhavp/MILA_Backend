#profile_controller.py:

from bson import ObjectId
from config.db_config import user_collection, onboarding_collection, file_collection
from core.utils.response_mixin import CustomResponseMixin
from core.utils.age_calculation import calculate_age
from api.controller.files_controller import save_file, generate_file_url, get_profile_photo_url
from datetime import date, datetime
from services.translation import translate_message
from core.utils.helper import serialize_datetime_fields
from config.basic_config import settings
from config.models.user_models import Files, FileType

response = CustomResponseMixin()

VERIFICATION_REWARD_TOKENS=settings.VERIFICATION_REWARD_TOKENS

async def get_user_profile_controller(current_user: dict, lang: str = "en"):
    """
    Fetch profile using User + Onboarding data
    """
    user = await user_collection.find_one(
        {"_id": ObjectId(current_user["_id"])}
    )
    if not user:
        return response.error_message(translate_message("User not found", lang=lang), data=[], status_code=404)

    onboarding = await onboarding_collection.find_one(
        {"user_id": str(user["_id"])}
    )
    age = None
    if onboarding and onboarding.get("birthdate"):
        age = calculate_age(onboarding["birthdate"])

    verification_status = user.get("is_verified")
    reward_given = user.get("verification_reward_given", False)

    if verification_status is True and not reward_given:
        new_tokens = user.get("tokens", 0) + VERIFICATION_REWARD_TOKENS

        await user_collection.update_one(
            {"_id": user["_id"]},
            {
                "$set": {
                    "tokens": new_tokens,
                    "verification_reward_given": True
                }
            }
        )
        user["tokens"] = new_tokens
        user["verification_reward_given"] = True
    membership_type = user.get("membership_type", "free")

    if verification_status == True:
        screen_state = "verified_user"
    elif verification_status == False:
        screen_state = "unverified_rejected"
    else:
        screen_state = "unverified_pending"

    public_gallery = onboarding.get("public_gallery", []) if onboarding else []
    private_gallery = onboarding.get("private_gallery", []) if onboarding else []

    private_gallery_locked = membership_type == "free"

    tokens = user.get("tokens", 0)
    profile_photo_url = await get_profile_photo_url(current_user)

    profile_data = [{
            "name": user.get("username"),
            "age": age,
            "email": user.get("email"),
            "profile_photo": profile_photo_url,
            "about": onboarding.get("bio"),
            "screen_state": screen_state,
            "verification": {
                "status": verification_status,
                "show_badge": verification_status == "verified",
                "show_retry": verification_status == "rejected",
            },
            "tokens": tokens,
            "membership": {
                "type": membership_type,
                "show_upgrade": membership_type == "free"
            },
            "public_gallery": {
                "items": public_gallery,
                "count": len(public_gallery)
            },
            "private_gallery": {
                "items": private_gallery,
                "count": len(private_gallery),
                "locked": private_gallery_locked
            },
            "menu": {
                "basic_details": True,
                "favourites": True,
                "subscription_billing": True,
                "notifications": True,
                "change_language": True,
                "logout": True
            }
        }]

    profile_data = serialize_datetime_fields(profile_data)

    return response.success_message(
        translate_message("Profile fetched successfully", lang=lang),
        data=profile_data,
        status_code=200
    )

async def upload_public_gallery_controller(images, current_user, lang: str = "en"):
    """
    Public Gallery Rules:
    - Multiple images allowed
    - No price
    - Max 5 images (BRD)
    """

    if not images:
        return response.error_message(translate_message("No images provided", lang=lang), data=[], status_code=400)

    if len(images) > 5:
        return response.error_message(
            translate_message("Maximum 5 public gallery images allowed", lang=lang),
            data=[],
            status_code=400
        )

    public_items = []

    for image in images:
        public_url, storage_key, backend = await save_file(
            file_obj=image,
            file_name=image.filename,
            user_id=str(current_user["_id"]),
            file_type="public_gallery"
        )

        file_doc = Files(
            storage_key=storage_key,
            storage_backend=backend,
            file_type=FileType.PUBLIC_GALLERY,
            uploaded_by=str(current_user["_id"])
        )

        result = await file_collection.insert_one(file_doc.dict(by_alias=True))
        file_id = str(result.inserted_id)

        public_items.append({
            "file_id": file_id,
            "uploaded_at": datetime.utcnow()
        })
        
        await onboarding_collection.update_one(
            {"user_id": str(current_user["_id"])},
            {
                "$push": {"public_gallery": {"$each": public_items}},
                "$setOnInsert": {
                    "user_id": str(current_user["_id"]),
                    "created_at": datetime.utcnow()
                },
                "$set": {"updated_at": datetime.utcnow()}
            },
            upsert=True
        )
    response_data = serialize_datetime_fields({
            "count": len(public_items),
            "items": public_items
        })

    return response.success_message(
        translate_message("Public gallery images uploaded successfully", lang=lang),
        data=[response_data],
        status_code=200
    )

async def upload_private_gallery_controller(image, price, current_user, lang: str= "en"):
    """
    Private Gallery Rules (UPDATED):
    - Single image per upload
    - Price required
    - Free users: max 3 images
    - Premium users: max 20 images
    """

    if price <= 0:
        return response.error_message(
            translate_message("Price must be greater than zero", lang=lang),
            data=[],
            status_code=400
        )

    onboarding = await onboarding_collection.find_one(
        {"user_id": str(current_user["_id"])},
        {"private_gallery": 1}
    )

    existing_count = len(onboarding.get("private_gallery", [])) if onboarding else 0
    membership = current_user.get("membership_type")

    max_limit = 3 if membership == "free" else 20

    if existing_count >= max_limit:
        return response.error_message(
            translate_message(f"Private gallery limit reached. Upgrade to premium to add more photos.", lang=lang),
            data=[],
            status_code=403 if membership == "free" else 400,
        )

    public_url, storage_key, backend = await save_file(
        file_obj=image,
        file_name=image.filename,
        user_id=str(current_user["_id"]),
        file_type="private_gallery"
    )

    file_doc = Files(
        storage_key=storage_key,
        storage_backend=backend,
        file_type=FileType.PRIVATE_GALLERY,
        uploaded_by=str(current_user["_id"])
    )

    result = await file_collection.insert_one(file_doc.dict(by_alias=True))
    file_id = str(result.inserted_id)

    # Store reference in onboarding
    private_item = {
        "file_id": file_id,
        "price": price,
        "uploaded_at": datetime.utcnow()
    }

    await onboarding_collection.update_one(
        {"user_id": str(current_user["_id"])},
        {
            "$push": {"private_gallery": private_item},
            "$setOnInsert": {
                "user_id": str(current_user["_id"]),
                "created_at": datetime.utcnow()
            },
            "$set": {"updated_at": datetime.utcnow()}
        },
        upsert=True
    )
    response_data = serialize_datetime_fields({
        **private_item,
        "remaining_slots": max_limit - (existing_count + 1)
    })

    return response.success_message(
        translate_message("Private gallery image uploaded successfully", lang=lang),
        data=[response_data],
        status_code=200
    )

async def get_public_gallery_controller(current_user, lang: str = "en"):
    onboarding = await onboarding_collection.find_one(
        {"user_id": str(current_user["_id"])},
        {"public_gallery": 1}
    )

    gallery = onboarding.get("public_gallery", []) if onboarding else []

    result = []

    for item in gallery:
        file_id = item.get("file_id")
        if not file_id:
            continue

        file_doc = await file_collection.find_one(
            {
                "_id": ObjectId(file_id),
                "is_deleted": {"$ne": True}
            }
        )

        if not file_doc:
            continue

        image_url = await generate_file_url(
            storage_key=file_doc["storage_key"],
            backend=file_doc["storage_backend"]
        )

        result.append({
            "file_id": file_id,
            "url": image_url,
            "uploaded_at": item.get("uploaded_at")
        })

    response_data = serialize_datetime_fields({
        "count": len(result),
        "items": result
    })

    return response.success_message(
        translate_message("Public gallery fetched successfully", lang=lang),
        data=[response_data],
        status_code=200
    )

async def get_private_gallery_controller(current_user, lang: str = "en"):
    onboarding = await onboarding_collection.find_one(
        {"user_id": str(current_user["_id"])},
        {"private_gallery": 1}
    )

    gallery = onboarding.get("private_gallery", []) if onboarding else []

    membership = current_user.get("membership_type", "free")
    max_limit = 3 if membership == "free" else 20

    result = []

    for item in gallery:
        file_id = item.get("file_id")
        if not file_id:
            continue

        file_doc = await file_collection.find_one(
            {
                "_id": ObjectId(file_id),
                "is_deleted": {"$ne": True}
            }
        )

        if not file_doc:
            continue

        image_url = await generate_file_url(
            storage_key=file_doc["storage_key"],
            backend=file_doc["storage_backend"]
        )

        result.append({
            "file_id": file_id,
            "url": image_url,
            "uploaded_at": item.get("uploaded_at")
        })

    response_data = serialize_datetime_fields({
        "count": len(result),
        "items": result
    })

    return response.success_message(
        translate_message("Private gallery fetched successfully", lang=lang),
        data=[response_data],
        status_code=200
    )
