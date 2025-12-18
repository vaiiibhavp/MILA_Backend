#profile_api_route.py:

from fastapi import APIRouter, Depends, Query, UploadFile, File, Form
from api.controller.profile_view_controller import *
from core.utils.permissions import UserPermission
from schemas.response_schema import Response
from typing import List, Optional

router = APIRouter(prefix="/view", tags=["User Profile"])


@router.get("/{user_id}", response_model=Response)
async def get_profile(
    user_id: str,
    current_user: dict = Depends(UserPermission(allowed_roles=["user"])),
    lang: str = Query(None)
):
    """
    Get logged-in user's profile details
    """
    return await get_profile_controller(user_id, lang)

@router.get(
    "/{profile_user_id}/private-gallery/image/{image_id}",
    response_model=Response
)
async def get_private_image(
    profile_user_id: str,
    image_id: str,
    current_user: dict = Depends(UserPermission(allowed_roles=["user"])),
    lang: str = Query("en")
):
    return await get_private_gallery_image(
        profile_user_id=profile_user_id,
        viewer=current_user,
        image_id=image_id,
        lang=lang
    )

@router.post(
    "/{profile_user_id}/private-gallery/image/{image_id}/buy",
    response_model=Response
)
async def buy_private_image(
    profile_user_id: str,
    image_id: str,
    current_user: dict = Depends(UserPermission(allowed_roles=["user"])),
    lang: str = Query("en")
):
    return await buy_private_gallery_image(
        profile_user_id=profile_user_id,
        image_id=image_id,
        viewer=current_user,
        lang=lang
    )

@router.get(
    "/profile/{profile_user_id}/gallery",
    response_model=Response
)
async def get_profile_gallery_route(
    profile_user_id: str,
    current_user: dict = Depends(UserPermission(allowed_roles=["user"])),
    lang: str = Query("en")
):
    return await get_profile_gallery(
        profile_user_id=profile_user_id,
        viewer=current_user,
        lang=lang
    )
