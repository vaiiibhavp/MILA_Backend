from datetime import datetime, date , time
from bson import ObjectId
from config.db_config import user_collection , video_call_sessions , onboarding_collection , file_collection
from core.utils.response_mixin import CustomResponseMixin
from services.translation import translate_message
from core.utils.core_enums import MembershipType ,TokenTransactionType ,TokenTransactionReason
import math
from config.basic_config import settings
from schemas.user_token_history_schema import CreateTokenHistory 
from config.models.user_token_history_model import create_user_token_history
from core.utils.core_enums import NotificationType, NotificationRecipientType
from services.notification_service import send_notification
from api.controller.files_controller import generate_file_url


FREE_VIDEO_LIMIT_SECONDS = settings.FREE_VIDEO_LIMIT_SECONDS


response = CustomResponseMixin()



async def start_video_call(
    user_id: str,
    receiver_user_id: str,
    conversation_id: str,
    channel_name: str,
    call_request_id: str,
    receiver_accepted: bool = False,
    lang: str = "en"
):
    # ---------------- Fetch caller ----------------
    caller = await user_collection.find_one({"_id": ObjectId(user_id)})
    if not caller:
        return response.error_message(
            translate_message("USER_NOT_FOUND", lang),
            status_code=404
        )

    if not caller.get("is_verified"):
        return response.error_message(
            translate_message("USER_NOT_VERIFIED", lang),
            status_code=400
        )

    if caller.get("login_status") != "active":
        return response.error_message(
            translate_message("USER_BLOCKED_OR_INACTIVE", lang),
            status_code=403
        )

    # Fetch receiver
    receiver = await user_collection.find_one({"_id": ObjectId(receiver_user_id)})
    if not receiver:
        return response.error_message(
            translate_message("RECEIVER_NOT_FOUND", lang),
            status_code=404
        )

    if not receiver.get("is_verified"):
        return response.error_message(
            translate_message("RECEIVER_NOT_VERIFIED", lang),
            status_code=400
        )

    if receiver.get("login_status") != "active":
        return response.error_message(
            translate_message("RECEIVER_BLOCKED_OR_INACTIVE", lang),
            status_code=403
        )

    # ---------------- Find existing ACTIVE call ----------------
    existing_call = await video_call_sessions.find_one({
        "call_request_id": call_request_id,
        "status": {"$in": ["ringing", "ongoing"]}
    })

    # ================= RECEIVER ACCEPTS =================
    if receiver_accepted is True:
        if not existing_call:
            return response.error_message(
                translate_message("CALL_NOT_FOUND", lang),
                status_code=404
            )

        await video_call_sessions.update_one(
            {"_id": existing_call["_id"]},
            {
                "$set": {
                    "receiver_accepted": True,
                    "accepted_at": datetime.utcnow(),
                    "status": "ongoing"
                }
            }
        )

        return response.success_message(
            translate_message("CALL_ACCEPTED", lang),
            data=[{
                "call_id": str(existing_call["_id"]),
                "receiver_accepted": True
            }]
        )

    # ================= CALLER STARTS =================
    if existing_call:
        return response.error_message(
            translate_message("CALL_ALREADY_EXISTS", lang),
            status_code=400
        )

    # ---------------- Token validation ----------------
    caller_tokens = int(caller.get("tokens", 0))
    receiver_tokens = int(receiver.get("tokens", 0))

    if caller_tokens <= 0:
        return response.error_message(
            translate_message("CALLER_INSUFFICIENT_TOKENS", lang),
            status_code=400
        )

    if receiver_tokens <= 0:
        return response.error_message(
            translate_message("RECEIVER_INSUFFICIENT_TOKENS", lang),
            status_code=400
        )

    # Calculate today's free usage (caller side)
    today_start = datetime.combine(date.today(), time.min)
    today_end = datetime.combine(date.today(), time.max)

    # ---------------- Caller TOTAL free usage ----------------
    caller_cursor = video_call_sessions.find({
        "$or": [
            {"caller_id": user_id},
            {"receiver_id": user_id}
        ],
        "status": "ended",
        "start_time": {"$gte": today_start, "$lte": today_end}
    })

    caller_free_used_seconds = 0
    async for call in caller_cursor:
        if call.get("caller_id") == user_id:
            caller_free_used_seconds += call.get("caller_free_seconds_used", 0)
        if call.get("receiver_id") == user_id:
            caller_free_used_seconds += call.get("receiver_free_seconds_used", 0)

    caller_free_seconds_remaining = max(
        0, FREE_VIDEO_LIMIT_SECONDS - caller_free_used_seconds
    )

    # ---------------- Receiver TOTAL free usage ----------------
    receiver_cursor = video_call_sessions.find({
        "$or": [
            {"caller_id": receiver_user_id},
            {"receiver_id": receiver_user_id}
        ],
        "status": "ended",
        "start_time": {"$gte": today_start, "$lte": today_end}
    })

    receiver_free_used_seconds = 0
    async for call in receiver_cursor:
        if call.get("caller_id") == receiver_user_id:
            receiver_free_used_seconds += call.get("caller_free_seconds_used", 0)
        if call.get("receiver_id") == receiver_user_id:
            receiver_free_used_seconds += call.get("receiver_free_seconds_used", 0)

    receiver_free_seconds_remaining = max(
        0, FREE_VIDEO_LIMIT_SECONDS - receiver_free_used_seconds
    )

    # Rates
    caller_rate = 1 if caller.get("membership_type") == MembershipType.PREMIUM.value else 2
    receiver_rate = 1 if receiver.get("membership_type") == MembershipType.PREMIUM.value else 2

    call_doc = {
        "caller_id": user_id,
        "receiver_id": receiver_user_id,
        "conversation_id": conversation_id,
        "channel_name": channel_name,
        "call_request_id": call_request_id,

        "receiver_accepted": False,
        "start_time": datetime.utcnow(),
        "caller_rate_per_minute": caller_rate,
        "receiver_rate_per_minute": receiver_rate,
        "caller_free_seconds_remaining": caller_free_seconds_remaining,
        "receiver_free_seconds_remaining": receiver_free_seconds_remaining,

        "status": "ringing",
        "created_at": datetime.utcnow()
    }

    result = await video_call_sessions.insert_one(call_doc)
    call_id = str(result.inserted_id)

    # ================= NEW PART (FETCH PROFILE IMAGE) =================

    recipient_name = receiver.get("username")
    recipient_verified = receiver.get("is_verified")

    recipient_profile_image = None

    onboarding_doc = await onboarding_collection.find_one({"user_id": receiver_user_id})

    if onboarding_doc and onboarding_doc.get("images"):
        first_image_id = onboarding_doc["images"][0]

        file_doc = await file_collection.find_one({
            "_id": ObjectId(first_image_id),
            "is_deleted": {"$ne": True}
        })

        if file_doc:
            url = await generate_file_url(
                storage_key=file_doc["storage_key"],
                backend=file_doc["storage_backend"]
            )

            recipient_profile_image = {
                "file_id": first_image_id,
                "url": url
            }

    # ---------------- Send notification ----------------
    await send_notification(
        recipient_id=receiver_user_id,
        recipient_type=NotificationRecipientType.USER,
        notification_type=NotificationType.VIDEO_CALL,

        #  NEW: priority
        priority="high",

        title="PUSH_TITLE_VIDEO_CALL",
        message="PUSH_MESSAGE_VIDEO_CALL",
        reference={
            "recipientUserId": receiver_user_id,
            "recipientName": recipient_name,
            "recipientVerified": recipient_verified,
            "recipientProfileImage": recipient_profile_image,

            "currentUserId": user_id,
            "conversationId": conversation_id,
            "channelName": channel_name,
            "callRequestId": call_request_id,
            "isIncomingCall": True,

            "call_id": call_id,
            "caller_free_seconds_remaining": caller_free_seconds_remaining,
            "receiver_free_seconds_remaining": receiver_free_seconds_remaining,
            "caller_rate": caller_rate,
            "receiver_rate": receiver_rate
        },
        sender_user_id=user_id,
        send_push=True,

        #  Push priority for mobile
        push_data={
            "caller_name": caller.get("username"),
            "type": "video_call",
            "priority": "high"
        }
    )

    return response.success_message(
        translate_message("VIDEO_CALL_STARTED", lang),
        data=[{
            "call_id": call_id,
            "conversation_id": conversation_id,
            "channel_name": channel_name,
            "call_request_id": call_request_id,
            "caller_free_seconds_remaining": caller_free_seconds_remaining,
            "receiver_free_seconds_remaining": receiver_free_seconds_remaining,
            "caller_rate": caller_rate,
            "receiver_rate": receiver_rate,
            "caller_tokens": caller_tokens,
            "receiver_tokens": receiver_tokens
        }]
    )

