from bson import ObjectId
from typing import Optional, Dict, Any, List

from pymongo import ReturnDocument

from core.utils.core_enums import TransactionStatus, TransactionType
from core.utils.pagination import StandardResultsSetPagination
from schemas.transcation_schema import TransactionCreateModel, TransactionUpdateModel, TokenWithdrawTransactionCreateModel
from config.db_config import transaction_collection, withdraw_token_transaction_collection
from core.utils.helper import convert_objectid_to_str, convert_datetime_to_date, serialize_datetime_fields
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


async def get_existing_transaction(tron_txn_id: str, lang:str) -> Optional[Dict[str, Any]]:
    """
    validate transaction id is existed in payment details
    """
    transaction =  await transaction_collection.find_one(
        {"payment_details.tron_txn_id": tron_txn_id},
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

async def ensure_no_pending_token_withdrawal(user_id: str, lang:str) -> Optional[Dict[str, Any]]:
    """
    Ensure user does not already have a pending token withdrawal request.
    """
    transaction =  await withdraw_token_transaction_collection.find_one(
        {
            "user_id": ObjectId(user_id),
            "status": TransactionStatus.PENDING
        }
    )
    if transaction is not None:
        raise response.raise_exception(
            translate_message(
                message="TOKEN_WITHDRAWAL_ALREADY_PENDING",
                lang=lang
            ),
            data=[],
            status_code=400
        )
    return None

async def store_withdrawn_token_request(doc:TokenWithdrawTransactionCreateModel):
    doc = doc.model_dump()
    doc["user_id"] = ObjectId(doc["user_id"])
    result = await withdraw_token_transaction_collection.insert_one(doc)
    doc["_id"] = convert_objectid_to_str(result.inserted_id)
    return doc

async def get_withdraw_token_transactions(user_id: str, pagination:StandardResultsSetPagination) -> List[Dict[str, Any]]:
    """
        Get all token withdrawal transactions for a user,
        sorted by latest created_at.
    """
    cursor = ((withdraw_token_transaction_collection
               .find({"user_id": ObjectId(user_id)})).sort("created_at", -1).skip(pagination.skip).limit(pagination.limit))
    docs = await cursor.to_list(length=pagination.limit)
    transactions: list[dict] = []
    for doc in docs:
        transactions.append({
            "id": convert_objectid_to_str(doc["_id"]),
            "user_id": user_id,
            "amount": doc["request_amount"],
            "status": doc["status"],
            "wallet_address": doc["wallet_address"],
            "platform_fee": str(doc["platform_fee"]),
            "tron_fee": str(doc["tron_fee"]),
            "paid_amount": str(doc["paid_amount"]),
            "tokens": doc["tokens"],
            "created_at": convert_datetime_to_date(doc["created_at"], '%d-%m-%Y'),
        })

    return transactions

async def get_subscription_transactions(user_id: str, pagination:StandardResultsSetPagination) -> List[Dict[str, Any]]:
    """
        Get all subscription transactions for a user,
        sorted by latest created_at.
    """
    pipeline = [
        {
            "$match": {
                "user_id": ObjectId(user_id),
                "trans_type": TransactionType.SUBSCRIPTION_TRANSACTION.value
            }
        },
        {
            "$lookup": {
                "from": "subscription_plan",  # collection name
                "localField": "plan_id",
                "foreignField": "_id",
                "as": "plan_details"
            }
        },
        {
            "$unwind": {
                "path": "$plan_details",
                "preserveNullAndEmptyArrays": True
            }
        },
        {"$sort": {"updated_at": -1}},
        {"$skip": pagination.skip},
        {"$limit": pagination.limit}
    ]
    cursor = transaction_collection.aggregate(pipeline)
    docs = await cursor.to_list(length=pagination.limit)
    transactions: list[dict] = []
    for doc in docs:
        doc = serialize_datetime_fields(doc)
        transactions.append({
            "id": convert_objectid_to_str(doc["_id"]),
            "user_id": user_id,
            "plan_id": convert_objectid_to_str(doc["plan_id"]),
            "plan_title": (
                doc["plan_details"]["title"]
                if doc.get("plan_details") else None
            ),
            "amount": doc["plan_amount"],
            "paid_amount": doc["paid_amount"],
            "remaining_amount": doc["remaining_amount"],
            "status": doc["status"],
            "tokens": doc["tokens"],
            "created_at": doc["updated_at"],
        })

    return transactions