from datetime import datetime
from bson import ObjectId
from config.db_config import db
from schemas.verification_schema import VerificationStatusEnum
from core.utils.pagination import StandardResultsSetPagination
from api.controller.files_controller import generate_file_url
from core.utils.response_mixin import CustomResponseMixin
from config.db_config import verification_collection , user_collection
from services.translation import translate_message

response = CustomResponseMixin()

async def get_verification_queue(
    status: str,
    lang: str = "en",
    search: str | None = None,
    pagination: StandardResultsSetPagination = None
):
    try:
        pipeline = [
            {
                "$match": {
                    "onboarding_completed": True,
                    "images": {"$exists": True, "$ne": []},
                    "selfie_image": {"$exists": True, "$ne": None}
                }
            },
            {
                "$addFields": {
                    "userObjectId": {
                        "$cond": [
                            {"$eq": [{"$type": "$user_id"}, "objectId"]},
                            "$user_id",
                            {"$toObjectId": "$user_id"}
                        ]
                    }
                }
            },
            {
                "$lookup": {
                    "from": "users",
                    "localField": "userObjectId",
                    "foreignField": "_id",
                    "as": "user"
                }
            },
            {"$unwind": "$user"},
        ]

        if search:
            pipeline.append({
                "$match": {
                    "user.username": {"$regex": search, "$options": "i"}
                }
            })

        pipeline.extend([
            {
                "$lookup": {
                    "from": "verification_history",
                    "let": {"uid": "$user_id"},
                    "pipeline": [
                        {
                            "$match": {
                                "$expr": {"$eq": ["$user_id", "$$uid"]}
                            }
                        },
                        {"$sort": {"verified_at": -1}},
                        {"$limit": 1}
                    ],
                    "as": "verification"
                }
            },
            {
                "$addFields": {
                    "latest_verification_status": {
                        "$cond": [
                            {"$gt": [{"$size": "$verification"}, 0]},
                            {"$arrayElemAt": ["$verification.status", 0]},
                            None
                        ]
                    }
                }
            },
        ])

        # ---------------- STATUS FILTER LOGIC ----------------

        if status == VerificationStatusEnum.APPROVED.value:
            pipeline.append({
                "$match": {
                    "latest_verification_status": VerificationStatusEnum.APPROVED.value
                }
            })
        else:
            pipeline.append({
                "$match": {
                    "latest_verification_status": {
                        "$in": [
                            None,
                            VerificationStatusEnum.PENDING.value
                        ]
                    }
                }
            })

        # ---------------- FIXED PAGINATION (CRASH PROOF) ----------------

        pipeline.append({"$sort": {"created_at": -1}})

        if pagination and pagination.skip is not None and pagination.skip >= 0:
            pipeline.append({"$skip": int(pagination.skip)})

        if pagination and pagination.limit is not None and pagination.limit > 0:
            pipeline.append({"$limit": int(pagination.limit)})

        # ---------------- FINAL PROJECTION ----------------

        pipeline.append({
            "$project": {
                "_id": 0,
                "user_id": {"$toString": "$user._id"},
                "username": "$user.username",

                "submitted_photos": "$images",
                "live_selfie": "$selfie_image",

                "verification_status": {
                    "$ifNull": [
                        "$latest_verification_status",
                        VerificationStatusEnum.PENDING.value
                    ]
                },
                "Registration_Date": "$created_at"
            }
        })

        results = await db.user_onboarding.aggregate(pipeline).to_list(None)

        # Collect file IDs
        file_ids = set()
        for item in results:
            file_ids.update(item.get("submitted_photos", []))
            if isinstance(item.get("live_selfie"), str):
                file_ids.add(item["live_selfie"])

        files_map = {}

        if file_ids:
            cursor = db.files.find({
                "_id": {"$in": [ObjectId(fid) for fid in file_ids]},
                "is_deleted": False
            })

            async for file in cursor:
                files_map[str(file["_id"])] = await generate_file_url(
                    storage_key=file["storage_key"],
                    backend=file["storage_backend"]
                )

        # Attach URLs (KEEP IDs)
        for item in results:
            item["submitted_photos"] = [
                {"file_id": fid, "url": files_map.get(fid)}
                for fid in item.get("submitted_photos", [])
            ]

            item["live_selfie"] = {
                "file_id": item["live_selfie"],
                "url": files_map.get(item["live_selfie"])
            }

            if item.get("Registration_Date"):
                item["Registration_Date"] = item["Registration_Date"].isoformat()

        return response.success_message(
            translate_message("VERIFICATION_QUEUE_FETCHED_SUCCESSFULLY", lang),
            data=results,
            status_code=200
        )

    except Exception as e:
        return response.error_message(
            translate_message("FAILED_TO_FETCH_VERIFICATION_QUEUE", lang),
            data=[],
            status_code=500
        )