async def end_video_call(user_id: str, call_id: str, total_call_seconds: int, lang: str = "en"):

    call = await video_call_sessions.find_one({"_id": ObjectId(call_id)})
    if not call:
        return response.error_message(
            translate_message("CALL_NOT_FOUND", lang),
            status_code=404
        )

    if call.get("status") == "ended":
        return response.error_message(
            translate_message("CALL_ALREADY_ENDED", lang),
            status_code=400
        )

    # IF RECEIVER NEVER ACCEPTED → END WITHOUT BILLING
    if call.get("receiver_accepted") is not True:
        await video_call_sessions.update_one(
            {"_id": ObjectId(call_id)},
            {
                "$set": {
                    "status": "ended",
                    "end_time": datetime.utcnow(),
                    "total_seconds": int(total_call_seconds),
                    "caller_tokens_deducted": 0,
                    "receiver_tokens_deducted": 0,
                    "caller_free_seconds_used": 0,
                    "receiver_free_seconds_used": 0,
                    "paid_seconds_used": 0,
                    "end_reason": "not_accepted"
                }
            }
        )

        return response.success_message(
            translate_message("VIDEO_CALL_ENDED", lang),
            data=[{
                "call_id": call_id,
                "total_call_seconds": total_call_seconds,
                "caller_tokens_deducted": 0,
                "receiver_tokens_deducted": 0,
                "end_reason": "not_accepted"
            }]
        )

    # ================= NORMAL BILLING FLOW =================

    caller = await user_collection.find_one({"_id": ObjectId(call["caller_id"])})
    receiver = await user_collection.find_one({"_id": ObjectId(call["receiver_id"])})

    if not caller or not receiver:
        return response.error_message(
            translate_message("USER_NOT_FOUND", lang),
            status_code=404
        )

    # FORCE INT CONVERSION (VERY IMPORTANT)
    total_call_seconds = int(total_call_seconds)

    caller_free_remaining = int(call.get("caller_free_seconds_remaining", 0))
    receiver_free_remaining = int(call.get("receiver_free_seconds_remaining", 0))

    caller_rate = int(call.get("caller_rate_per_minute", 2))
    receiver_rate = int(call.get("receiver_rate_per_minute", 2))

    caller_balance_before = int(caller.get("tokens", 0))
    receiver_balance_before = int(receiver.get("tokens", 0))

    # Free usage
    caller_free_used = min(total_call_seconds, caller_free_remaining)
    receiver_free_used = min(total_call_seconds, receiver_free_remaining)

    paid_seconds = max(0, total_call_seconds - min(caller_free_used, receiver_free_used))
    paid_minutes = math.ceil(paid_seconds / 60)

    caller_tokens_to_deduct = paid_minutes * caller_rate
    receiver_tokens_to_deduct = paid_minutes * receiver_rate

    # Never deduct more than balance
    caller_tokens_to_deduct = min(caller_balance_before, caller_tokens_to_deduct)
    receiver_tokens_to_deduct = min(receiver_balance_before, receiver_tokens_to_deduct)

    new_caller_balance = caller_balance_before - caller_tokens_to_deduct
    new_receiver_balance = receiver_balance_before - receiver_tokens_to_deduct

    await user_collection.update_one(
        {"_id": caller["_id"]},
        {"$set": {"tokens": new_caller_balance}}
    )

    await user_collection.update_one(
        {"_id": receiver["_id"]},
        {"$set": {"tokens": new_receiver_balance}}
    )

    # Token history - caller
    await create_user_token_history(CreateTokenHistory(
        user_id=str(caller["_id"]),
        delta=caller_tokens_to_deduct,
        type=TokenTransactionType.DEBIT,
        reason=TokenTransactionReason.VIDEO_CALL,
        balance_before=str(caller_balance_before),
        balance_after=str(new_caller_balance)
    ))

    # Token history - receiver
    await create_user_token_history(CreateTokenHistory(
        user_id=str(receiver["_id"]),
        delta=receiver_tokens_to_deduct,
        type=TokenTransactionType.DEBIT,
        reason=TokenTransactionReason.VIDEO_CALL,
        balance_before=str(receiver_balance_before),
        balance_after=str(new_receiver_balance)
    ))

    new_caller_free_remaining = max(0, caller_free_remaining - caller_free_used)
    new_receiver_free_remaining = max(0, receiver_free_remaining - receiver_free_used)

    await video_call_sessions.update_one(
        {"_id": ObjectId(call_id)},
        {
            "$set": {
                "status": "ended",
                "end_time": datetime.utcnow(),
                "total_seconds": total_call_seconds,
                "caller_free_seconds_used": caller_free_used,
                "receiver_free_seconds_used": receiver_free_used,

                "caller_free_seconds_remaining": new_caller_free_remaining,
                "receiver_free_seconds_remaining": new_receiver_free_remaining,

                "paid_seconds_used": paid_seconds,
                "caller_tokens_deducted": caller_tokens_to_deduct,
                "receiver_tokens_deducted": receiver_tokens_to_deduct
            }
        }
    )

    return response.success_message(
        translate_message("VIDEO_CALL_ENDED", lang),
        data=[{
            "call_id": call_id,
            "total_call_seconds": total_call_seconds,
            "caller_free_seconds_used": caller_free_used,
            "receiver_free_seconds_used": receiver_free_used,
            "paid_seconds_used": paid_seconds,
            "caller_tokens_deducted": caller_tokens_to_deduct,
            "receiver_tokens_deducted": receiver_tokens_to_deduct
        }]
    )

