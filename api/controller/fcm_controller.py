from datetime import datetime
from fastapi import Depends
from core.utils.response_mixin import CustomResponseMixin
from config.models.notification_model import * 
from config.db_config import fcm_device_tokens_collection
from services.translation import translate_message
from fastapi.encoders import jsonable_encoder
from core.utils.pagination import StandardResultsSetPagination

response = CustomResponseMixin()


async def register_fcm_token_controller(payload: dict, current_user: dict, lang: str):
    user_id = str(current_user["_id"])

    await fcm_device_tokens_collection.update_one(
        {
            "user_id": user_id,
            "device_token": payload["device_token"]
        },
        {
            "$set": {
                "user_id": user_id,
                "device_token": payload["device_token"],
                "device_type": payload.get("device_type"),
                "device_name": payload.get("device_name"),
                "status": DeviceStatus.ACTIVE.value,
                "updated_at": datetime.utcnow()
            },
            "$setOnInsert": {
                "created_at": datetime.utcnow()
            }
        },
        upsert=True
    )
    return response.success_message(
        translate_message("FCM_TOKEN_REGISTERED", lang),
        status_code=200
    )

async def get_fcm_tokens_controller(
    current_user: dict,
    pagination: StandardResultsSetPagination,
    lang: str
):
    user_id = str(current_user["_id"])

    # Total count (for pagination metadata)
    total = await fcm_device_tokens_collection.count_documents(
        {"user_id": user_id}
    )

    cursor = fcm_device_tokens_collection.find(
        {"user_id": user_id}
    ).skip(pagination.skip).limit(pagination.limit)

    tokens = await cursor.to_list(length=pagination.limit)

    # Convert ObjectId → str
    for token in tokens:
        token["_id"] = str(token["_id"])

    return response.success_message(
        translate_message("FCM_TOKENS_FETCHED", lang),
        data=[{
            "pagination": {
                "page": pagination.page,
                "page_size": pagination.page_size,
                "total_records": total,
                "total_pages": (total + pagination.page_size - 1) // pagination.page_size
            },
            "results": jsonable_encoder(tokens)
        }],
        status_code=200
    )


async def deactivate_fcm_token_controller(payload: dict, current_user: dict, lang: str):
    user_id = str(current_user["_id"])
    device_token = payload.get("device_token")

    if not device_token:
        return response.error_message(
            translate_message("DEVICE_TOKEN_REQUIRED", lang),
            status_code=400
        )

    result = await fcm_device_tokens_collection.update_one(
        {
            "user_id": user_id,
            "device_token": device_token
        },
        {
            "$set": {
                "status": DeviceStatus.INACTIVE.value,
                "updated_at": datetime.utcnow()
            }
        }
    )

    if result.matched_count == 0:
        return response.error_message(
            translate_message("FCM_TOKEN_NOT_FOUND", lang),
            status_code=404
        )

    return response.success_message(
        translate_message("FCM_TOKEN_DEACTIVATED", lang),
        status_code=200
    )

async def delete_fcm_token_controller(payload: dict, current_user: dict, lang: str):
    user_id = str(current_user["_id"])
    device_token = payload.get("device_token")

    if not device_token:
        return response.error_message(
            translate_message("DEVICE_TOKEN_REQUIRED", lang),
            status_code=400
        )

    result = await fcm_device_tokens_collection.delete_one(
        {
            "user_id": user_id,
            "device_token": device_token
        }
    )

    if result.deleted_count == 0:
        return response.error_message(
            translate_message("FCM_TOKEN_NOT_FOUND", lang),
            status_code=404
        )

    return response.success_message(
        translate_message("FCM_TOKEN_DELETED", lang),
        status_code=200
    )