async def approve_verification(
    user_id: str,
    admin: dict,
    lang: str = "en"
):
    # Fetch the user
    user = await user_collection.find_one({"_id": ObjectId(user_id)})

    if not user:
        return response.raise_exception(
            translate_message("USER_NOT_FOUND", lang),
            data=[],
            status_code=404
        )

    # ------------------ SIMPLE REJECTED CHECK ------------------
    rejected_exists = await verification_collection.find_one({
        "user_id": user_id,
        "status": VerificationStatusEnum.REJECTED
    })

    if rejected_exists:
        return response.raise_exception(
            translate_message("USER_CANNOT_BE_APPROVED_ALREADY_REJECTED",lang),
            data=[],
            status_code=400
        )

    # ------------------ ALREADY VERIFIED ------------------
    if user.get("is_verified", False):
        return response.raise_exception(
            translate_message("USER_ALREADY_VERIFIED", lang),
            data=[],
            status_code=400
        )

    # ------------------ FIND PENDING VERIFICATION ------------------
    pending_verification = await verification_collection.find_one({
        "user_id": user_id,
        "status": VerificationStatusEnum.PENDING
    })

    # ------------------ UPDATE USER ------------------
    await user_collection.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {
            "is_verified": True,
            "updated_at": datetime.utcnow()
        }}
    )

    # ------------------ UPDATE OR INSERT VERIFICATION ------------------
    if pending_verification:
        #  UPDATE EXISTING PENDING RECORD
        await verification_collection.update_one(
            {"_id": pending_verification["_id"]},
            {"$set": {
                "status": VerificationStatusEnum.APPROVED,
                "verified_by_admin_id": str(admin["_id"]),
                "verified_at": datetime.utcnow()
            }}
        )
    else:
        #  CREATE NEW RECORD ONLY IF NO PENDING EXISTS
        await verification_collection.insert_one({
            "user_id": user_id,
            "verified_by_admin_id": str(admin["_id"]),
            "status": VerificationStatusEnum.APPROVED,
            "verified_at": datetime.utcnow()
        })

    # ------------------ RESPONSE ------------------
    return response.success_message(
        translate_message("USER_VERIFICATION_APPROVED", lang),
        data=[{
            "user_id": user_id,
            "verified_by": str(admin["_id"]),
            "status": VerificationStatusEnum.APPROVED
        }]
    )

async def reject_verification(
    user_id: str,
    admin: dict,
    lang: str = "en"
):
    # ------------------ FETCH USER ------------------
    user = await user_collection.find_one({"_id": ObjectId(user_id)})

    if not user:
        return response.error_message(
            message=translate_message("USER_NOT_FOUND", lang),
            data=[],
            status_code=404
        )

    latest_verification = await verification_collection.find_one(
        {"user_id": user_id},
        sort=[("verified_at", -1)]
    )

    if latest_verification:
        latest_status = latest_verification.get("status")

        # Already approved
        if latest_status == VerificationStatusEnum.APPROVED:
            return response.error_message(
                message=translate_message("USER_ALREADY_VERIFIED", lang),
                data=[],
                status_code=400
            )

        # Already rejected
        if latest_status == VerificationStatusEnum.REJECTED:
            return response.error_message(
                message=translate_message("USER_ALREADY_REJECTED", lang),
                data=[],
                status_code=400
            )

    # ------------------ FIND PENDING VERIFICATION ------------------
    pending_verification = await verification_collection.find_one({
        "user_id": user_id,
        "status": VerificationStatusEnum.PENDING
    })

    # ------------------ UPDATE OR INSERT ------------------
    if pending_verification:
        #  UPDATE EXISTING PENDING RECORD
        await verification_collection.update_one(
            {"_id": pending_verification["_id"]},
            {"$set": {
                "status": VerificationStatusEnum.REJECTED,
                "verified_by_admin_id": str(admin["_id"]),
                "verified_at": datetime.utcnow()
            }}
        )
    else:
        #  INSERT ONLY IF NO PENDING EXISTS
        await verification_collection.insert_one({
            "user_id": user_id,
            "verified_by_admin_id": str(admin["_id"]),
            "status": VerificationStatusEnum.REJECTED,
            "verified_at": datetime.utcnow()
        })

    return response.success_message(
        message=translate_message("USER_VERIFICATION_REJECTED", lang),
        data=[{
            "user_id": user_id,
            "verified_by": str(admin["_id"]),
            "status": VerificationStatusEnum.REJECTED
        }],
        status_code=200
    )

async def get_approved_verification(lang: str = "en"):
    count = await verification_collection.count_documents({
        "status": VerificationStatusEnum.APPROVED
    })

    return response.success_message(
        message=translate_message("APPROVED_VERIFICATION_COUNT_FETCHED", lang),
        data=[{
            "approved_verification_count": count
        }]
    )