async def video_call_tick(user_id: str, call_id: str, elapsed_seconds: int, lang: str = "en"):

    call = await video_call_sessions.find_one({"_id": ObjectId(call_id)})
    if not call:
        return response.error_message(
            translate_message("CALL_NOT_FOUND", lang),
            status_code=404
        )

    call_status = call.get("status")

    caller = await user_collection.find_one({"_id": ObjectId(call["caller_id"])})
    receiver = await user_collection.find_one({"_id": ObjectId(call["receiver_id"])})

    if not caller or not receiver:
        return response.error_message(
            translate_message("USER_NOT_FOUND", lang),
            status_code=404
        )

    caller_tokens = int(caller.get("tokens", 0))
    receiver_tokens = int(receiver.get("tokens", 0))

    # Block only if already ended
    if call_status == "ended":
        return response.error_message(
            translate_message("CALL_NOT_ACTIVE", lang),
            status_code=400
        )

    # If still ringing → allow tick but NO billing
    if call_status == "ringing":
        return response.success_message(
            translate_message("CALL_CAN_CONTINUE", lang),
            data=[{
                "continue_call": True,
                "billing_started": False,
                "caller_tokens_required": 0,
                "receiver_tokens_required": 0,
                "caller_available_tokens": caller_tokens,
                "receiver_available_tokens": receiver_tokens
            }]
        )

    # If receiver not accepted yet → no billing
    if call.get("receiver_accepted") is not True:
        return response.success_message(
            translate_message("CALL_CAN_CONTINUE", lang),
            data=[{
                "continue_call": True,
                "billing_started": False,
                "caller_tokens_required": 0,
                "receiver_tokens_required": 0,
                "caller_available_tokens": caller_tokens,
                "receiver_available_tokens": receiver_tokens
            }]
        )

    # ================= NORMAL ONGOING BILLING FLOW =================

    caller_free_remaining = int(call.get("caller_free_seconds_remaining", 0))
    receiver_free_remaining = int(call.get("receiver_free_seconds_remaining", 0))

    free_remaining = min(caller_free_remaining, receiver_free_remaining)

    free_used = min(int(elapsed_seconds), free_remaining)
    paid_seconds = max(0, int(elapsed_seconds) - free_used)
    paid_minutes = math.ceil(paid_seconds / 60)

    caller_rate = int(call.get("caller_rate_per_minute", 2))
    receiver_rate = int(call.get("receiver_rate_per_minute", 2))

    caller_required = paid_minutes * caller_rate
    receiver_required = paid_minutes * receiver_rate

    if caller_required > caller_tokens or receiver_required > receiver_tokens:
        await video_call_sessions.update_one(
            {"_id": ObjectId(call_id)},
            {"$set": {"status": "ended", "end_reason": "insufficient_tokens"}}
        )

        return response.success_message(
            translate_message("INSUFFICIENT_TOKENS_CALL_ENDED", lang),
            data=[{"continue_call": False}]
        )

    return response.success_message(
        translate_message("CALL_CAN_CONTINUE", lang),
        data=[{
            "continue_call": True,
            "billing_started": True,
            "caller_tokens_required": caller_required,
            "receiver_tokens_required": receiver_required,
            "caller_available_tokens": caller_tokens,
            "receiver_available_tokens": receiver_tokens
        }]
    )
