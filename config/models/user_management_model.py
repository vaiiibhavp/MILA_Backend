from bson import ObjectId
from datetime import datetime, timedelta
from typing import Optional
from pymongo.errors import PyMongoError
from config.db_config import (
    user_collection,
    onboarding_collection,
    countries_collection,
    file_collection,
    verification_collection,
    user_match_history,
    user_suspension_collection,
    admin_blocked_users_collection,
    deleted_account_collection,
    reported_users_collection
)
from api.controller.files_controller import generate_file_url
from core.utils.core_enums import VerificationStatusEnum
from services.translation import translate_message

class UserManagementModel:

    @staticmethod
    async def get_admin_users_pipeline(
        status: Optional[str],
        search: Optional[str],
        gender: Optional[str],
        country: Optional[str],
        verification: Optional[str],
        membership: Optional[str],
        date_from: Optional[datetime],
        date_to: Optional[datetime],
        pagination
    ):
        try:
            if not pagination:
                raise ValueError("Pagination object is required")

            pipeline = []

            # ---------------- USER MATCH ----------------
            user_match = {"is_deleted": {"$ne": True}}

            if status:
                user_match["login_status"] = status

            if membership:
                user_match["membership_type"] = membership

            if date_from or date_to:
                user_match["created_at"] = {}
                if date_from:
                    user_match["created_at"]["$gte"] = date_from
                if date_to:
                    user_match["created_at"]["$lte"] = date_to

            pipeline.append({"$match": user_match})

            # ---------------- STRING ID ----------------
            pipeline.append({
                "$addFields": {
                    "userIdStr": {"$toString": "$_id"}
                }
            })

            # ---------------- ONBOARDING ----------------
            pipeline.extend([
                {
                    "$lookup": {
                        "from": "user_onboarding",
                        "localField": "userIdStr",
                        "foreignField": "user_id",
                        "as": "onboarding"
                    }
                },
                {"$unwind": "$onboarding"}
            ])

            if search:
                pipeline.append({
                    "$match": {"username": {"$regex": search, "$options": "i"}}
                })

            if gender:
                pipeline.append({"$match": {"onboarding.gender": gender}})

            if country:
                pipeline.append({"$match": {"onboarding.country": country}})

            # ---------------- VERIFICATION ----------------
            pipeline.append({
                "$lookup": {
                    "from": "verification_history",
                    "let": {"uid": "$userIdStr"},
                    "pipeline": [
                        {"$match": {"$expr": {"$eq": ["$user_id", "$$uid"]}}},
                        {"$sort": {"verified_at": -1}},
                        {"$limit": 1}
                    ],
                    "as": "verification"
                }
            })

            pipeline.append({
                "$addFields": {
                    "verification_status": {
                        "$cond": {
                            "if": {"$gt": [{"$size": "$verification"}, 0]},
                            "then": {"$arrayElemAt": ["$verification.status", 0]},
                            "else": VerificationStatusEnum.PENDING
                        }
                    }
                }
            })

            if verification:
                pipeline.append({"$match": {"verification_status": verification}})

            # ---------------- MATCHES ----------------
            pipeline.append({
                "$lookup": {
                    "from": "users_matched_history",
                    "let": {"uid": "$userIdStr"},
                    "pipeline": [
                        {"$match": {"$expr": {"$in": ["$$uid", "$user_ids"]}}}
                    ],
                    "as": "matches"
                }
            })

            pipeline.append({
                "$addFields": {
                    "match_count": {"$size": "$matches"}
                }
            })

            # ---------------- COUNTRY ----------------
            pipeline.append({
                "$addFields": {
                    "countryObjId": {
                        "$toObjectId": "$onboarding.country"
                    }
                }
            })

            pipeline.append({
                "$lookup": {
                    "from": "countries",
                    "localField": "countryObjId",
                    "foreignField": "_id",
                    "as": "country"
                }
            })

            pipeline.append({
                "$unwind": {
                    "path": "$country",
                    "preserveNullAndEmptyArrays": True
                }
            })

            # ---------------- PAGINATION ----------------
            pipeline.extend([
                {"$sort": {"created_at": -1}},
                {"$skip": max(pagination.skip, 0)},
                {"$limit": max(pagination.limit, 1)}
            ])

            # ---------------- FINAL PROJECTION ----------------
            pipeline.append({
                "$project": {
                    "_id": 0,
                    "user_id": {"$toString": "$_id"},
                    "username": 1,
                    "email": 1,
                    "account_status": "$login_status",
                    "subscription": "$membership_type",
                    "verification_status": 1,
                    "gender": "$onboarding.gender",
                    "sexual_orientation": "$onboarding.sexual_orientation",
                    "relationship_status": "$onboarding.marital_status",
                    "country": {
                        "id": {"$toString": "$country._id"},
                        "name": "$country.name"
                    },
                    "match_count": 1,
                    "registration_date": "$created_at"
                }
            })

            return await user_collection.aggregate(pipeline).to_list(None)

        except ValueError as ve:
            # logger.warning(f"Validation error: {ve}")
            raise ve

        except PyMongoError as db_error:
            # logger.error(f"Database error: {db_error}")
            raise RuntimeError("Database operation failed")

        except Exception as e:
            # logger.exception("Unexpected error while fetching admin users")
            raise RuntimeError(str(e))

    # ------------------ USER DETAILS ------------------
    @staticmethod
    async def get_user(user_id: str):
        return await user_collection.find_one(
            {"_id": ObjectId(user_id), "is_deleted": {"$ne": True}},
            {"password": 0}
        )

    @staticmethod
    async def get_onboarding(user_id: str):
        return await onboarding_collection.find_one(
            {"user_id": user_id}, {"_id": 0}
        )

    @staticmethod
    async def get_country(country_id: str):
        country = await countries_collection.find_one(
            {"_id": ObjectId(country_id)}, {"name": 1}
        )
        if not country:
            return None
        return {"id": str(country["_id"]), "name": country["name"]}

    # ---------------- VERIFICATION ----------------
    @staticmethod
    async def get_latest_verification_status(user_id: str):
        data = await verification_collection.find(
            {"user_id": user_id}
        ).sort("verified_at", -1).limit(1).to_list(1)

        return data[0]["status"] if data else VerificationStatusEnum.PENDING

    # ---------------- MATCHES ----------------
    async def get_matches(user_id: str):
        cursor = user_match_history.find({"user_ids": user_id})
        matched_ids = set()

        # 1️ Collect matched user IDs
        async for doc in cursor:
            for uid in doc.get("user_ids", []):
                if uid != user_id:
                    matched_ids.add(uid)

        if not matched_ids:
            return 0, []

        # 2️ Fetch existing users only
        users_cursor = user_collection.find(
            {
                "_id": {
                    "$in": [ObjectId(uid) for uid in matched_ids if ObjectId.is_valid(uid)]
                },
                "is_deleted": {"$ne": True}
            },
            {"username": 1}
        )

        users = []
        async for u in users_cursor:
            users.append({
                "user_id": str(u["_id"]),
                "username": u.get("username")
            })
        return len(matched_ids), users

    # ---------------- PHOTOS ----------------
    @staticmethod
    async def get_user_photos(image_ids: list):
        if not image_ids:
            return [], None

        files = await file_collection.find(
            {"_id": {"$in": [ObjectId(i) for i in image_ids]}}
        ).to_list(None)

        photos = []
        for f in files:
            url = await generate_file_url(
                f["storage_key"], f.get("storage_backend")
            )
            photos.append({
                "id": str(f["_id"]),
                "url": url
            })

        profile_photo = photos[0] if photos else None
        return photos, profile_photo


    # ------------------ SUSPEND ------------------
    @staticmethod
    async def suspend_user(
        user_id: str,
        admin_id: str,
        days: int,
        lang: str = "en"
    ):
        user = await user_collection.find_one(
            {"_id": ObjectId(user_id), "is_deleted": {"$ne": True}}
        )

        if not user:
            return {
                "error": True,
                "message": translate_message("USER_NOT_FOUND", lang),
                "status_code": 404
            }

        # ---------------- DELETED ACCOUNT CHECK ----------------
        deleted_account = await deleted_account_collection.find_one({
            "user_id": user_id
        })

        if deleted_account:
            return {
                "error": True,
                "message": translate_message("USER_ACCOUNT_DELETED", lang),
                "status_code": 400
            }

        # ---------------- ADMIN BLOCK CHECK ----------------
        admin_blocked = await admin_blocked_users_collection.find_one({
            "user_id": user_id,
            "unblocked_at": {"$exists": False}
        })

        if admin_blocked:
            return {
                "error": True,
                "message": translate_message("USER_ALREADY_BLOCKED", lang),
                "status_code": 400
            }

        # ---------------- ACTIVE SUSPENSION CHECK ----------------
        already_suspended = await user_suspension_collection.find_one({
            "user_id": user_id,
            "suspended_until": {"$gt": datetime.utcnow()}
        })

        if already_suspended:
            return {
                "error": True,
                "message": translate_message("USER_ALREADY_SUSPENDED", lang),
                "status_code": 400
            }

        suspended_from = datetime.utcnow()
        suspended_until = suspended_from + timedelta(days=days)

        await user_suspension_collection.insert_one({
            "user_id": user_id,
            "suspended_by": admin_id,
            "suspended_from": suspended_from,
            "suspended_until": suspended_until,
            "created_at": suspended_from,
            "updated_at": suspended_from
        })

        # ---------------- UPDATE REPORT STATUS ----------------
        await reported_users_collection.update_many(
            {
                "reported_id": user_id
            },
            {
                "$set": {
                    "status": VerificationStatusEnum.SUSPENDED.value,
                    "updated_at": datetime.utcnow()
                }
            }
        )

        return {
            "error": False,
            "data": {
                "user_id": user_id,
                "suspended_until": suspended_until
            }
        }

    # ------------------ BLOCK ------------------
    @staticmethod
    async def block_user(
        user_id: str,
        admin_id: str,
        lang: str = "en"
    ):
        # ---------------- CHECK USER EXISTS ----------------
        user = await user_collection.find_one(
            {"_id": ObjectId(user_id), "is_deleted": {"$ne": True}}
        )

        if not user:
            return {
                "error": True,
                "message": translate_message("USER_NOT_FOUND", lang),
                "status_code": 404
            }

        # ---------------- CHECK DELETED ACCOUNT ----------------
        deleted_account = await deleted_account_collection.find_one({
            "user_id": user_id
        })

        if deleted_account:
            return {
                "error": True,
                "message": translate_message("USER_ACCOUNT_DELETED", lang),
                "status_code": 400
            }

        # ---------------- CHECK ALREADY BLOCKED ----------------
        already_blocked = await admin_blocked_users_collection.find_one({
            "user_id": user_id,
            "unblocked_at": {"$exists": False}
        })

        if already_blocked:
            return {
                "error": True,
                "message": translate_message("USER_ALREADY_BLOCKED", lang),
                "status_code": 400
            }

        # ---------------- CHECK ACTIVE SUSPENSION ----------------
        active_suspension = await user_suspension_collection.find_one({
            "user_id": user_id,
            "suspended_until": {"$gt": datetime.utcnow()}
        })

        if active_suspension:
            return {
                "error": True,
                "message": translate_message("USER_ALREADY_SUSPENDED", lang),
                "status_code": 400
            }

        # ---------------- BLOCK USER ----------------
        now = datetime.utcnow()

        await admin_blocked_users_collection.insert_one({
            "user_id": user_id,
            "blocked_by": admin_id,
            "created_at": now,
            "updated_at": now
        })

        # ---------------- UPDATE REPORT STATUS ----------------
        await reported_users_collection.update_many(
            {
                "reported_id": user_id
            },
            {
                "$set": {
                    "status": VerificationStatusEnum.BLOCKED.value,
                    "updated_at": datetime.utcnow()
                }
            }
        )

        return {
            "error": False,
            "data": {
                "user_id": user_id,
                "blocked_by": admin_id
            }
        }

    # ------------------ DELETE ------------------
    @staticmethod
    async def delete_user(
        user_id: str,
        admin_id: str,
        lang: str = "en"
    ):
    # ---------------- CHECK USER EXISTS ----------------
        user = await user_collection.find_one(
            {"_id": ObjectId(user_id), "is_deleted": {"$ne": True}}
        )

        if not user:
            return {
            "error": True,
            "message": translate_message("USER_NOT_FOUND", lang),
            "status_code": 404
        }

    # ---------------- CHECK ALREADY DELETED ----------------
        already_deleted = await deleted_account_collection.find_one(
            {"user_id": user_id}
        )

        if already_deleted:
            return {
            "error": True,
            "message": translate_message("ACCOUNT_ALREADY_DELETED", lang),
            "status_code": 400
        }

        now = datetime.utcnow()

    # ---------------- STORE DELETE AUDIT ----------------
        await deleted_account_collection.insert_one({
        "user_id": user_id,
        "email": user.get("email"),
        "deleted_by": admin_id,
        "created_at": now,
        "updated_at": now
        })

    # ---------------- UPDATE REPORT STATUS ----------------
        await reported_users_collection.update_many(
            {
                "reported_id": user_id
            },
            {
                "$set": {
                    "status": VerificationStatusEnum.DELETED.value,
                    "updated_at": datetime.utcnow()
                }
            }
        )

        return {
        "error": False,
        "data": {
            "user_id": user_id,
            "deleted_by": admin_id
        }
    }
