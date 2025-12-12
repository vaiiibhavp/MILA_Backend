from bson import ObjectId
from typing import Optional, Dict, Any

from pymongo import ReturnDocument

from schemas.transcation_schema import TransactionCreateModel, TransactionUpdateModel
from config.db_config import transaction_collection
from core.utils.helper import convert_objectid_to_str
from services.translation import translate_message
from core.utils.response_mixin import CustomResponseMixin
from datetime import datetime,timezone
response = CustomResponseMixin()

async def store_transaction_details(doc:TransactionCreateModel):
    doc = doc.model_dump()
    doc["user_id"] = ObjectId(doc["user_id"])
    doc["plan_id"] = ObjectId(doc["plan_id"])
    result = await transaction_collection.insert_one(doc)
    doc["_id"] = convert_objectid_to_str(result.inserted_id)
    return doc


async def get_existing_transaction(txn_id: str, lang:str) -> Optional[Dict[str, Any]]:
    """
    validate transaction id is existed in payment details
    """
    transaction =  await transaction_collection.find_one(
        {"payment_details.txn_id": txn_id},
        {"payment_details.$": 1}  # return
    )
    if transaction is not None:
        raise response.raise_exception(translate_message("ALREADY_SUBSCRIBED_USING_THIS_TRANSACTION_ID",
                                                         lang=lang), data=[], status_code=400)
    return None

async def get_subscription_payment_details(payment_id: str, lang:str) -> Dict[str, Any]:
    payment_details = await transaction_collection.find_one(
        {"_id": ObjectId(payment_id)}
    )
    if payment_details is None:
        raise response.raise_exception(translate_message("TRANSACTION_PAYMENT_DETAILS_NOT_FOUND", lang=lang),
                                       data=[], status_code=404)
    return payment_details

async def update_transaction_details(doc:TransactionUpdateModel, subscription_id:str):
    doc = doc.model_dump()
    payment_details = doc.pop("payment_details", None)
    res = await transaction_collection.find_one_and_update(
        {"_id": ObjectId(subscription_id)},
        {
            "$push": {"payment_details": payment_details},
            "$set": doc
        },
        return_document=ReturnDocument.AFTER
    )
    return res