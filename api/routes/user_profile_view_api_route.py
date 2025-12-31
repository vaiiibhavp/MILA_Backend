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