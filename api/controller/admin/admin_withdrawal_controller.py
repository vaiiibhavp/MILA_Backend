from typing import Optional

from config.models.admin_withdrawal_request_model import list_withdrawal_requests
from core.utils.helper import serialize_datetime_fields
from core.utils.pagination import StandardResultsSetPagination
from core.utils.response_mixin import CustomResponseMixin
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
