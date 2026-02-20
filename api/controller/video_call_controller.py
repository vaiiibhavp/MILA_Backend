from datetime import datetime, date , time
from bson import ObjectId
from config.db_config import user_collection , video_call_sessions
from core.utils.response_mixin import CustomResponseMixin
from services.translation import translate_message
from core.utils.core_enums import MembershipType ,TokenTransactionType ,TokenTransactionReason
import math
from config.basic_config import settings
from schemas.user_token_history_schema import CreateTokenHistory 
from config.models.user_token_history_model import create_user_token_history

FREE_VIDEO_LIMIT_SECONDS = settings.FREE_VIDEO_LIMIT_SECONDS


response = CustomResponseMixin()



async def start_video_call(user_id: str, receiver_user_id: str, lang: str = "en"):

    # Fetch caller
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

    # Token validation for both users
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

    cursor = video_call_sessions.find({
        "caller_id": user_id,
        "status": "ended",
        "start_time": {"$gte": today_start, "$lte": today_end}
    })

    total_free_used_seconds = 0
    async for call in cursor:
        total_free_used_seconds += call.get("free_seconds_used", 0)

    remaining_free_seconds = max(0, FREE_VIDEO_LIMIT_SECONDS - total_free_used_seconds)

    # Rates
    caller_rate = 1 if caller.get("membership_type") == MembershipType.PREMIUM.value else 2
    receiver_rate = 1 if receiver.get("membership_type") == MembershipType.PREMIUM.value else 2

    call_doc = {
        "caller_id": user_id,
        "receiver_id": receiver_user_id,
        "start_time": datetime.utcnow(),
        "caller_rate_per_minute": caller_rate,
        "receiver_rate_per_minute": receiver_rate,
        "free_seconds_remaining": remaining_free_seconds,
        "status": "ongoing",
        "created_at": datetime.utcnow()
    }

    result = await video_call_sessions.insert_one(call_doc)

    return response.success_message(
        translate_message("VIDEO_CALL_STARTED", lang),
        data=[{
            "call_id": str(result.inserted_id),
            "free_seconds_remaining": remaining_free_seconds,
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

    caller = await user_collection.find_one({"_id": ObjectId(call["caller_id"])})
    receiver = await user_collection.find_one({"_id": ObjectId(call["receiver_id"])})

    if not caller or not receiver:
        return response.error_message(
            translate_message("USER_NOT_FOUND", lang), 
            status_code=404
        )

    free_seconds_remaining = call.get("free_seconds_remaining", 0)

    free_used = min(total_call_seconds, free_seconds_remaining)
    paid_seconds = max(0, total_call_seconds - free_used)

    paid_minutes = math.ceil(paid_seconds / 60)

    caller_rate = call.get("caller_rate_per_minute", 2)
    receiver_rate = call.get("receiver_rate_per_minute", 2)

    caller_tokens_to_deduct = paid_minutes * caller_rate
    receiver_tokens_to_deduct = paid_minutes * receiver_rate

    caller_balance_before = caller.get("tokens", 0)
    receiver_balance_before = receiver.get("tokens", 0)

    caller_tokens_to_deduct = min(caller_balance_before, caller_tokens_to_deduct)
    receiver_tokens_to_deduct = min(receiver_balance_before, receiver_tokens_to_deduct)

    # Deduct tokens
    await user_collection.update_one(
        {"_id": ObjectId(caller["_id"])},
        {"$inc": {"tokens": -caller_tokens_to_deduct}}
    )

    await user_collection.update_one(
        {"_id": ObjectId(receiver["_id"])},
        {"$inc": {"tokens": -receiver_tokens_to_deduct}}
    )

    # Token history - caller
    await create_user_token_history(CreateTokenHistory(
        user_id=str(caller["_id"]),
        delta=caller_tokens_to_deduct,
        type=TokenTransactionType.DEBIT,
        reason=TokenTransactionReason.VIDEO_CALL,
        balance_before=str(caller_balance_before),
        balance_after=str(caller_balance_before - caller_tokens_to_deduct)
    ))

    # Token history - receiver
    await create_user_token_history(CreateTokenHistory(
        user_id=str(receiver["_id"]),
        delta=receiver_tokens_to_deduct,
        type=TokenTransactionType.DEBIT,
        reason=TokenTransactionReason.VIDEO_CALL,
        balance_before=str(receiver_balance_before),
        balance_after=str(receiver_balance_before - receiver_tokens_to_deduct)
    ))

    await video_call_sessions.update_one(
        {"_id": ObjectId(call_id)},
        {
            "$set": {
                "status": "ended",
                "end_time": datetime.utcnow(),
                "total_seconds": total_call_seconds,
                "free_seconds_used": free_used,
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
            "paid_minutes": paid_minutes,
            "caller_tokens_deducted": caller_tokens_to_deduct,
            "receiver_tokens_deducted": receiver_tokens_to_deduct
        }]
    )

async def video_call_tick(user_id: str, call_id: str, elapsed_seconds: int, lang: str = "en"):

    call = await video_call_sessions.find_one({"_id": ObjectId(call_id)})
    if not call or call.get("status") != "ongoing":
        return response.error_message(
            translate_message("CALL_NOT_ACTIVE", lang), 
            status_code=400
        )

    caller = await user_collection.find_one({"_id": ObjectId(call["caller_id"])})
    receiver = await user_collection.find_one({"_id": ObjectId(call["receiver_id"])})

    if not caller or not receiver:
        return response.error_message(
            translate_message("USER_NOT_FOUND", lang), 
            status_code=404
        )

    free_seconds_remaining = call.get("free_seconds_remaining", 0)

    free_used = min(elapsed_seconds, free_seconds_remaining)
    paid_seconds = max(0, elapsed_seconds - free_used)
    paid_minutes = math.ceil(paid_seconds / 60)

    caller_rate = call.get("caller_rate_per_minute", 2)
    receiver_rate = call.get("receiver_rate_per_minute", 2)

    caller_required = paid_minutes * caller_rate
    receiver_required = paid_minutes * receiver_rate

    if caller_required > caller.get("tokens", 0) or receiver_required > receiver.get("tokens", 0):
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
            "caller_tokens_required": caller_required,
            "receiver_tokens_required": receiver_required,
            "caller_available_tokens": caller.get("tokens", 0),
            "receiver_available_tokens": receiver.get("tokens", 0)
        }]
    )
