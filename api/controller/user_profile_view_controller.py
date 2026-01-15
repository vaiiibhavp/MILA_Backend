# user_profile_view_controller.py

from core.utils.response_mixin import CustomResponseMixin
from services.translation import translate_message
from services.profile_fetch_service import fetch_basic_profile_data
from services.profile_mapper import build_edit_profile_response
from schemas.profile_edit_schema import *
from core.utils.core_enums import *
from config.db_config import *
from datetime import datetime, timezone
from config.models.user_models import *
from services.premium_guard import require_premium
from api.controller.files_controller import get_profile_photo_url, generate_file_url, save_file
from fastapi import UploadFile
from bson import ObjectId
from services.profile_fetch_service import *
from config.models.onboarding_model import *
from core.utils.helper import *

response = CustomResponseMixin()

async def get_edit_profile_controller(current_user: dict, lang: str = "en"):
    user, onboarding = await fetch_basic_profile_data(
        str(current_user["_id"])
    )

    if not user:
        return response.error_message(
            translate_message("USER_NOT_FOUND", lang),
            status_code=404
        )

    data = await build_edit_profile_response(user, onboarding)

    data = serialize_datetime_fields(convert_objectid_to_str(data))

    return response.success_message(
        translate_message("EDIT_PROFILE_DATA_FETCHED_SUCCESSFULLY", lang),
        data=[data],
        status_code=200
    )

async def update_edit_profile_controller(
    payload: EditProfileRequest,
    current_user: dict,
    lang: str = "en"
):
    """
    Update editable profile fields
    """
    user_id = str(current_user["_id"])

    # FETCH USER 
    user = await get_user_details(
        {"_id": current_user["_id"]},
        fields=["membership_type"]
    )

    if not user:
        return response.error_message(
            translate_message("USER_NOT_FOUND", lang),
            status_code=404
        )

    is_premium = user.get("membership_type") == MembershipType.PREMIUM

    # USER UPDATE
    user_update = {}

    if payload.wallet_address is not None:
        user_update["wallet_address"] = payload.wallet_address

    if payload.two_factor_enabled is not None:
        user_update["two_factor_enabled"] = payload.two_factor_enabled

    if user_update:
        user_update["updated_at"] = datetime.utcnow()
        await user_collection.update_one(
            {"_id": current_user["_id"]},
            {"$set": user_update}
        )

    # ONBOARDING UPDATE
    onboarding_update = {}

    # BASIC DETAILS
    if payload.bio is not None:
        onboarding_update["bio"] = payload.bio

    if payload.country is not None:
        onboarding_update["country"] = payload.country

    if payload.gender is not None:
        onboarding_update["gender"] = payload.gender

    if payload.sexual_orientation is not None:
        onboarding_update["sexual_orientation"] = payload.sexual_orientation

    if payload.marital_status is not None:
        onboarding_update["marital_status"] = payload.marital_status

    # INTERESTS
    if payload.passions is not None:
        onboarding_update["passions"] = payload.passions

    if payload.interested_in is not None:
        onboarding_update["interested_in"] = payload.interested_in

    if payload.preferred_country is not None:
        onboarding_update["preferred_country"] = payload.preferred_country

    # PREMIUM-ONLY
    if payload.sexual_preferences is not None:
        if not is_premium:
            return response.error_message(
                translate_message("PREMIUM_REQUIRED", lang),
                status_code=403,
                data={"premium_required": True}
            )
        onboarding_update["sexual_preferences"] = payload.sexual_preferences

    if onboarding_update:
        onboarding_update["updated_at"] = datetime.utcnow()
        await onboarding_collection.update_one(
            {"user_id": user_id},
            {
                "$set": onboarding_update,
                "$setOnInsert": {
                    "user_id": user_id,
                    "created_at": datetime.utcnow()
                }
            },
            upsert=True
        )

    return response.success_message(
        translate_message("PROFILE_UPDATED_SUCCESSFULLY", lang),
        data=[{"updated": True}],
        status_code=200
    )

