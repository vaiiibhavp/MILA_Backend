from bson import ObjectId

from core.utils.pagination import StandardResultsSetPagination
from config.models.user_token_history_model import get_user_token_history
from config.models.token_packages_plan_model import get_token_packages_plans
from schemas.user_token_history_schema import TokenHistoryResponse
from services.translation import translate_message
from core.utils.helper import serialize_datetime_fields, convert_objectid_to_str
from config.models.user_models import get_user_details
from core.utils.response_mixin import CustomResponseMixin
response = CustomResponseMixin()


async def get_user_token_details(
        user_id:str,
        lang:str,
        pagination:StandardResultsSetPagination
):
    try:
        token_history = await get_user_token_history(user_id=user_id,lang=lang,pagination=pagination)
        available_tokens = await get_user_details(condition={"_id":ObjectId(user_id)}, fields=["tokens"])
        token_plans = await get_token_packages_plans()
        token_plans = convert_objectid_to_str(token_plans)
        data = TokenHistoryResponse(
            history=token_history,
            available_tokens=available_tokens['tokens'],
            token_plans=token_plans
        ).model_dump()
        data = serialize_datetime_fields(data)
        return response.success_message(
            translate_message("SUBSCRIPTION_PLAN_FETCHED", lang=lang),
            data=[data]
        )
    except Exception as e:
        return response.raise_exception(
            translate_message("ERROR_WHILE_FETCHING_TOKEN_DETAILS", lang=lang),
            data=str(e),
            status_code=500
        )