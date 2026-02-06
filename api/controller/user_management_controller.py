from fastapi import Depends
from typing import Optional
from datetime import datetime
from core.utils.response_mixin import CustomResponseMixin
from core.utils.pagination import StandardResultsSetPagination ,pagination_params ,build_paginated_response
from services.translation import translate_message
from config.models.user_management_model import UserManagementModel
from core.utils.helper import serialize_datetime_fields

response = CustomResponseMixin()

# Get all users table
async def get_admin_users(
    status: Optional[str],
    lang: str = "en",
    search: Optional[str] = None,
    gender: Optional[str] = None,
    country: Optional[str] = None,
    verification: Optional[str] = None,
    membership: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    pagination: StandardResultsSetPagination = Depends(pagination_params)
):
    try:
        users, total_records = await UserManagementModel.get_admin_users_pipeline(
            status,
            search,
            gender,
            country,
            verification,
            membership,
            date_from,
            date_to,
            pagination
        )

        for user in users:
            if user.get("registration_date"):
                user["registration_date"] = user["registration_date"].isoformat()

        paginated_response = build_paginated_response(
            records=users,
            page=pagination.page or 1,
            page_size=pagination.limit or len(users),
            total_records=total_records
        )

        return response.success_message(
            translate_message("USERS_FETCHED_SUCCESSFULLY", lang),
            data=paginated_response,
            status_code=200
        )

    except Exception as e:
        return response.error_message(
            translate_message("SOMETHING_WENT_WRONG", lang),
            data=str(e),
            status_code=500
        )

# Get complete user details (View)
async def get_admin_user_details(user_id: str, lang: str = "en"):
    try:
        # ---------------- USER ----------------
        user = await UserManagementModel.get_user(user_id)
        if not user:
            return response.error_message(
                translate_message("USER_NOT_FOUND", lang),
                data=[],
                status_code=404
            )

        # ---------------- ONBOARDING ----------------
        onboarding = await UserManagementModel.get_onboarding(user_id)

        # ---------------- COUNTRY ----------------
        country = (
            await UserManagementModel.get_country(onboarding["country"])
            if onboarding and onboarding.get("country") else None
        )

        # ---------------- VERIFICATION ----------------
        verification_status = await UserManagementModel.get_latest_verification_status(user_id)

        # ---------------- MATCHES ----------------
        match_count, matched_users = await UserManagementModel.get_matches(user_id)

        # ---------------- PHOTOS ----------------
        photos, profile_photo = await UserManagementModel.get_user_photos(
            onboarding.get("images") if onboarding else []
        )

        # ---------------- RESPONSE ----------------
        result = {
            "user_id": user_id,

            "username": user.get("username"),
            "email": user.get("email"),
            "profile_photo": profile_photo,

            "verification_status": verification_status,
            "login_status": user.get("login_status"),
            "membership_type": user.get("membership_type"),

            "gender": onboarding.get("gender") if onboarding else None,
            "sexual_orientation": onboarding.get("sexual_orientation") if onboarding else None,
            "relationship_status": onboarding.get("marital_status") if onboarding else None,
            "city": onboarding.get("city") if onboarding else None,

            "country": country,
            "registration_date": user.get("created_at"),

            "bio": onboarding.get("bio") if onboarding else None,
            "interests": onboarding.get("passions") if onboarding else None,

            "photos": photos,
            "match_count": match_count,
            "matched_users": matched_users
        }

        return response.success_message(
            translate_message("USER_DETAILS_FETCHED_SUCCESSFULLY", lang),
            data=serialize_datetime_fields(result),
            status_code=200
        )

    except Exception as e:
        return response.error_message(
            translate_message("FAILED_TO_FETCH_USER_DETAILS", lang),
            data=str(e),
            status_code=500
        )

async def admin_suspend_user(
    user_id: str,
    days: int,
    admin_id: str,
    lang: str = "en"
):
    try:
        result = await UserManagementModel.suspend_user(
            user_id=user_id,
            admin_id=admin_id,
            days=days,
            lang=lang
        )

        #  Handle validation errors from model
        if result.get("error"):
            return response.error_message(
                message=result["message"],
                data=[],
                status_code=result["status_code"]
            )

        suspended_until = result["data"]["suspended_until"]

        return response.success_message(
            translate_message("USER_SUSPENDED_SUCCESSFULLY", lang),
            data=[{
                "user_id": user_id,
                "suspended_until": suspended_until.isoformat()
            }],
            status_code=200
        )

    except Exception as e:
        return response.error_message(
            translate_message("FAILED_TO_SUSPEND_USER", lang),
            data=str(e),
            status_code=500
        )

async def admin_block_user(
    user_id: str,
    admin_id: str,
    lang: str = "en"
):
    try:
        result = await UserManagementModel.block_user(
            user_id=user_id,
            admin_id=admin_id,
            lang=lang
        )

        #  Handle validation errors
        if result.get("error"):
            return response.error_message(
                message=result["message"],
                data=[],
                status_code=result["status_code"]
            )

        return response.success_message(
            translate_message("USER_BLOCKED_SUCCESSFULLY", lang),
            data=[{
                "user_id": user_id,
                "blocked_by": admin_id
            }],
            status_code=200
        )

    except Exception as e:
        return response.error_message(
            translate_message("FAILED_TO_BLOCK_USER", lang),
            data=str(e),
            status_code=500
        )



async def admin_delete_user(
    user_id: str,
    admin_id: str,
    lang: str = "en"
):
    try:
        result = await UserManagementModel.delete_user(
            user_id=user_id,
            admin_id=admin_id,
            lang=lang
        )

        #  Validation errors from model
        if result.get("error"):
            return response.error_message(
                message=result["message"],
                data=[],
                status_code=result["status_code"]
            )

        return response.success_message(
            translate_message("ACCOUNT_DELETED_SUCCESSFULLY", lang),
            data=[{
                "user_id": user_id,
                "deleted_by": admin_id
            }],
            status_code=200
        )

    except Exception as e:
        return response.error_message(
            translate_message("FAILED_TO_DELETE_ACCOUNT", lang),
            data=str(e),
            status_code=500
        )