async def retry_verification_selfie_controller(
    selfie: UploadFile,
    current_user: dict,
    lang: str = "en"
):
    user_id = str(current_user["_id"])

    # VALIDATE USER STATUS
    if current_user.get("is_verified") is True:
        return response.error_message(
            translate_message("ALREADY_VERIFIED", lang),
            status_code=400
        )

    if not selfie:
        return response.error_message(
            translate_message("SELFIE_REQUIRED", lang),
            status_code=400
        )

    # SAVE SELFIE FILE
    _, storage_key, backend = await save_file(
        file_obj=selfie,
        file_name=selfie.filename,
        user_id=user_id,
        file_type="verification_selfie"
    )

    file_doc = Files(
        storage_key=storage_key,
        storage_backend=backend,
        file_type=FileType.SELFIE,
        uploaded_by=user_id
    )

    file_result = await file_collection.insert_one(
        file_doc.dict(by_alias=True)
    )

    selfie_file_id = str(file_result.inserted_id)

    # GENERATE IMAGE URL
    selfie_image_url = await generate_file_url(
        storage_key=storage_key,
        backend=backend
    )

    # UPDATE ONBOARDING
    await onboarding_collection.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "selfie_image": selfie_file_id,
                "updated_at": datetime.utcnow()
            },
            "$setOnInsert": {
                "user_id": user_id,
                "created_at": datetime.utcnow()
            }
        },
        upsert=True
    )

    await verification_collection.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "status": "pending",
                "verified_by_admin_id": None,
                "verified_at": None,
                "updated_at": datetime.utcnow()
            },
            "$setOnInsert": {
                "user_id": user_id,
                "created_at": datetime.utcnow()
            }
        },
        upsert=True
    )
    
    # UPDATE USER STATUS
    await user_collection.update_one(
        {"_id": current_user["_id"]},
        {
            "$set": {
                "is_verified": False,
                "updated_at": datetime.utcnow()
            }
        }
    )

    return response.success_message(
        translate_message("SELFIE_SUBMITTED_FOR_VERIFICATION", lang),
        data=[{
            "status": "pending",
            "selfie_image_url": selfie_image_url
        }],
        status_code=200
    )

async def get_verification_selfie_controller(
    current_user: dict,
    lang: str = "en"
):
    # BLOCK if already verified
    if current_user.get("is_verified") is True:
        return response.success_message(
            translate_message("USER_ALREADY_VERIFIED", lang),
            data=[{"selfie_url": None}],
            status_code=200
        )

    user_id = str(current_user["_id"])

    onboarding = await onboarding_collection.find_one(
        {"user_id": user_id},
        {"selfie_image": 1}
    )

    if not onboarding or not onboarding.get("selfie_image"):
        return response.success_message(
            translate_message("NO_VERIFICATION_SELFIE_FOUND", lang),
            data=[{"selfie_url": None}],
            status_code=200
        )

    file_doc = await file_collection.find_one(
        {"_id": ObjectId(onboarding["selfie_image"])}
    )

    if not file_doc:
        return response.error_message(
            translate_message("FILE_NOT_FOUND", lang),
            status_code=404
        )

    selfie_url = await generate_file_url(
        storage_key=file_doc["storage_key"],
        backend=file_doc["storage_backend"]
    )

    return response.success_message(
        translate_message("VERIFICATION_SELFIE_FETCHED", lang),
        data=[{"selfie_url": selfie_url}],
        status_code=200
    )

async def get_notifications_controller(current_user,lang: str = "en"):

    user_id = str(current_user["_id"])

    notifications = await notification_collection.find(
        {
            "recipient_id": user_id,
            "recipient_type": "user"
        }
    ).sort("created_at", -1).to_list(length=100)

    today = []
    earlier = []

    today_date = datetime.now(timezone.utc).date()

    for n in notifications:
        created_at = n["created_at"]

        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))

        if created_at.date() == today_date:
            today.append(format_notification(n))
        else:
            earlier.append(format_notification(n))

    return response.success_message(
        translate_message("NOTIFICATION_FETCHED", lang),
        data=[{
            "today": today,
            "earlier": earlier
        }],
        status_code=200
    )

async def mark_notification_read(notification_id: str, current_user, lang: str = "en"):
    user_id = str(current_user["_id"])

    result = await notification_collection.update_one(
        {
            "_id": ObjectId(notification_id),
            "recipient_id": user_id
        },
        {
            "$set": {
                "is_read": True,
                "read_at": datetime.now(timezone.utc)
            }
        }
    )

    if result.matched_count == 0:
        return response.error_message(
            translate_message("NOTIFICATION_NOT_FOUND", lang),
            status_code=404
        )

    return response.success_message(
        translate_message("NOTIFICATION_MARKED_AS_READ", lang),
        status_code=200
    )

async def mark_all_notifications_read(current_user, lang):
    user_id = str(current_user["_id"])

    await notification_collection.update_many(
        {
            "recipient_id": user_id,
            "is_read": False
        },
        {
            "$set": {
                "is_read": True,
                "read_at": datetime.now(timezone.utc)
            }
        }
    )

    return response.success_message(
        translate_message("ALL_NOTIFICATION_MARKED_AS_READ", lang),
        status_code=200
    )

async def delete_account_controller(current_user: dict, lang: str):
    await user_collection.update_one(
        {"_id": current_user["_id"]},
        {
            "$set": {
                "is_deleted": True,
                "deleted_at": datetime.utcnow(),
                "deleted_by": "user"
            }
        }
    )

    return response.success_message(
        translate_message("ACCOUNT_DELETED_SUCCESSFULLY", lang),
        status_code=200
    )
