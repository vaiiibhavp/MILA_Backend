#like_route_api.py

from fastapi import APIRouter, Depends, Query, UploadFile, File, Form
from api.controller.like_controller import *
from core.utils.permissions import UserPermission
from schemas.response_schema import Response
from typing import List, Optional
from schemas.language_schema import *
from core.utils.pagination import StandardResultsSetPagination, pagination_params

router = APIRouter(prefix="", tags=["User Profile"])

@router.get("/likes", response_model=Response)
async def get_likes(
    current_user: dict = Depends(UserPermission(["user"])),
    pagination: StandardResultsSetPagination = Depends(pagination_params),
    lang: str = Query("en")
):
    return await get_users_who_liked_me_for_premium(
        current_user=current_user,
        pagination=pagination,
        lang=lang
    )
