from pymongo.errors import PyMongoError
from bson import ObjectId
from datetime import datetime
from config.db_config import (
    user_collection,
    admin_blocked_users_collection,
    transaction_collection,
    onboarding_collection,
    contest_collection,
    withdraw_token_transaction_collection,
    deleted_account_collection
)
from core.utils.filer_date import get_date_filter


class DashboardModel:

    @staticmethod
    async def get_dashboard_stats(filter_type: str):
        try:
            start_date, end_date = get_date_filter(filter_type)
            date_range = {"$gte": start_date, "$lte": end_date}
            now = datetime.utcnow()

            # ---------------- EXCLUDE DELETED USERS ----------------
            deleted_users = await deleted_account_collection.distinct("user_id")

            deleted_users = [ObjectId(uid) for uid in deleted_users]

            # ---------------- USERS ----------------
            total_users = await user_collection.count_documents({
                "created_at": date_range,
                "_id": {"$nin": deleted_users}
            })

            verified_users = await user_collection.count_documents({
                "is_verified": True,
                "updated_at": date_range,
                "_id": {"$nin": deleted_users}
            })

            active_users = await user_collection.count_documents({
                "login_status": "active",
                "last_login_at": date_range,
                "_id": {"$nin": deleted_users}
            })

            new_users = await user_collection.count_documents({
                "created_at": date_range,
                "_id": {"$nin": deleted_users}
            })

            # ---------------- ACTIVE SUBSCRIPTIONS----------------
            active_subscription_pipeline = [
                {
                    "$match": {
                        "trans_type": "subscription_transaction",
                        "status": {"$in": ["success", "partial payment"]},
                        "expires_at": {"$gt": now}
                    }
                },
                {
                    "$group": {
                        "_id": "$user_id"
                    }
                },
                {
                    "$count": "active_count"
                }
            ]

            active_sub_result = await transaction_collection.aggregate(
                active_subscription_pipeline
            ).to_list(1)

            active_subscriptions = (
                active_sub_result[0]["active_count"]
                if active_sub_result else 0
            )

            # ---------------- BLOCKED USERS ----------------
            blocked_users = await admin_blocked_users_collection.count_documents({
                "created_at": date_range
            })

            # ---------------- TOTAL REVENUE ----------------
            revenue_pipeline = [
                {
                    "$match": {
                        "status": {"$in": ["success", "partial payment"]},
                        "updated_at": date_range
                    }
                },
                {
                    "$group": {
                        "_id": None,
                        "total": {"$sum": "$paid_amount"}
                    }
                }
            ]

            revenue_result = await transaction_collection.aggregate(
                revenue_pipeline
            ).to_list(1)

            total_revenue = round(revenue_result[0]["total"], 2) if revenue_result else 0

            # ---------------- TOTAL WITHDRAWAL AMOUNT (SUCCESS ONLY) ----------------
            withdraw_pipeline = [
                {
                    "$match": {
                        "status": "completed",   # only success
                        "updated_at": date_range
                    }
                },
                {
                    "$group": {
                        "_id": None,
                        "total_withdraw": {"$sum": "$paid_amount"}
                    }
                }
            ]

            withdraw_result = await withdraw_token_transaction_collection.aggregate(
                withdraw_pipeline
            ).to_list(1)

            total_withdraw_amount = (
                round(withdraw_result[0]["total_withdraw"], 2)
                if withdraw_result else 0
            )

            # Deduct withdrawal from revenue
            total_revenue = round(total_revenue - total_withdraw_amount, 2)

            # ---------------- MONTHLY REVENUE SUMMARY ----------------
            monthly_revenue_pipeline = [
                {
                    "$match": {
                        "status": {"$in": ["success", "partial payment"]},
                        "trans_type": "subscription_transaction",
                        "start_date": date_range
                    }
                },
                {
                    "$group": {
                        "_id": {
                            "year": {"$year": "$start_date"},
                            "month": {"$month": "$start_date"}
                        },
                        "revenue": {"$sum": "$paid_amount"}
                    }
                },
                {
                    "$sort": {
                        "_id.year": 1,
                        "_id.month": 1
                    }
                }
            ]

            monthly_data = await transaction_collection.aggregate(
                monthly_revenue_pipeline
            ).to_list(None)

            month_map = {
                1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr",
                5: "May", 6: "Jun", 7: "Jul", 8: "Aug",
                9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"
            }

            revenue_summary = [
                {
                    "month": month_map[item["_id"]["month"]],
                    "revenue": round(item["revenue"], 2)
                }
                for item in monthly_data
            ]

            # ---------------- TOTAL WITHDRAWALS APPROVED ----------------
            total_withdrawals_approved = await withdraw_token_transaction_collection.count_documents({
                "status": "completed",
                "updated_at": date_range
            })

            # ---------------- CONTEST COUNT ----------------
            total_contests = await contest_collection.count_documents({
                "created_at": date_range
            })

            # ---------------- GENDER DISTRIBUTION ----------------
            gender_pipeline = [
                {"$match": {"created_at": date_range}},
                {
                    "$group": {
                        "_id": "$gender",
                        "count": {"$sum": 1}
                    }
                }
            ]

            gender_data = await onboarding_collection.aggregate(
                gender_pipeline
            ).to_list(None)

            gender_counts = {"male": 0, "female": 0, "other": 0}

            for g in gender_data:
                if g["_id"] in gender_counts:
                    gender_counts[g["_id"]] = g["count"]
                else:
                    gender_counts["other"] += g["count"]

            total_gender = sum(gender_counts.values())

            def pct(c):
                return round((c / total_gender) * 100, 2) if total_gender else 0

            gender_distribution = {
                "total": total_gender,
                "male": {"count": gender_counts["male"], "percentage": pct(gender_counts["male"])},
                "female": {"count": gender_counts["female"], "percentage": pct(gender_counts["female"])},
                "other": {"count": gender_counts["other"], "percentage": pct(gender_counts["other"])}
            }

            return {
                "users": {
                    "total_registered": total_users,
                    "verified": verified_users,
                    "active": active_users,
                    "new_users": new_users,
                    "blocked": blocked_users
                },
                "subscriptions": {
                    "active": active_subscriptions
                },
                "revenue": {
                    "total": total_revenue
                },
                "revenue_summary": revenue_summary,
                "withdrawals": {
                    "approved": total_withdrawals_approved
                },
                "contests": {
                    "total_hosted": total_contests
                },
                "gender_distribution": gender_distribution
            }

        except PyMongoError:
            raise RuntimeError("Database operation failed")

        except Exception as e:
            raise RuntimeError(str(e))
