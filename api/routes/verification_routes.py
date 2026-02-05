from fastapi import APIRouter, Depends, Query
from typing import List, Optional
from api.controller.verification_controller import (
    get_verification_user_details_controller,
    approve_verification,
    reject_verification,
    get_approved_verification,
    get_pending_verification_users_controller
)
from core.utils.pagination import StandardResultsSetPagination, pagination_params
from schemas.verification_schema import VerificationActionRequest
from core.utils.permissions import AdminPermission

router = APIRouter(prefix="/admin/verifications")



@router.get("/pending-list")
async def get_pending_verification_users(
    search: Optional[str] = Query(None),
    pagination: StandardResultsSetPagination = Depends(pagination_params),
    lang: str = "en",
    admin: dict = Depends(AdminPermission(allowed_roles=["admin"]))
):
    return await get_pending_verification_users_controller(
        search=search,
        pagination=pagination,
        lang=lang
    )

@router.get("/get-details/{user_id}")
async def get_verification_user_details(
    user_id: str,
    lang: str = "en",
    admin: dict = Depends(AdminPermission(allowed_roles=["admin"]))
):
    return await get_verification_user_details_controller(
        user_id=user_id,
        lang=lang
    )



@router.post("/approve")
async def approve_user_verification(
    payload: VerificationActionRequest,
    admin: dict = Depends(AdminPermission(allowed_roles=["admin"])),
    lang: str = "en"
):
    return await approve_verification(
        user_id=payload.user_id,
        admin=admin,
        lang=lang
    )



@router.post("/reject")
async def reject_user_verification(
    payload: VerificationActionRequest,
    admin: dict = Depends(AdminPermission(allowed_roles=["admin"])),
    lang: str = "en"
):
    return await reject_verification(
        user_id=payload.user_id,
        admin=admin,
        lang=lang
    )


@router.get("/count/approved")
async def get_approved_verification_count(
    admin: dict = Depends(AdminPermission(allowed_roles=["admin"])),
    lang: str = "en"
):
    return await get_approved_verification(lang)