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
from api.controller.onboardingController import *
from services.profile_fetch_service import *
from services.profile_mapper import *
from schemas.language_schema import *
from services.gallery_service import *
from api.controller.files_controller import *
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
        return response.error_message(translate_message("USER_NOT_FOUND", lang=lang), data=[], status_code=404)
    viewer_unlocked_images = set()

    if user:
        viewer_db = await user_collection.find_one(
            {"_id": user["_id"]},
            {"unlocked_images": 1}
        )
        viewer_unlocked_images = set(viewer_db.get("unlocked_images", []))

    is_owner = str(user["_id"]) == str(current_user["_id"])
    onboarding = await onboarding_collection.find_one(
        {"user_id": str(user["_id"])}
    )
    age = None
    if onboarding and onboarding.get("birthdate"):
        age = calculate_age(onboarding["birthdate"])

    verification_status = user.get("is_verified")
    membership_type = user.get("membership_type", "free")

    verification_record = await verification_collection.find_one(
        {"user_id": str(user["_id"])},
        sort=[("created_at", -1)]
    )

    screen_state = "unverified_pending"
    show_badge = False
    show_retry = False

    if verification_record:
        if verification_record["status"] == "approved":
            screen_state = "verified_user"
            show_badge = True
        elif verification_record["status"] == "rejected":
            screen_state = "unverified_rejected"
            show_retry = True

    public_gallery_raw = onboarding.get("public_gallery", []) if onboarding else []
    private_gallery_raw = onboarding.get("private_gallery", []) if onboarding else []

    public_gallery = await resolve_public_gallery_items(public_gallery_raw)
    private_gallery = await resolve_private_gallery_items(
        private_gallery_raw,
        viewer_unlocked_images=viewer_unlocked_images,
        is_owner=is_owner
    )

    private_gallery_locked = membership_type == "free"

    tokens = await get_user_token_balance(str(user["_id"]))
    profile_photo = await profile_photo_from_onboarding(onboarding)

    profile_data = [{
            "name": user.get("username"),
            "age": age,
            "email": user.get("email"),
            "profile_photo": profile_photo,
            "about": onboarding.get("bio") if onboarding else None,
            "screen_state": screen_state,
            "verification": {
                "status": screen_state,
                "show_badge": show_badge,
                "show_retry": show_retry,
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
        translate_message("PROFILE_FETCHED_SUCCESSFULLY", lang=lang),
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
        return response.error_message(translate_message("PUBLIC_GALLERY_IMAGES_REQUIRED", lang=lang), data=[], status_code=400)

    user_id = str(current_user["_id"])

    existing_count = await get_gallery_count(
        user_id=user_id,
        gallery_field="public_gallery"
    )

    incoming_count = len(images)

    # Enforce TOTAL limit (existing + new)
    if existing_count + incoming_count > 5:
        return response.error_message(
            translate_message("PUBLIC_GALLERY_MAX_LIMIT_EXCEEDED", lang=lang),
            data={
                "allowed": max(0, 5 - existing_count),
                "existing": existing_count,
                "max_limit": 5
            },
            status_code=400
        )

    public_items = []

    for image in images:
        size_error = await validate_image_size(image, lang)
        if size_error:
            return size_error
        
        item = await create_and_store_file(
            file_obj=image,
            user_id=str(current_user["_id"]),
            file_type=FileType.PUBLIC_GALLERY
        )
        public_items.append(item)

    await append_gallery_items(
        user_id=str(current_user["_id"]),
        gallery_field="public_gallery",
        items=public_items
    )

    resolved_items = await resolve_public_gallery_items(public_items)

    return response.success_message(
        translate_message("PUBLIC_GALLERY_IMAGES_UPLOADED_SUCCESSFULLY", lang),
        data=[serialize_datetime_fields({
            "count": len(resolved_items),
            "items": resolved_items
        })],
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

    user_id = str(current_user["_id"])

    # Validate user
    user = await user_collection.find_one({"_id": ObjectId(user_id)})
    if not user:
        return response.error_message(
            translate_message("USER_NOT_FOUND", lang),
            status_code=404
        )

    # Only one image allowed
    if not image or len(image) != 1:
        return response.error_message(
            translate_message(
                "PLEASE_SELECT_ONE_IMAGE_AT_A_TIME_WITH_ITS_PRICE",
                lang=lang
            ),
            data=[],
            status_code=400
        )

    size_error = await validate_image_size(image[0], lang)
    if size_error:
        return size_error
    
    # PRICE VALIDATION (string-safe)
    if price is None or price.strip() == "":
        return response.error_message(
            translate_message("PLEASE_ENTER_A_VALID_PRICE", lang),
            status_code=400
        )

    if not price.isdigit():
        return response.error_message(
            translate_message("ONLY_NUMERIC_VALUES_ALLOWED", lang),
            status_code=400
        )

    price = int(price)

    if price <= 0:
        return response.error_message(
            translate_message("PRICE_MUST_BE_GREATER_THAN_ZERO", lang),
            status_code=400
        )

    onboarding = await onboarding_collection.find_one(
        {"user_id": str(current_user["_id"])},
        {"private_gallery": 1}
    )

    existing_count = len(onboarding.get("private_gallery", [])) if onboarding else 0
    membership = current_user.get("membership_type", "free")
    max_limit = 3 if membership == "free" else 20

    if existing_count >= max_limit:
        return response.error_message(
            translate_message("PRIVATE_GALLERY_LIMIT_REACHED_UPGRADE_TO_PREMIUM_TO_ADD_MORE_PHOTOS", lang=lang),
            data=[],
            status_code=403 if membership == "free" else 400,
        )

    base_item = await create_and_store_file(
        file_obj=image[0],
        user_id=str(current_user["_id"]),
        file_type=FileType.PRIVATE_GALLERY
    )

    private_item = {
        **base_item,
        "price": price
    }

    await append_gallery_items(
        user_id=str(current_user["_id"]),
        gallery_field="private_gallery",
        items=[private_item]
    )

    # Generate URL for response (owner → always unlocked)
    file_doc = await file_collection.find_one(
        {"_id": ObjectId(private_item["file_id"])}
    )

    image_url = await generate_file_url(
        file_doc["storage_key"],
        file_doc["storage_backend"]
    )

    # Response payload
    response_item = {
        "file_id": private_item["file_id"],
        "url": image_url,
        "uploaded_at": private_item["uploaded_at"],
        "price": private_item["price"],
        "is_unlocked": True,  # owner always unlocked
        "remaining_slots": max_limit - (existing_count + 1)
    }

    return response.success_message(
        translate_message(
            "PRIVATE_GALLERY_IMAGE_UPLOADED_SUCCESSFULLY",
            lang
        ),
        data=[serialize_datetime_fields(response_item)],
        status_code=200
    )

async def get_public_gallery_controller(current_user, lang: str = "en"):
    onboarding = await onboarding_collection.find_one(
        {"user_id": str(current_user["_id"])},
        {"public_gallery": 1}
    )

    gallery = onboarding.get("public_gallery", []) if onboarding else []

    items = await resolve_public_gallery_items(gallery)

    response_data = serialize_datetime_fields({
        "count": len(items),
        "items": items
    })

    return response.success_message(
        translate_message("PUBLIC_GALLERY_FETCHED_SUCCESSFULLY", lang=lang),
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

    items = await resolve_private_gallery_items(
        gallery=gallery,
        viewer_unlocked_images=set(),
        is_owner=True
    )

    response_data = serialize_datetime_fields({
        "count": len(items),
        "items": items,
        "max_limit": max_limit
    })

    return response.success_message(
        translate_message("PRIVATE_GALLERY_FETCHED_SUCCESSFULLY", lang=lang),
        data=[response_data],
        status_code=200
    )

async def get_basic_profile_details_controller(
    current_user: dict,
    lang: str = "en"
):
    """
    Fetch complete basic profile details for logged-in user (Basic Info View)
    """
    user, onboarding = await fetch_basic_profile_data(str(current_user["_id"]))

    if not user:
        return response.error_message(
            translate_message("USER_NOT_FOUND", lang),
            status_code=404
        )

    profile_photo = await profile_photo_from_onboarding(onboarding)

    data = await build_basic_profile_response(
        user=user,
        onboarding=onboarding,
        profile_photo=profile_photo
    )

    return response.success_message(
        translate_message("BASIC_PROFILE_FETCHED_SUCCESSFULLY", lang),
        data=[serialize_datetime_fields(data)],
        status_code=200
    )

async def change_language_controller(
    payload: ChangeLanguageRequest,
    current_user: dict,
    lang: str = "en"
):
    """
    Change application language for logged-in user(Change Language)
    """
    await user_collection.update_one(
        {"_id": ObjectId(current_user["_id"])},
        {"$set": {"language": payload.language.value}}
    )

    return response.success_message(
        translate_message("LANGUAGE_UPDATED_SUCCESSFULLY", lang),
        data=[{
            "language": payload.language.value
        }],
        status_code=200
    )

async def delete_gallery_image_controller(
    file_id: str,
    gallery_field: str,
    current_user: dict,
    lang: str = "en"
):
    user_id = str(current_user["_id"])

    # Validate ObjectId
    try:
        ObjectId(file_id)
    except Exception:
        return response.error_message(
            translate_message("INVALID_FILE_ID", lang),
            status_code=400
        )

    # Ownership + existence check
    onboarding = await find_gallery_item(
        user_id=user_id,
        gallery_field=gallery_field,
        file_id=file_id
    )

    if not onboarding:
        return response.error_message(
            translate_message("IMAGE_NOT_FOUND_IN_GALLERY", lang),
            status_code=404
        )

    # Remove from gallery
    await remove_gallery_item(
        user_id=user_id,
        gallery_field=gallery_field,
        file_id=file_id
    )

    # Soft delete file
    await soft_delete_file(
        file_id=file_id,
        deleted_by=user_id
    )

    return response.success_message(
        translate_message("GALLERY_IMAGE_DELETED_SUCCESSFULLY", lang),
        data=[{"file_id": file_id}],
        status_code=200
    )

async def get_user_details_controller(current_user: dict, lang: str = "en"):
    try:
        user_id = str(current_user.get("_id") or current_user.get("id"))

        user_data = await fetch_user_by_id(user_id, lang)

        return response.success_message(
            translate_message("USER_DETAILS_FETCHED_SUCCESSFULLY", lang),
            data=[user_data],
            status_code=200
        )

    except Exception as e:
        return response.error_message(
            translate_message("ERROR_WHILE_FETCHING_USER_DETAILS", lang),
            data=[str(e)],
            status_code=500
        )
