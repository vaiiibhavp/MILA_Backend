from datetime import datetime
from bson import ObjectId
import copy
from config.db_config import db
from schemas.verification_schema import VerificationStatusEnum
from core.utils.pagination import StandardResultsSetPagination , build_paginated_response
from api.controller.files_controller import generate_file_url
from core.utils.response_mixin import CustomResponseMixin
from config.db_config import verification_collection , user_collection , onboarding_collection
from services.translation import translate_message
from config.basic_config import settings
from core.utils.helper import credit_tokens_for_verification
from core.utils.core_enums import NotificationType, NotificationRecipientType
from services.notification_service import send_notification
from core.utils.helper import get_admin_id_by_email
from core.templates.email_templates import verification_approved_template ,verification_rejected_template
from core.utils.auth_utils import send_email
from core.utils.core_enums import MembershipType
from config.models.onboarding_model import GenderEnum

response = CustomResponseMixin()

async def get_verification_user_details_controller(
    user_id: str,
    lang: str = "en"
):
    try:
        pipeline = [
            {
                "$match": {
                    "user_id": user_id,
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
            {"$unwind": "$user"}
        ]

        # ---------------- VERIFICATION LOOKUP ----------------
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
                    "verification_status": {
                        "$cond": [
                            {"$gt": [{"$size": {"$ifNull": ["$verification", []]}}, 0]},
                            {"$arrayElemAt": ["$verification.status", 0]},
                            VerificationStatusEnum.PENDING.value
                        ]
                    }
                }
            }
        ])

        # ---------------- FINAL PROJECTION ----------------
        pipeline.append({
            "$project": {
                "_id": 0,
                "user_id": {"$toString": "$user._id"},
                "username": "$user.username",
                "submitted_photos": "$images",
                "live_selfie": "$selfie_image",
                "verification_status": 1,
                "Registration_Date": "$created_at"
            }
        })

        result = await db.user_onboarding.aggregate(pipeline).to_list(1)

        if not result:
            return response.error_message(
                translate_message("USER_NOT_FOUND", lang),
                data={},
                status_code=404
            )

        user_data = result[0]

        # ---------------- FILE URL RESOLUTION ----------------
        file_ids = set(user_data.get("submitted_photos", []))
        if isinstance(user_data.get("live_selfie"), str):
            file_ids.add(user_data["live_selfie"])

        files_map = {}

        if file_ids:
            async for file in db.files.find(
                {
                    "_id": {"$in": [ObjectId(fid) for fid in file_ids]},
                    "is_deleted": False
                }
            ):
                files_map[str(file["_id"])] = await generate_file_url(
                    storage_key=file["storage_key"],
                    backend=file["storage_backend"]
                )

        # Submitted photos
        user_data["submitted_photos"] = [
            {
                "file_id": fid,
                "url": files_map.get(fid)
            }
            for fid in user_data.get("submitted_photos", [])
        ]

        # Live selfie
        user_data["live_selfie"] = {
            "file_id": user_data.get("live_selfie"),
            "url": files_map.get(user_data.get("live_selfie"))
        }

        # Date serialize
        if user_data.get("Registration_Date"):
            user_data["Registration_Date"] = (
                user_data["Registration_Date"].isoformat()
            )

        return response.success_message(
            translate_message("VERIFICATION_USER_DETAILS_FETCHED_SUCCESSFULLY", lang),
            data=user_data,
            status_code=200
        )

    except Exception as e:
        return response.error_message(
            translate_message("FAILED_TO_FETCH_VERIFICATION_USER_DETAILS", lang),
            data=[str(e)],
            status_code=500
        )

