#profile_api_route.py:

from fastapi import APIRouter, Depends, Query, UploadFile, File, Form
from api.controller.profile_view_controller import *
from core.utils.permissions import UserPermission
from schemas.response_schema import Response
from typing import List, Optional
from core.utils.pagination import *

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
    return await get_profile_controller(
        user_id=user_id,
        viewer=current_user,
        lang=lang
    )

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

@router.post(
    "/{profile_user_id}/send-gift",
    response_model=Response
)
async def send_gift(
    profile_user_id: str,
    payload: dict,
    current_user: dict = Depends(UserPermission(allowed_roles=["user"])),
    lang: str = Query("en")
):
    """
    Send a virtual gift to another user's profile.

    This endpoint allows a logged-in user to send a gift to the profile they
    are currently viewing.

    Flow & Rules:
    - User cannot send a gift to their own profile
    - Gift must exist and be active
    - Sender must have sufficient token balance
    - Gift token value is deducted from sender
    - Gift token value is credited to receiver
    - Token transaction history is recorded for both users

    Request Body:
    - gift_id (string): ID of the gift to send

    Path Params:
    - profile_user_id (string): User ID of the profile receiving the gift

    Query Params:
    - lang (string, optional): Language code for localized messages (default: "en")

    Auth:
    - Requires authenticated user with role "user"

    Response:
    - gift_id
    - gift_name
    - tokens_deducted
    - sender_remaining_tokens
    """
    return await send_gift_to_profile(
        profile_user_id=profile_user_id,
        gift_id=payload.get("gift_id"),
        viewer=current_user,
        lang=lang
    )

@router.post("/search/profiles", response_model=Response)
async def search_profiles(
    payload: dict,
    pagination: StandardResultsSetPagination = Depends(pagination_params),
    current_user: dict = Depends(UserPermission(["user"])),
    lang: str = Query("en")
):
    return await search_profiles_controller(
        payload=payload,
        current_user=current_user,
        pagination=pagination,
        lang=lang
    )

