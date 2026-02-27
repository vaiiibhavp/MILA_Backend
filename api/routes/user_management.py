
from fastapi import APIRouter, Query, Depends
from datetime import datetime
from typing import List, Optional
from api.controller.user_management_controller import * 
from core.utils.pagination import StandardResultsSetPagination, pagination_params
from schemas.user_management_schema import *
from core.utils.permissions import AdminPermission , BothPermission


router = APIRouter(prefix="/usermanagement", tags=["Admin Users"])


@router.get("/users")
async def get_all_users(
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    gender: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    verification: Optional[str] = Query(None),
    membership: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    pagination: StandardResultsSetPagination = Depends(pagination_params),
    lang: str = "en",
    admin: dict = Depends(AdminPermission(allowed_roles=["admin"]))
):
    return await get_admin_users(
        status=status,
        search=search,
        gender=gender,
        country=country,
        verification=verification,
        membership=membership,
        date_from=date_from,
        date_to=date_to,
        pagination=pagination,
        lang=lang
    )



@router.get("/users/{user_id}")
async def get_user_details(
    user_id: str,
    lang: str = "en",
    admin: dict = Depends(BothPermission(allowed_roles=["admin" , "user"]))
):
    return await get_admin_user_details(
        user_id=user_id,
        current_user=admin,
        lang=lang
    )


@router.post("/users/suspend/{user_id}")
async def suspend_user(
    user_id: str,
    days: int = Query(7, ge=1),
    lang: str = "en",
    admin: dict = Depends(AdminPermission(allowed_roles=["admin"]))
):
    return await admin_suspend_user(
        user_id=user_id,
        days=days,
        admin_id=str(admin["_id"]),
        lang=lang
    )

@router.post("/users/block/{user_id}")
async def block_user(
    user_id: str,
    lang: str = "en",
    admin: dict = Depends(AdminPermission(allowed_roles=["admin"]))
):
    return await admin_block_user(
        user_id=  user_id,
        admin_id = str(admin["_id"]),
        lang=lang
    )

@router.post("/users/delete/{user_id}")
async def delete_user_account(
    user_id: str,
    lang: str = "en",
    admin: dict = Depends(AdminPermission(allowed_roles=["admin"]))
):
    return await admin_delete_user(
        user_id=user_id,
        admin_id=str(admin["_id"]),
        lang=lang
    )
