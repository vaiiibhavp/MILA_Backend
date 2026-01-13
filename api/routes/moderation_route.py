from fastapi import APIRouter, Query, Depends
from datetime import datetime
from typing import List, Optional
from api.controller.user_management_controller import * 
from core.utils.pagination import StandardResultsSetPagination, pagination_params
from schemas.user_management_schema import *
from core.utils.permissions import AdminPermission
from api.controller.moderation_controller import get_reported_users_controller , get_report_details_controller

router = APIRouter()


@router.get("/reported-users")
async def get_reported_users(
    status: Optional[str] = Query("all"),
    search: Optional[str] = Query(None),
    pagination: StandardResultsSetPagination = Depends(pagination_params),
    lang: str = "en",
    admin: dict = Depends(AdminPermission(allowed_roles=["admin"]))
):
    return await get_reported_users_controller(
        status=status,
        search=search,
        pagination=pagination,
        lang=lang
    )

@router.get("/reported-users/{report_id}")
async def get_report_details(
    report_id: str,
    lang: str = "en",
    admin: dict = Depends(AdminPermission(allowed_roles=["admin"]))
):
    return await get_report_details_controller(
        report_id=report_id,
        lang=lang
    )

