#user_profile_view_api_route.py:

from fastapi import APIRouter, Depends, Query, UploadFile, File
from api.controller.user_profile_view_controller import *
from core.utils.permissions import UserPermission
from schemas.response_schema import Response

router = APIRouter(prefix="", tags=["User Profile"])

@router.get(
    "/get-editable-data",
    response_model=Response
)
async def get_edit_profile(
    current_user: dict = Depends(UserPermission(allowed_roles=["user"])),
    lang: str = Query("en")
):
    return await get_edit_profile_controller(
        current_user=current_user,
        lang=lang
    )

@router.put(
    "/profile-edit",
    response_model=Response
)
async def update_profile(
    payload: EditProfileRequest,
    current_user: dict = Depends(UserPermission(["user"])),
    lang: str = Query("en")
):
    return await update_edit_profile_controller(payload, current_user, lang)

@router.post(
    "/verification-retry-selfie",
    response_model=Response
)
async def retry_verification_selfie(
    selfie: UploadFile = File(...),
    current_user: dict = Depends(UserPermission(["user"])),
    lang: str = Query("en")
):
    return await retry_verification_selfie_controller(
        selfie, current_user, lang
    )

@router.get(
    "/verification-selfie",
    response_model=Response
)
async def get_verification_selfie(
    current_user: dict = Depends(UserPermission(["user"])),
    lang: str = Query("en")
):
    return await get_verification_selfie_controller(
        current_user, lang
    )

@router.get("/notifications")
async def get_notifications(
    current_user: dict = Depends(UserPermission(["user"])),
    lang: str = Query("en")
):
    return await get_notifications_controller(current_user, lang)

@router.patch("/{notification_id}/read")
async def read_single_notification(
    notification_id: str,
    current_user: dict = Depends(UserPermission(["user"])),
    lang: str = Query("en")
):
    return await mark_notification_read(
        notification_id=notification_id,
        current_user=current_user,
        lang=lang
    )

@router.patch("/read-all")
async def read_all_notifications(
    current_user: dict = Depends(UserPermission(["user"])),
    lang: str = Query("en")
):
    return await mark_all_notifications_read(
        current_user=current_user,
        lang=lang
    )

@router.delete("/delete-account")
async def delete_account(
    current_user: dict = Depends(UserPermission(["user"])),
    lang: str = Query("en")
):
    return await delete_account_controller(current_user, lang)
