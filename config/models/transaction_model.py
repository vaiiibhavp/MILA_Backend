from datetime import datetime
import copy
from bson import ObjectId
from typing import Optional
from config.db_config import withdraw_token_transaction_collection ,transaction_collection,system_config_collection
from core.utils.helper import serialize_datetime_fields
from core.utils.core_enums import TransactionType , TransactionTab

class TransactionModel:

    @staticmethod
    async def fetch_all_transactions(
        tab: TransactionTab,
        search,
        status,
        date_from,
        date_to,
        pagination
    ):
        pipeline = []

        # --------------------------------------------------
        # COLLECTION SELECTION
        # --------------------------------------------------
        if tab == TransactionTab.TOKEN_WITHDRAWAL:
            collection = withdraw_token_transaction_collection
        else:
            collection = transaction_collection

        # --------------------------------------------------
        # MATCH
        # --------------------------------------------------
        match_stage = {}

        if tab == TransactionTab.SUBSCRIPTION:
            match_stage["trans_type"] = TransactionType.SUBSCRIPTION_TRANSACTION.value

        elif tab == TransactionTab.TOKEN_PURCHASE:
            match_stage["trans_type"] = TransactionType.TOKEN_TRANSACTION.value

        if status:
            match_stage["status"] = {"$regex": f"^{status}$", "$options": "i"}

        if date_from or date_to:
            match_stage["updated_at"] = {}
            if date_from:
                match_stage["updated_at"]["$gte"] = date_from
            if date_to:
                match_stage["updated_at"]["$lte"] = date_to

        pipeline.append({"$match": match_stage})

        # --------------------------------------------------
        # USER LOOKUP
        # --------------------------------------------------
        pipeline.extend([
            {
                "$lookup": {
                    "from": "users",
                    "localField": "user_id",
                    "foreignField": "_id",
                    "as": "user"
                }
            },
            {"$unwind": "$user"}
        ])

        # --------------------------------------------------
        # SEARCH
        # --------------------------------------------------
        if search:
            pipeline.append({
                "$match": {
                    "user.username": {"$regex": search, "$options": "i"}
                }
            })

        # --------------------------------------------------
        # TOKEN PACKAGE LOOKUP (ONLY FOR TOKEN PURCHASE)
        # --------------------------------------------------
        if tab == TransactionTab.TOKEN_PURCHASE:
            pipeline.extend([
                {
                    "$lookup": {
                        "from": "token_packages_plan",
                        "localField": "plan_id",
                        "foreignField": "_id",
                        "as": "package"
                    }
                },
                {
                    "$unwind": {
                        "path": "$package",
                        "preserveNullAndEmptyArrays": True
                    }
                }
            ])

        # ==================================================
        # COUNT PIPELINE (BEFORE PAGINATION)
        # ==================================================
        count_pipeline = copy.deepcopy(pipeline)
        count_pipeline.append({"$count": "total"})

        count_result = await collection.aggregate(count_pipeline).to_list(1)
        total = count_result[0]["total"] if count_result else 0

        # --------------------------------------------------
        # SORT
        # --------------------------------------------------
        pipeline.append({"$sort": {"updated_at": -1}})

        # --------------------------------------------------
        # PAGINATION
        # --------------------------------------------------
        if pagination and pagination.limit:
            pipeline.extend([
                {"$skip": pagination.skip},
                {"$limit": pagination.limit}
            ])

        # --------------------------------------------------
        # PROJECTION
        # --------------------------------------------------
        if tab == TransactionTab.TOKEN_WITHDRAWAL:
            pipeline.append({
                "$project": {
                    "_id": 0,
                    "transaction_id": "$payment_details.tron_txn_id",
                    "username": "$user.username",
                    "email": "$user.email",
                    "requested_token_amount": "$tokens",
                    "usdt_equivalent": "$request_amount",
                    "processed_amount": "$paid_amount",
                    "status": "$status",
                    "processing_date": "$updated_at"
                }
            })

        elif tab == TransactionTab.SUBSCRIPTION:
            pipeline.append({
                "$project": {
                    "_id": 0,

                    # ---------------- TRANSACTION ID ----------------
                    "transaction_id": {
                        "$cond": [
                            {"$isArray": "$payment_details"},
                            {
                                "$arrayElemAt": [
                                    {
                                        "$map": {
                                            "input": "$payment_details",
                                            "as": "p",
                                            "in": "$$p.tron_txn_id"
                                        }
                                    },
                                    -1
                                ]
                            },
                            "$payment_details.tron_txn_id"
                        ]
                    },

                    # ---------------- USER ----------------
                    "username": "$user.username",

                    # ---------------- AMOUNTS ----------------
                    "payment_amount": "$plan_amount",
                    "paid_amount": "$paid_amount",

                    # ---------------- SUBSCRIPTION DATE ----------------
                    "subscription_date": {
                        "$cond": [
                            {"$isArray": "$payment_details"},
                            {
                                "$arrayElemAt": [
                                    {
                                        "$map": {
                                            "input": "$payment_details",
                                            "as": "p",
                                            "in": "$$p.created_at"
                                        }
                                    },
                                    -1
                                ]
                            },
                            "$payment_details.created_at"
                        ]
                    },

                    # ---------------- STATUS ----------------
                    "status": "$status",

                    # ---------------- PLAN DATES ----------------
                    "start_date": "$start_date",
                    "end_date": "$expires_at"
                }
            })

        else:  # TOKEN PURCHASE
            pipeline.append({
                "$project": {
                    "_id": 0,
                    "transaction_id": "$payment_details.tron_txn_id",
                    "package_name": "$package.title",
                    "username": "$user.username",
                    "email": "$user.email",
                    "plan_amount": "$plan_amount",
                    "paid_amount": "$paid_amount",
                    # "tokens": "$tokens",
                    "status": "$status",
                    "date": "$updated_at"
                }
            })

        # --------------------------------------------------
        # EXECUTE
        # --------------------------------------------------
        data = await collection.aggregate(pipeline).to_list(None)

        return {
            "data": serialize_datetime_fields(data),
            "total": total
        }

    @staticmethod
    async def get_subscription_bonus_token():
        config = await system_config_collection.find_one({}, {"_id": 0})

        if not config:
            return {"on_subscribe_token": 0}

        return {
            "on_subscribe_token": int(config.get("on_subscribe_token", 0))
        }

    @staticmethod
    async def update_subscription_bonus_token(tokens: int):
        await system_config_collection.update_one(
            {},
            {"$set": {"on_subscribe_token": str(tokens)}},
            upsert=True
        )

        return {
            "on_subscribe_token": tokens
        }