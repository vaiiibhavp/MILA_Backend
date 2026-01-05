from datetime import datetime
from bson import ObjectId
from fastapi import HTTPException
from config.db_config import db
from bson.errors import InvalidId
from schemas.verification_schema import VerificationStatusEnum
from api.controller.files_controller import generate_file_url
from core.utils.response_mixin import CustomResponseMixin
from config.db_config import verification_collection , user_collection
from services.translation import translate_message

response = CustomResponseMixin()

async def get_verification_queue(
    status: str,
    lang: str = "en"
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
                    "userObjectId": {"$toObjectId": "$user_id"}
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

        if status == "pending":
            pipeline.append({"$match": {"user.is_verified": False}})
        elif status == "approved":
            pipeline.append({"$match": {"user.is_verified": True}})

        pipeline.append({
            "$project": {
                "_id": 0,
                "user_id": {"$toString": "$user._id"},
                "username": "$user.username",

                "submitted_photos": "$images",
                "live_selfie": "$selfie_image",

                "verification_status": {
                    "$cond": {
                        "if": {"$eq": ["$user.is_verified", True]},
                        "then": "approved",
                        "else": "pending"
                    }
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

    except Exception:
        return response.error_message(
            translate_message("FAILED_TO_FETCH_VERIFICATION_QUEUE", lang),
            data=[],
            status_code=500
        )

async def approve_verification(user_id: str, admin: dict , lang: str = "en"):
    # Fetch the user
    user = await user_collection.find_one({"_id": ObjectId(user_id)})

    if not user:
        return response.raise_exception(
            message=translate_message("USER_NOT_FOUND"),
            data=[],
            status_code=404
        )

    if user.get("is_verified", False):
        return response.raise_exception(
            message=translate_message("USER_ALREADY_VERIFIED"),
            data=[],
            status_code=400
        )

    #  Update user verification status
    await user_collection.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {
            "is_verified": True,
            "updated_at": datetime.utcnow()
        }}
    )

    #  Store successful verification record with status APPROVED
    await verification_collection.insert_one({
        "user_id": user_id,
        "verified_by_admin_id": str(admin["_id"]),
        "status": "approved",
        "verified_at": datetime.utcnow(),

    })

    return response.success_message(
        message=translate_message("USER_VERIFICATION_APPROVED"),
        data=[{
            "user_id": user_id,
            "verified_by": str(admin["_id"]),
            "status": "approved"
        }]
    )

async def reject_verification(user_id: str, admin , lang: str = "en"):
    user = await user_collection.find_one({"_id":ObjectId(user_id)})

    if not user:
        return response.error_message(
            message=translate_message("USER_NOT_FOUND"),
            data=[],
            status_code=404
        )
    
    approved_verification = await verification_collection.find_one({
        "user_id": user_id,
        "status": "approved"
    })

    if approved_verification:
        return response.error_message(
            message=translate_message("USER_ALREADY_APPROVED"),
            data=[],
            status_code=400
        )
    
    await verification_collection.insert_one({
        "user_id": user_id,
        "verified_by_admin_id": str(admin["_id"]),
        "status": "rejected",
        "verified_at": datetime.utcnow(),
        })
    
    return response.success_message(
        message=translate_message("USER_VERIFICATION_REJECTED"),
        data=[{
        "user_id": user_id,
        "verified_by": str(admin["_id"]),
        "status": "rejected"
        }]
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
