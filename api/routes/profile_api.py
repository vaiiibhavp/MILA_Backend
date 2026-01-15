#profile_api.py:

from fastapi import APIRouter, Depends, Query, UploadFile, File, Form
from api.controller.profile_controller import *
from core.utils.permissions import UserPermission
from schemas.response_schema import Response
from typing import List, Optional
from schemas.language_schema import *

router = APIRouter(prefix="/profile", tags=["User Profile"])


@router.get("", response_model=Response)
async def get_user_profile(
    current_user: dict = Depends(UserPermission(allowed_roles=["user"])),
    lang: str = Query("en")
):
    """
    Get logged-in user's profile details
    """
    return await get_user_profile_controller(current_user, lang)

@router.post("/upload_public_gallery", response_model=Response)
async def upload_public_gallery(
    images: List[UploadFile] = File(...),
    current_user: dict = Depends(UserPermission(["user"])),
    lang: str = Query("en")

):
    """
    Upload multiple images to public gallery
    """
    return await upload_public_gallery_controller(
        images=images,
        current_user=current_user,
        lang=lang
    )

@router.post("/upload_private_gallery", response_model=Response)
async def upload_private_gallery(
    image: List[UploadFile] = File(...),
    price: Optional[str] = Form(None),
    current_user: dict = Depends(UserPermission(["user"])),
    lang: str = Query("en")
):
    """
    Upload single image with price to private gallery
    """
    return await upload_private_gallery_controller(
        image=image,
        price=price,
        current_user=current_user,
        lang=lang
    )

@router.get("/get_public_gallery", response_model=Response)
async def get_public_gallery(
    current_user: dict = Depends(UserPermission(["user"])),
    lang: str = Query("en")
):
    """
    Get user's public gallery
    """
    return await get_public_gallery_controller(current_user, lang=lang)


@router.get("/get_private_gallery", response_model=Response)
async def get_private_gallery(
    current_user: dict = Depends(UserPermission(["user"])),
    lang: str = Query("en")
):
    """
    Get user's private gallery
    """
    return await get_private_gallery_controller(current_user, lang=lang)

@router.get(
    "/basic-details",
    response_model=Response
)
async def get_basic_profile_details(
    current_user: dict = Depends(UserPermission(["user"])),
    lang: str = Query("en")
):
    return await get_basic_profile_details_controller(
        current_user=current_user,
        lang=lang
    )

@router.put(
    "/change-language",
    response_model=Response
)
async def change_language(
    payload: ChangeLanguageRequest,
    current_user: dict = Depends(UserPermission(["user"])),
    lang: str = Query("en")
):
    return await change_language_controller(payload, current_user, lang)