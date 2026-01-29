from datetime import datetime
from bson import ObjectId
import re
from core.utils.response_mixin import CustomResponseMixin
from core.utils.helper import serialize_datetime_fields
from api.controller.onboardingController import fetch_user_by_id
from config.db_config import blocked_users_collection , reported_users_collection , user_collection
from services.translation import translate_message
from core.utils.core_enums import NotificationType, NotificationRecipientType
from services.notification_service import send_notification
from core.utils.helper import get_admin_id_by_email



response = CustomResponseMixin()

async def block_user_controller(
    blocker_id: str,
    blocked_id: str,
    lang: str = "en"
):
    # Cannot block self
    if blocker_id == blocked_id:
        return response.error_message(
            translate_message("CANNOT_BLOCK_SELF", lang),
            status_code=400,
            data=[]
        )
    if not blocked_id or not blocked_id.strip():
        return response.error_message(
            translate_message("USER_ID_REQUIRED", lang),
            status_code=400,
            data=[]
        )

    if not ObjectId.is_valid(blocked_id):
        return response.error_message(
            translate_message("INVALID_USER_ID", lang),
            status_code=400,
            data=[]
        )

    blocked_user = await user_collection.find_one(
        {"_id": ObjectId(blocked_id), "is_deleted": {"$ne": True}},
        {"_id": 1}
    )

    if not blocked_user:
        return response.error_message(
            translate_message("USER_NOT_FOUND", lang),
            status_code=404,
            data=[]
        )

    already_blocked = await blocked_users_collection.find_one({
        "blocker_id": blocker_id,
        "blocked_id": blocked_id
    })

    if already_blocked:
        return response.success_message(
            translate_message("USER_ALREADY_BLOCKED", lang),
            data=[{
                "blocked_user_id": blocked_id
            }],
            status_code=400
        )

    await blocked_users_collection.insert_one({
        "blocker_id": blocker_id,
        "blocked_id": blocked_id,
        "created_at": datetime.utcnow()
    })

    admin_id = await get_admin_id_by_email()
    await send_notification(
        recipient_id=admin_id,
        recipient_type=NotificationRecipientType.ADMIN,
        notification_type=NotificationType.BLOCK,
        title=translate_message("PUSH_TITLE_USER_BLOCKED", lang),
        message=translate_message("PUSH_MESSAGE_USER_BLOCKED", lang),
        reference={
            "entity": "user_block",
            "entity_id": blocked_id,
            "blocked_by": blocker_id
        },
        sender_user_id=blocker_id,
        send_push=False
    )

    return response.success_message(
        translate_message("USER_BLOCKED_SUCCESSFULLY", lang),
        data=[{
            "blocked_user_id": blocked_id
        }],
        status_code=200
    )

async def report_user_controller(
    reporter_id: str,
    reported_id: str,
    reason: str,
    lang: str = "en"
):
    # Cannot report self
    if reporter_id == reported_id:
        return response.error_message(
            translate_message("CANNOT_REPORT_SELF", lang),
            status_code=400,
            data=[]
        )

    if not reported_id or not reported_id.strip():
        return response.error_message(
            translate_message("USER_ID_REQUIRED", lang),
            status_code=400,
            data=[]
        )

    if not ObjectId.is_valid(reported_id):
        return response.error_message(
            translate_message("INVALID_USER_ID", lang),
            status_code=400,
            data=[]
        )

    user = await user_collection.find_one(
        {"_id": ObjectId(reported_id), "is_deleted": {"$ne": True}},
        {"_id": 1}
    )

    if not user:
        return response.error_message(
            translate_message("USER_NOT_FOUND", lang),
            status_code=404,
            data=[]
        )

    # ---------------- VALIDATE REASON ----------------
    if not reason or not reason.strip():
        return response.error_message(
            translate_message("REPORT_REASON_REQUIRED", lang),
            status_code=400,
            data=[]
        )

    reason = reason.strip()

    if len(reason) < 5:
        return response.error_message(
            translate_message("PLEASE_ENTER_AT_LEAST_5_CHARACTERS", lang),
            status_code=400,
            data=[]
        )

    if not re.search(r"[A-Za-z]", reason):
        return response.error_message(
            translate_message("PLEASE_ENTER_VALID_REPORT_REASON", lang),
            status_code=400,
            data=[]
        )

    existing_report = await reported_users_collection.find_one({
        "reporter_id": reporter_id,
        "reported_id": reported_id
    })

    if existing_report:
        return response.error_message(
            translate_message("USER_ALREADY_REPORTED", lang),
            status_code=400,
            data=[{
                "reported_user_id": reported_id,
                "reason": reason
            }]
        )

    await reported_users_collection.insert_one({
        "reporter_id": reporter_id,
        "reported_id": reported_id,
        "reason": reason,
        "status": "pending",
        "created_at": datetime.utcnow()
    })

    admin_id = await get_admin_id_by_email()
    if not admin_id:
        return response.error_message(
            translate_message("ADMIN_CRED"),
            data=[],
            status_code=404
        )
    await send_notification(
        recipient_id=admin_id,
        recipient_type=NotificationRecipientType.ADMIN,
        notification_type=NotificationType.REPORT,
        title=translate_message("PUSH_TITLE_USER_REPORTED", lang),
        message=translate_message("PUSH_MESSAGE_USER_REPORTED", lang),
        reference={
            "entity": "user_report",
            "entity_id": reported_id,
            "reported_by": reporter_id
        },
        sender_user_id=reporter_id,
        send_push=False
    )

    return response.success_message(
        translate_message("USER_REPORTED_SUCCESSFULLY", lang),
        data=[{
            "reported_user_id": reported_id,
            "reason": reason
        }],
        status_code=200
    )

async def get_blocked_users_list(user_id: str, lang: str):
    try:
        cursor = blocked_users_collection.find(
            {"blocker_id": user_id},
            {"_id": 0, "blocked_id": 1, "created_at": 1}
        )

        blocked_users = []
        async for doc in cursor:
            blocked_users.append({
                "blocked_user_id": doc.get("blocked_id"),
                "blocked_at": doc.get("created_at")
            })

        return response.success_message(
            translate_message("BLOCKED_USERS_FETCHED", lang),
            data=serialize_datetime_fields(blocked_users),
            status_code=200
        )

    except Exception as e:
        return response.raise_exception(
            translate_message("FAILED_TO_FETCH_BLOCKED_USERS", lang),
            data=str(e),
            status_code=500
        )

async def get_reported_users_list(user_id: str, lang: str):
    try:
        cursor = reported_users_collection.find(
            {"reporter_id": user_id},
            {
                "_id": 0,
                "reported_id": 1,
                "reason": 1,
                "status": 1,
                "created_at": 1
            }
        )

        reported_users = []
        async for doc in cursor:
            reported_users.append({
                "reported_user_id": doc.get("reported_id"),
                "reason": doc.get("reason"),
                "status": doc.get("status"),
                "reported_at": doc.get("created_at")
            })

        return response.success_message(
            translate_message("REPORTED_USERS_FETCHED", lang),
            data=serialize_datetime_fields(reported_users),
            status_code=200
        )

    except Exception as e:
        return response.raise_exception(
            translate_message("FAILED_TO_FETCH_REPORTED_USERS", lang),
            data=str(e),
            status_code=500
        )
