from typing import Optional

from config.db_config import user_token_history_collection
from core.utils.core_enums import TokenTransactionType, TokenTransactionReason
from core.utils.pagination import StandardResultsSetPagination
from schemas.user_token_history_schema import TokenHistory
from services.translation import translate_message
from config.db_config import user_token_history_collection
from schemas.user_token_history_schema import CreateTokenHistory

async def get_user_token_history(user_id:str,lang:str, pagination:StandardResultsSetPagination, transaction_type: Optional[TokenTransactionType] = None):

    match_stage = {"user_id": user_id}
    if transaction_type:
        match_stage["type"] = transaction_type.value

    pipeline = [
        {"$match": match_stage},

        # 🔹 Convert txn_id (string) → ObjectId
        {
            "$addFields": {
                "txn_object_id": {
                    "$cond": [
                        {
                            "$and": [
                                {"$ne": ["$txn_id", None]},
                                {"$eq": [{"$type": "$txn_id"}, "string"]}
                            ]
                        },
                        {"$toObjectId": "$txn_id"},
                        None
                    ]
                }
            }
        },

        # 🔹 Lookup withdrawal transactions
        {
            "$lookup": {
                "from": "withdraw_token_transaction",
                "localField": "txn_object_id",
                "foreignField": "_id",
                "as": "withdraw_txn"
            }
        },

        # 🔹 Lookup normal transactions
        {
            "$lookup": {
                "from": "transaction",
                "localField": "txn_object_id",
                "foreignField": "_id",
                "as": "normal_txn"
            }
        },

        # 🔹 Lookup gift transactions
        {
            "$lookup": {
                "from": "gift_transaction",
                "localField": "txn_object_id",
                "foreignField": "_id",
                "as": "gift_txn"
            }
        },

        # 🔹 Convert sender_id / receiver_id (STRING → ObjectId)
        {
            "$addFields": {
                "gift_sender_object_id": {
                    "$cond": [
                        {
                            "$and": [
                                {"$ne": [{"$arrayElemAt": ["$gift_txn.sender_id", 0]}, None]},
                                {"$eq": [{"$type": {"$arrayElemAt": ["$gift_txn.sender_id", 0]}}, "string"]}
                            ]
                        },
                        {"$toObjectId": {"$arrayElemAt": ["$gift_txn.sender_id", 0]}},
                        None
                    ]
                },
                "gift_receiver_object_id": {
                    "$cond": [
                        {
                            "$and": [
                                {"$ne": [{"$arrayElemAt": ["$gift_txn.receiver_id", 0]}, None]},
                                {"$eq": [{"$type": {"$arrayElemAt": ["$gift_txn.receiver_id", 0]}}, "string"]}
                            ]
                        },
                        {"$toObjectId": {"$arrayElemAt": ["$gift_txn.receiver_id", 0]}},
                        None
                    ]
                }
            }
        },

        # 🔹 Decide which user ID to show
        {
            "$addFields": {
                "gift_user_object_id": {
                    "$cond": [
                        {"$eq": ["$reason", TokenTransactionReason.GIFT_SENT.value]},
                        "$gift_receiver_object_id",
                        {
                            "$cond": [
                                {"$eq": ["$reason", TokenTransactionReason.GIFT_RECEIVED.value]},
                                "$gift_sender_object_id",
                                None
                            ]
                        }
                    ]
                }
            }
        },

        # 🔹 Lookup username
        {
            "$lookup": {
                "from": "users",
                "localField": "gift_user_object_id",
                "foreignField": "_id",
                "as": "gift_user"
            }
        },
        {
            "$unwind": {
                "path": "$gift_user",
                "preserveNullAndEmptyArrays": True
            }
        },

        # 🔹 Resolve status dynamically
        {
            "$addFields": {
                "status": {
                    "$cond": [
                        # 1️⃣ txn_id is null
                        {"$eq": ["$txn_object_id", None]},
                        None,

                        # 2️⃣ Gift transactions
                        {
                            "$cond": [
                                {
                                    "$in": [
                                        "$reason",
                                        [
                                            TokenTransactionReason.GIFT_SENT.value,
                                            TokenTransactionReason.GIFT_RECEIVED.value
                                        ]
                                    ]
                                },
                                {"$arrayElemAt": ["$gift_txn.status", 0]},

                                # 3️⃣ Withdraw vs normal
                                {
                                    "$cond": [
                                        {"$eq": ["$type", TokenTransactionType.WITHDRAW.value]},
                                        {"$arrayElemAt": ["$withdraw_txn.status", 0]},
                                        {"$arrayElemAt": ["$normal_txn.status", 0]}
                                    ]
                                }
                            ]
                        }
                    ]
                }
            }
        },

        {"$sort": {"created_at": -1}},
        {"$skip": pagination.skip},
        {"$limit": pagination.limit}
    ]

    cursor = user_token_history_collection.aggregate(pipeline)
    docs = await cursor.to_list(length=pagination.limit)
    history: list[dict] = []
    for doc in docs:
        history.append({
            "txn_id": doc["txn_id"],
            "user_id": user_id,
            "delta": doc["delta"],
            "type": doc["type"],
            "gift_username": (
                doc.get("gift_user", {}).get("username")
                if doc.get("gift_user") else None
            ),
            "status": doc.get("status"),
            "reason": translate_message(doc["reason"], lang),
            "balance_before": str(doc["balance_before"]),
            "balance_after": str(doc["balance_after"]),
            "created_at": doc["created_at"],
        })

    return history

async def create_user_token_history(data:CreateTokenHistory):
    await user_token_history_collection.insert_one(data.model_dump())