import os
from decimal import Decimal

from bson import ObjectId
from datetime import datetime, timezone

from config.db_config import withdraw_token_transaction_collection
from core.utils.core_enums import WithdrawalStatus
from core.utils.helper import serialize_datetime_fields
from core.utils.pagination import build_paginated_response
from core.utils.response_mixin import CustomResponseMixin
from core.utils.transaction_helper import get_transaction_details
from schemas.transcation_schema import PaymentDetailsModel
from schemas.withdrawal_request_schema import AdminWithdrawalCompleteRequestModel
from services.translation import translate_message

response = CustomResponseMixin()

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

    # 2️⃣ Join USER_ONBOARDING  (profile image id stored here)
    pipeline.append({
        "$lookup": {
            "from": "user_onboarding",
            "let": {"userId": {"$toString": "$user._id"}},
            "pipeline": [
                {
                    "$match": {
                        "$expr": {"$eq": ["$user_id", "$$userId"]}
                    }
                },
                {
                    "$project": {
                        "profile_image_id": {
                            "$arrayElemAt": ["$images", 0]
                        }
                    }
                }
            ],
            "as": "onboarding"
        }
    })

    pipeline.append({
        "$unwind": {
            "path": "$onboarding",
            "preserveNullAndEmptyArrays": True
        }
    })

    # 3️⃣ Convert image string → ObjectId
    pipeline.append({
        "$addFields": {
            "profile_image_object_id": {
                "$cond": [
                    {"$ne": ["$onboarding.profile_image_id", None]},
                    {"$toObjectId": "$onboarding.profile_image_id"},
                    None
                ]
            }
        }
    })

    # 4️⃣ Join FILES (NOW IT WILL MATCH)
    pipeline.append({
        "$lookup": {
            "from": "files",
            "localField": "profile_image_object_id",
            "foreignField": "_id",
            "as": "profile_image"
        }
    })

    pipeline.append({
        "$unwind": {
            "path": "$profile_image",
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
    pipeline.append({
        "$facet": {
            "data": [
                {"$sort": {"created_at": -1}},
                {"$skip": pagination.skip},
                {"$limit": pagination.limit}
            ],
            "total": [
                {"$count": "count"}
            ]
        }
    })

    cursor = withdraw_token_transaction_collection.aggregate(pipeline)
    docs = await cursor.to_list(length=pagination.limit)
    data = docs[0].get("data", [])
    total = docs[0].get("total", [])
    total_records = total[0]["count"] if total else 0
    base_url = os.getenv("BASE_URL")
    items = [
        {
            "_id": str(doc["_id"]),
            "user_id": str(doc["user_id"]),
            "user_name": doc.get("user", {}).get("username"),
            "user_email": doc.get("user", {}).get("email"),
            "profile_image": (
                f"{base_url}/{doc['profile_image']['storage_key']}"
                if doc.get("profile_image")
                   and doc["profile_image"].get("storage_key")
                else None
            ),
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
        for doc in data
    ]
    items = serialize_datetime_fields(items)
    return build_paginated_response(
        records=items,
        page=pagination.page,
        page_size=pagination.page_size,
        total_records=total_records
    )

async def reject_withdrawal_request(
    request_id: str,
    admin_user_id: str,
    lang: str
):
    """
    Reject a pending withdrawal request.
    """

    withdrawal = await withdraw_token_transaction_collection.find_one(
        {"_id": ObjectId(request_id)}
    )

    if not withdrawal:
        raise response.raise_exception(
            translate_message(message="WITHDRAWAL_REQUEST_NOT_FOUND", lang=lang),
            status_code=404
        )

    if withdrawal["status"] != WithdrawalStatus.pending.value:
        raise response.raise_exception(
            translate_message(
                message="WITHDRAWAL_REQUEST_CANNOT_BE_REJECTED",
                lang=lang
            ),
            status_code=409
        )

    update_doc = {
        "status": WithdrawalStatus.rejected.value,
        "updated_at": datetime.now(timezone.utc),
        "updated_by": ObjectId(admin_user_id),
    }

    await withdraw_token_transaction_collection.update_one(
        {"_id": ObjectId(request_id)},
        {"$set": update_doc}
    )

    return {
        "id": request_id,
        "user_id": str(withdrawal["user_id"]),
        "status": WithdrawalStatus.rejected.value,
        "tokens": withdrawal["tokens"]
    }

async def complete_withdrawal_request(
    request_id: str,
    payload: AdminWithdrawalCompleteRequestModel,
    admin_user_id: str,
    lang: str
):
    """
    Mark an approved withdrawal request as completed.
    """

    withdrawal = await withdraw_token_transaction_collection.find_one(
        {"_id": ObjectId(request_id)}
    )

    if not withdrawal:
        raise response.raise_exception(
            translate_message(message="WITHDRAWAL_REQUEST_NOT_FOUND", lang=lang),
            status_code=404
        )

    if withdrawal["status"] != WithdrawalStatus.pending.value:
        raise response.raise_exception(
            translate_message(
                message="WITHDRAWAL_REQUEST_NOT_ELIGIBLE_FOR_COMPLETION",
                lang=lang
            ),
            status_code=409
        )

    """
        validate transaction id is existed in payment details
    """
    transaction = await withdraw_token_transaction_collection.find_one(
        {"payment_details.tron_txn_id": payload.tron_txn_id},
        {"payment_details.$": 1}  # return
    )
    if transaction is not None:
        raise response.raise_exception(translate_message("WITHDRAWAL_TRANSACTION_ID_ALREADY_USED",
                                                         lang=lang), data=[], status_code=400)

    trans_details = await get_transaction_details(txn_id=payload.tron_txn_id,lang=lang)

    if trans_details["to"] != withdrawal['wallet_address']:
        raise response.raise_exception(
            translate_message(
                message="INVALID_DESTINATION_WALLET",
                lang=lang
            ),
            status_code=400
        )


    payment_details = PaymentDetailsModel(**trans_details).model_dump()

    request_amount = Decimal(str(withdrawal["request_amount"]))
    paid_amount = payload.paid_amount

    total_amount = paid_amount + Decimal(str(withdrawal["platform_fee"])) + payload.tron_fee

    if total_amount != request_amount:
        raise response.raise_exception(
            translate_message(
                message="WITHDRAWAL_PAID_AMOUNT_MISMATCH",
                lang=lang
            ),
            status_code=400
        )

    update_doc = {
        "status": WithdrawalStatus.completed.value,
        "paid_amount": float(paid_amount),
        "remaining_amount": 0,
        "tron_fee": float(payload.tron_fee),
        "payment_details": payment_details,
        "updated_at": datetime.now(timezone.utc),
        "updated_by": ObjectId(admin_user_id)
    }

    await withdraw_token_transaction_collection.update_one(
        {"_id": ObjectId(request_id)},
        {"$set": update_doc}
    )

    return {
        "id": request_id,
        "user_id": str(withdrawal["user_id"]),
        "status": WithdrawalStatus.completed.value,
        "paid_amount": float(paid_amount),
        "tron_txn_id": payload.tron_txn_id,
        "tokens": withdrawal["tokens"],
    }
