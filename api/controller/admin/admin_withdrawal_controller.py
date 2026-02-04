from typing import Optional

from bson import ObjectId

from config.db_config import user_collection
from config.models.admin_withdrawal_request_model import list_withdrawal_requests, reject_withdrawal_request, \
    complete_withdrawal_request
from core.utils.core_enums import NotificationRecipientType, NotificationType, TokenTransactionType, \
    TokenTransactionReason
from core.utils.exceptions import CustomValidationError
from core.utils.helper import serialize_datetime_fields
from core.utils.pagination import StandardResultsSetPagination
from core.utils.response_mixin import CustomResponseMixin
from core.utils.transaction_helper import update_user_tokens_and_history
from schemas.withdrawal_request_schema import AdminWithdrawalCompleteRequestModel
from services.notification_service import send_notification
from services.translation import translate_message

response = CustomResponseMixin()


async def fetch_withdrawal_requests(
    user_id:str,
    lang:str,
    search: Optional[str],
    pagination:StandardResultsSetPagination,
):
    try:
        data = await list_withdrawal_requests(search=search, pagination=pagination)
        data = serialize_datetime_fields(data)
        result = {
            "result": data,
            "page": pagination.page,
            "page_size": pagination.page_size
        }
        return response.success_message(
            translate_message(message="WITHDRAWAL_REQUESTS_FETCHED", lang=lang),
            data=[result]
        )
    except Exception as e:
        return response.raise_exception(
            translate_message(message="WITHDRAWAL_REQUESTS_FETCH_FAILED", lang=lang),
            data=str(e),
            status_code=500
        )

async def reject_withdrawal_request_controller(
    request_id: str,
    user_id: str,
    lang: str
):
    try:
        result = await reject_withdrawal_request(
            request_id=request_id,
            admin_user_id=user_id,
            lang=lang
        )

        user = await user_collection.find_one({"_id": ObjectId(result.get("user_id"))})

        await update_user_tokens_and_history(
            user_id=str(user["_id"]),
            user_details=user,
            tokens=int(result['tokens']),
            transaction_type=TokenTransactionType.CREDIT,
            reason=TokenTransactionReason.TOKEN_WITHDRAWAL_REJECTED,
            transaction_id=ObjectId(request_id),
            lang=lang
        )

        recipient_lang = user.get("lang", "en")
        await send_notification(
            recipient_id=str(user["_id"]),
            recipient_type=NotificationRecipientType.USER,
            notification_type=NotificationType.TOKEN_WITHDRAW_STATUS,
            title="PUSH_TITLE_WITHDRAWAL_REQUEST_REJECTED",
            message="PUSH_MESSAGE_WITHDRAWAL_REQUEST_REJECTED",
            reference={
                "entity": "token_withdrawal_request",
                "entity_id": request_id
            },
            sender_user_id=str(user["_id"]),
            send_push=True
        )

        return response.success_message(
            translate_message(
                message="WITHDRAWAL_REQUEST_REJECTED_SUCCESSFULLY",
                lang=lang
            ),
            data=result
        )

    except CustomValidationError as error:
        return response.error_message(
            message=error.message,
            data=error.data,
            status_code=error.status_code
        )
    except Exception as e:
        return response.raise_exception(
            translate_message(message="WITHDRAWAL_REQUEST_REJECT_FAILED", lang=lang),
            data=str(e),
            status_code=500
        )

async def complete_withdrawal_request_controller(
    request_id: str,
    payload: AdminWithdrawalCompleteRequestModel,
    user_id: str,
    lang: str
):
    try:

        result = await complete_withdrawal_request(
            request_id=request_id,
            payload=payload,
            admin_user_id=user_id,
            lang=lang
        )

        user = await user_collection.find_one({"_id": ObjectId(result.get("user_id"))})
        if not user:
            return response.error_message(translate_message("USER_NOT_FOUND", lang=lang), data=[], status_code=404)

        recipient_lang = user.get("lang", "en")
        await send_notification(
            recipient_id=str(user["_id"]),
            recipient_type=NotificationRecipientType.USER,
            notification_type=NotificationType.TOKEN_WITHDRAW_STATUS,
            title="PUSH_TITLE_WITHDRAWAL_COMPLETED",
            message="PUSH_MESSAGE_WITHDRAWAL_COMPLETED",
            reference={
                "entity": "token_withdrawal_request",
                "entity_id": request_id
            },
            sender_user_id=str(user["_id"]),
            send_push=True
        )

        return response.success_message(
            translate_message(
                message="WITHDRAWAL_REQUEST_APPROVED_SUCCESSFULLY",
                lang=lang
            ),
            data=result
        )
    except CustomValidationError as error:
        return response.error_message(
            message=error.message,
            data=error.data,
            status_code=error.status_code
        )
    except Exception as e:
        return response.raise_exception(
            translate_message(message="WITHDRAWAL_REQUEST_APPROVE_FAILED", lang=lang),
            data=str(e),
            status_code=500
        )


