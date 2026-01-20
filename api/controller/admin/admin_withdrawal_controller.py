from typing import Optional

from bson import ObjectId

from config import user_collection
from config.models.admin_withdrawal_request_model import list_withdrawal_requests, reject_withdrawal_request
from core.utils.core_enums import NotificationRecipientType, NotificationType
from core.utils.exceptions import CustomValidationError
from core.utils.helper import serialize_datetime_fields
from core.utils.pagination import StandardResultsSetPagination
from core.utils.response_mixin import CustomResponseMixin
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

        user = await user_collection.find_one(
            {"_id": ObjectId(result.user_id)}
        )
        recipient_lang = user.get("lang", "en")
        await send_notification(
            recipient_id=str(user["_id"]),
            recipient_type=NotificationRecipientType.USER,
            notification_type=NotificationType.TOKEN_WITHDRAW_STATUS,
            title=translate_message(message="PUSH_TITLE_WITHDRAWAL_REQUEST_REJECTED", lang=recipient_lang),
            message=translate_message(message="PUSH_MESSAGE_WITHDRAWAL_REQUEST_REJECTED", lang=recipient_lang),
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

