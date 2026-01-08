from typing import Optional

from config.db_config import user_token_history_collection
from core.utils.core_enums import TokenTransactionType
from core.utils.pagination import StandardResultsSetPagination
from schemas.user_token_history_schema import TokenHistory
from services.translation import translate_message
from config.db_config import user_token_history_collection
from schemas.user_token_history_schema import CreateTokenHistory

async def get_user_token_history(user_id:str,lang:str, pagination:StandardResultsSetPagination, transaction_type: Optional[TokenTransactionType] = None):
    # Build a base query
    query = {"user_id": user_id}

    # Apply optional type filter
    if transaction_type:
        query["type"] = transaction_type.value

    cursor = (
            user_token_history_collection
            .find(query)
            .sort("created_at", -1)
            .skip(pagination.skip)
            .limit(pagination.limit)
    )
    docs = await cursor.to_list(length=pagination.limit)
    history: list[dict] = []
    for doc in docs:
        history.append({
            "user_id": user_id,
            "delta": doc["delta"],
            "type": doc["type"],
            "reason": translate_message(doc["reason"], lang),
            "balance_before": str(doc["balance_before"]),
            "balance_after": str(doc["balance_after"]),
            "created_at": doc["created_at"],
        })

    return history

async def create_user_token_history(data:CreateTokenHistory):
    await user_token_history_collection.insert_one(data.model_dump())