async def approve_verification(
    user_id: str,
    admin: dict,
    lang: str = "en"
):
    # ------------------ FETCH USER ------------------
    user = await user_collection.find_one(
        {"_id": ObjectId(user_id)},
        {
            "email": 1,
            "username": 1,
            "is_verified": 1
        }
    )

    if not user:
        return response.raise_exception(
            translate_message("USER_NOT_FOUND", lang),
            data=[],
            status_code=404
        )

    # ------------------ FETCH ONBOARDING (FOR GENDER) ------------------
    onboarding = await onboarding_collection.find_one(
        {"user_id": user_id},
        {"gender": 1}
    )

    gender = onboarding.get("gender") if onboarding else None

    # ------------------ SIMPLE REJECTED CHECK ------------------
    rejected_exists = await verification_collection.find_one({
        "user_id": user_id,
        "status": VerificationStatusEnum.REJECTED
    })

    if rejected_exists:
        return response.raise_exception(
            translate_message("USER_CANNOT_BE_APPROVED_ALREADY_REJECTED", lang),
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

    # ------------------ USER UPDATE ------------------
    update_data = {
        "is_verified": True,
        "updated_at": datetime.utcnow()
    }

    # FEMALE → PREMIUM (FROM ONBOARDING)
    if gender and gender.lower() == GenderEnum.female:
        update_data["membership_type"] = MembershipType.PREMIUM

    await user_collection.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": update_data}
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

    #  VERIFICATION REWARD TOKEN LOGIC
    await credit_tokens_for_verification(
        user_id=user_id,
        admin_id=str(admin["_id"])
    )
    await send_notification(
        recipient_id=user_id,
        recipient_type=NotificationRecipientType.USER,
        notification_type=NotificationType.VERIFICATION_APPROVED,
        title="PUSH_TITLE_VERIFICATION_APPROVED",
        message="PUSH_MESSAGE_VERIFICATION_APPROVED",
        reference={
            "entity": "verification",
            "entity_id": user_id
        },
        sender_user_id=str(admin["_id"]),
        send_push=True
    )

    # ------------------ EMAIL ------------------
    if user.get("email"):
        subject, body = verification_approved_template(
            username=user.get("username", "User"), lang=lang
        )
        await send_email(
            to_email=user["email"],
            subject=subject,
            body=body,
            is_html=True
        )

    # ------------------ RESPONSE ------------------
    return response.success_message(
        translate_message("USER_VERIFICATION_APPROVED", lang),
        data=[{
            "user_id": user_id,
            "verified_by": str(admin["_id"]),
            "status": VerificationStatusEnum.APPROVED,
            "tokens_rewarded": settings.VERIFICATION_REWARD_TOKENS,
            "membership_type": update_data.get("membership_type", "unchanged")
        }]
    )

async def reject_verification(user_id: str, admin: dict, lang: str = "en"):

    user = await user_collection.find_one(
        {"_id": ObjectId(user_id)},
        {"email": 1, "username": 1}
    )

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
        if latest_verification.get("status") == VerificationStatusEnum.APPROVED:
            return response.error_message(
                message=translate_message("USER_ALREADY_VERIFIED", lang),
                data=[],
                status_code=400
            )

        if latest_verification.get("status") == VerificationStatusEnum.REJECTED:
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
    await send_notification(
        recipient_id=user_id,
        recipient_type=NotificationRecipientType.USER,
        notification_type=NotificationType.VERIFICATION_REJECTED,
        title="PUSH_TITLE_VERIFICATION_REJECTED",
        message="PUSH_MESSAGE_VERIFICATION_REJECTED",
        reference={"entity": "verification", "entity_id": user_id},
        sender_user_id=str(admin["_id"]),
        send_push=True
    )

    # ------------------ SEND EMAIL (NEW) ------------------
    if user.get("email"):
        subject, body = verification_rejected_template(
            username=user.get("username", "User"), lang=lang
        )
        await send_email(
            to_email=user["email"],
            subject=subject,
            body=body,
            is_html=True
        )

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

async def get_pending_verification_users_controller(
    search: str | None,
    pagination: StandardResultsSetPagination,
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
                    "userObjId": {
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
                    "localField": "userObjId",
                    "foreignField": "_id",
                    "as": "user"
                }
            },
            {"$unwind": "$user"},
            {
                "$lookup": {
                    "from": "deleted_accounts",
                    "let": {"uid": {"$toString": "$user._id"}},
                    "pipeline": [
                        {
                            "$match": {
                                "$expr": {
                                    "$eq": ["$user_id", "$$uid"]
                                }
                            }
                        }
                    ],
                    "as": "deleted_user"
                }
            },
            {
                "$match": {
                    "deleted_user": {"$size": 0}
                }
            }
        ]

        # ---------------- SEARCH ----------------
        if search:
            pipeline.append({
                "$match": {
                    "user.username": {"$regex": search, "$options": "i"}
                }
            })

        # ---------------- VERIFICATION LOOKUP ----------------
        pipeline.extend([
            {
                "$lookup": {
                    "from": "verification_history",
                    "let": {"uid": "$user_id"},
                    "pipeline": [
                        {"$match": {"$expr": {"$eq": ["$user_id", "$$uid"]}}},
                        {"$sort": {"verified_at": -1}},
                        {"$limit": 1}
                    ],
                    "as": "verification"
                }
            },
            {
                "$addFields": {
                    "verification_status": {
                        "$cond": [
                            {"$gt": [{"$size": {"$ifNull": ["$verification", []]}}, 0]},
                            {"$arrayElemAt": ["$verification.status", 0]},
                            VerificationStatusEnum.PENDING.value
                        ]
                    }
                }
            }
        ])

        # ---------------- ONLY PENDING ----------------
        pipeline.append({
            "$match": {
                "verification_status": VerificationStatusEnum.PENDING.value
            }
        })

        # ---------------- COUNT ----------------
        count_pipeline = list(pipeline)
        count_pipeline.append({"$count": "total"})

        # ---------------- SORT + PAGINATION ----------------
        pipeline.append({"$sort": {"created_at": -1}})

        if pagination and pagination.skip is not None:
            pipeline.append({"$skip": pagination.skip})

        if pagination and pagination.limit is not None:
            pipeline.append({"$limit": pagination.limit})

        # ---------------- FINAL PROJECTION ----------------
        pipeline.append({
            "$project": {
                "_id": 0,
                "user_id": {"$toString": "$user._id"},
                "username": "$user.username",
                "selfie": "$selfie_image",
                "verification_status": 1,
                "registration_date": "$user.created_at"
            }
        })

        # ---------------- EXECUTION ----------------
        records = await db.user_onboarding.aggregate(pipeline).to_list(None)
        count_result = await db.user_onboarding.aggregate(count_pipeline).to_list(1)

        total_records = count_result[0]["total"] if count_result else 0

        # ---------------- SELFIE URL RESOLUTION ----------------
        file_ids = {r["selfie"] for r in records if isinstance(r.get("selfie"), str)}
        files_map = {}

        if file_ids:
            async for f in db.files.find(
                {"_id": {"$in": [ObjectId(fid) for fid in file_ids]}, "is_deleted": False}
            ):
                files_map[str(f["_id"])] = await generate_file_url(
                    f["storage_key"], f["storage_backend"]
                )

        for r in records:
            selfie_id = r.get("selfie")
            r["selfie"] = (
                {"file_id": selfie_id, "url": files_map.get(selfie_id)}
                if selfie_id else None
            )

            if r.get("registration_date"):
                r["registration_date"] = r["registration_date"].isoformat()

        # ---------------- PAGINATION RESPONSE ----------------
        page = pagination.page or 1
        page_size = pagination.limit or total_records

        data = build_paginated_response(
            records=records,
            page=page,
            page_size=page_size,
            total_records=total_records
        )

        return response.success_message(
            translate_message("VERIFICATION_QUEUE_FETCHED_SUCCESSFULLY", lang),
            data=data,
            status_code=200
        )

    except Exception as e:
        return response.error_message(
            translate_message("FAILED_TO_FETCH_VERIFICATION_QUEUE", lang),
            data=str(e),
            status_code=500
        )
