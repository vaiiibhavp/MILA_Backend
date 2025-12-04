from fastapi import Request
from services.translation import translate_message
from core.utils.response_mixin import CustomResponseMixin
from core.utils.helper import serialize_datetime_fields, convert_objectid_to_str
from config.db_config import subscription_plan_collection
response = CustomResponseMixin()


async def get_subscription_list(request: Request, lang: str = "en"):
    """
    Get all active subscription plan list.
    """
    try:
        cursor = subscription_plan_collection.find({f"status": "active"})
        subscription_docs = await cursor.to_list(length=None)  # <- correct: await on to_list, not on cursor
        subscription_docs = serialize_datetime_fields(subscription_docs)
        subscription_list = convert_objectid_to_str(subscription_docs)
        return response.success_message(
            translate_message("SUBSCRIPTION_PLAN_FETCHED", lang=lang),
            data=subscription_list
        )
    except Exception as e:
        return response.raise_exception(
            translate_message("ERROR_FETCHING_SUBSCRIPTION_PLAN", lang=lang),
            data=str(e),
            status_code=500
        )