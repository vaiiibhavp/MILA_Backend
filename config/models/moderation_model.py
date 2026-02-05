from typing import Optional
import copy
from pymongo.errors import PyMongoError
from bson import ObjectId
from config.db_config import (
    reported_users_collection,
    file_collection
)
from api.controller.files_controller import generate_file_url
from core.utils.core_enums import VerificationStatusEnum
from services.translation import translate_message
from core.utils.pagination import StandardResultsSetPagination



class ModerationModel:

    @staticmethod
    async def get_reported_users_pipeline(
        status: Optional[str],
        search: Optional[str],
        pagination: StandardResultsSetPagination
    ):
        try:
            if not pagination:
                raise ValueError("Pagination object is required")

            pipeline = []

            # ---------------- REPORT STATUS FILTER ----------------
            report_match = {}

            if status and status.lower() != "all":
                report_match["status"] = status.lower()

            if report_match:
                pipeline.append({"$match": report_match})

            # ---------------- STRING IDS ----------------
            pipeline.append({
                "$addFields": {
                    "reporterObjId": {
                        "$convert": {
                            "input": "$reporter_id",
                            "to": "objectId",
                            "onError": None,
                            "onNull": None
                        }
                    },
                    "reportedObjId": {
                        "$convert": {
                            "input": "$reported_id",
                            "to": "objectId",
                            "onError": None,
                            "onNull": None
                        }
                    }
                }
            })

            # ---------------- REPORTER LOOKUP ----------------
            pipeline.extend([
                {
                    "$lookup": {
                        "from": "users",
                        "localField": "reporterObjId",
                        "foreignField": "_id",
                        "as": "reporter"
                    }
                },
                {
                    "$unwind": {
                        "path": "$reporter",
                        "preserveNullAndEmptyArrays": True
                    }
                }
            ])

            # ---------------- REPORTED USER LOOKUP ----------------
            pipeline.extend([
                {
                    "$lookup": {
                        "from": "users",
                        "localField": "reportedObjId",
                        "foreignField": "_id",
                        "as": "reported_user"
                    }
                },
                {
                    "$unwind": {
                        "path": "$reported_user",
                        "preserveNullAndEmptyArrays": True
                    }
                }
            ])

            # ---------------- SEARCH ----------------
            if search:
                pipeline.append({
                    "$match": {
                        "$or": [
                            {"reporter.username": {"$regex": search, "$options": "i"}},
                            {"reporter.email": {"$regex": search, "$options": "i"}},
                            {"reported_user.username": {"$regex": search, "$options": "i"}},
                            {"reported_user.email": {"$regex": search, "$options": "i"}},
                        ]
                    }
                })

            # =====================================================
            #  COUNT PIPELINE (BEFORE PAGINATION)
            # =====================================================
            count_pipeline = copy.deepcopy(pipeline)
            count_pipeline.append({"$count": "total"})

            count_result = await reported_users_collection.aggregate(
                count_pipeline
            ).to_list(1)

            total_records = count_result[0]["total"] if count_result else 0

            # ---------------- SORT ----------------
            pipeline.append({"$sort": {"created_at": -1}})

            # ---------------- PAGINATION ----------------
            skip = pagination.skip if isinstance(pagination.skip, int) and pagination.skip >= 0 else 0
            limit = pagination.page_size if isinstance(pagination.page_size, int) and pagination.page_size > 0 else 10

            pipeline.extend([
                {"$skip": skip},
                {"$limit": limit}
            ])

            # ---------------- FINAL PROJECTION ----------------
            pipeline.append({
                "$project": {
                    "_id": 0,
                    "report_id": {"$toString": "$_id"},
                    "status": 1,
                    "reported_at": "$created_at",
                    "reporter": {
                        "user_id": {"$toString": "$reporter._id"},
                        "username": "$reporter.username",
                        "email": "$reporter.email"
                    },
                    "reported_user": {
                        "user_id": {"$toString": "$reported_user._id"},
                        "username": "$reported_user.username",
                        "email": "$reported_user.email"
                    }
                }
            })

            reports = await reported_users_collection.aggregate(pipeline).to_list(None)

            return reports, total_records

        except ValueError:
            raise

        except PyMongoError:
            raise RuntimeError("Database operation failed")

        except Exception as e:
            raise RuntimeError(str(e))

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

    @staticmethod
    async def get_report_details_pipeline(report_id: str):
        try:
            if not ObjectId.is_valid(report_id):
                raise ValueError("Invalid report id")

            pipeline = []

            # ---------------- MATCH REPORT ----------------
            pipeline.append({"$match": {"_id": ObjectId(report_id)}})

            # ---------------- OBJECT IDS ----------------
            pipeline.append({
                "$addFields": {
                    "reporterObjId": {"$toObjectId": "$reporter_id"},
                    "reportedObjId": {"$toObjectId": "$reported_id"}
                }
            })

            # ---------------- REPORTER USER ----------------
            pipeline.append({
                "$lookup": {
                    "from": "users",
                    "localField": "reporterObjId",
                    "foreignField": "_id",
                    "as": "reporter"
                }
            })
            pipeline.append({
                "$unwind": {
                    "path": "$reporter",
                    "preserveNullAndEmptyArrays": True
                }
            })

            # ---------------- REPORTED USER ----------------
            pipeline.append({
                "$lookup": {
                    "from": "users",
                    "localField": "reportedObjId",
                    "foreignField": "_id",
                    "as": "reported_user"
                }
            })
            pipeline.append({
                "$unwind": {
                    "path": "$reported_user",
                    "preserveNullAndEmptyArrays": True
                }
            })

            # ---------------- REPORTER ONBOARDING ----------------
            pipeline.append({
                "$lookup": {
                    "from": "user_onboarding",
                    "localField": "reporter_id",
                    "foreignField": "user_id",
                    "as": "reporter_onboarding"
                }
            })
            pipeline.append({
                "$unwind": {
                    "path": "$reporter_onboarding",
                    "preserveNullAndEmptyArrays": True
                }
            })

            # ---------------- REPORTED ONBOARDING ----------------
            pipeline.append({
                "$lookup": {
                    "from": "user_onboarding",
                    "localField": "reported_id",
                    "foreignField": "user_id",
                    "as": "reported_onboarding"
                }
            })
            pipeline.append({
                "$unwind": {
                    "path": "$reported_onboarding",
                    "preserveNullAndEmptyArrays": True
                }
            })

            # ---------------- FINAL PROJECTION (IDS ONLY) ----------------
            pipeline.append({
                "$project": {
                    "_id": 0,
                    "report_id": {"$toString": "$_id"},
                    "status": 1,
                    "reason": 1,
                    "reported_at": "$created_at",

                    "reporter": {
                        "user_id": {"$toString": "$reporter._id"},
                        "username": "$reporter.username",
                        "email": "$reporter.email",
                        "image_id": {
                            "$arrayElemAt": [
                                {"$ifNull": ["$reporter_onboarding.images", []]},
                                0
                            ]
                        }
                    },

                    "reported_user": {
                        "user_id": {"$toString": "$reported_user._id"},
                        "username": "$reported_user.username",
                        "email": "$reported_user.email",
                        "image_id": {
                            "$arrayElemAt": [
                                {"$ifNull": ["$reported_onboarding.images", []]},
                                0
                            ]
                        }
                    }
                }
            })

            result = await reported_users_collection.aggregate(pipeline).to_list(1)
            return result[0] if result else None

        except ValueError:
            raise
        except PyMongoError:
            raise RuntimeError("Database operation failed")
        except Exception as e:
            raise RuntimeError(str(e))
        
