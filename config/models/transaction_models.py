from bson import ObjectId
from typing import Optional, Dict, Any
from schemas.transcation_schema import TransactionCreateModel
from config.db_config import transaction_collection
from core.utils.helper import convert_objectid_to_str

async def store_transaction_details(doc:TransactionCreateModel):
    doc = doc.model_dump()
    doc["user_id"] = ObjectId(doc["user_id"])
    doc["plan_id"] = ObjectId(doc["plan_id"])
    result = await transaction_collection.insert_one(doc)
    doc["_id"] = convert_objectid_to_str(result.inserted_id)
    return doc


async def get_existing_transaction(txn_id: str) -> Optional[Dict[str, Any]]:
    """
    validate transaction id is existed in payment details
    """
    return await transaction_collection.find_one(
        {"payment_details.txn_id": txn_id},
        {"payment_details.$": 1}  # return
    )


