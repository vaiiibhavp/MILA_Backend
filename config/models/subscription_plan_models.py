from typing import Dict, Any
from bson import ObjectId
from services.translation import translate_message
from config.db_config import subscription_plan_collection
from core.utils.response_mixin import CustomResponseMixin

response = CustomResponseMixin()

async def get_subscription_plan(plan_id: str, lang:str) -> Any:
    """
    get subscription plan by id
    """
    plan_data = await subscription_plan_collection.find_one({"_id": ObjectId(plan_id)})
    if not plan_data:
        return response.error_message(
            translate_message("SUBSCRIPTION_PLAN_NOT_FOUND", lang=lang),
            data=[],
            status_code=404,
        )
    return plan_data