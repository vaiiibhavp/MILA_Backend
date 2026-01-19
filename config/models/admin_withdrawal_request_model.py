from bson import ObjectId
from datetime import datetime, timezone

from config.db_config import withdraw_token_transaction_collection


async def list_withdrawal_requests(search: str, pagination):
    """
        Fetch withdrawal requests with global search and user details.
        """

    pipeline = []

    # 🔹 Join user collection
    pipeline.append({
        "$lookup": {
            "from": "users",
            "localField": "user_id",
            "foreignField": "_id",
            "as": "user"
        }
    })

    pipeline.append({
        "$unwind": {
            "path": "$user",
            "preserveNullAndEmptyArrays": True
        }
    })

    # 🔹 Global search
    if search:
        search = search.strip()
        or_conditions = [
            {"user.username": {"$regex": search, "$options": "i"}},
            {"user.email": {"$regex": search, "$options": "i"}},
            {"wallet_address": {"$regex": search, "$options": "i"}},
            {"status": {"$regex": search, "$options": "i"}}
        ]

        # ObjectId search support
        if ObjectId.is_valid(search):
            or_conditions.append({"_id": ObjectId(search)})

        pipeline.append({
            "$match": {
                "$or": or_conditions
            }
        })

    # 🔹 Sort + pagination
    pipeline.extend([
        {"$sort": {"created_at": -1}},
        {"$skip": pagination.skip},
        {"$limit": pagination.limit}
    ])

    cursor = withdraw_token_transaction_collection.aggregate(pipeline)
    docs = await cursor.to_list(length=pagination.limit)

    return [
        {
            "_id": str(doc["_id"]),
            "user_id": str(doc["user_id"]),
            "user_name": doc.get("user", {}).get("username"),
            "user_email": doc.get("user", {}).get("email"),
            "request_amount": doc["request_amount"],
            "paid_amount": doc["paid_amount"],
            "remaining_amount": doc["remaining_amount"],
            "status": doc["status"],
            "wallet_address": doc["wallet_address"],
            "platform_fee": doc["platform_fee"],
            "tron_fee": doc["tron_fee"],
            "tokens": doc["tokens"],
            "requested_at": doc["created_at"],
            "updated_at": doc["updated_at"]
        }
        for doc in docs
    ]
