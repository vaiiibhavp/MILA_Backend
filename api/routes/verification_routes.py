from fastapi import APIRouter, Depends, Query
from typing import List, Optional
from api.controller.verification_controller import (
    get_verification_queue,
    approve_verification,
    reject_verification,
    get_approved_verification
)
from core.auth import get_current_user
from schemas.verification_schema import VerificationActionRequest
from core.utils.permissions import AdminPermission

router = APIRouter(prefix="/admin/verifications")


@router.get("/get")
async def fetch_verification_queue(
    status: Optional[str] = Query("pending"),
    lang: str = "en",
    admin: dict = Depends(AdminPermission(allowed_roles=["admin"]))
):
    return await get_verification_queue(status, lang)



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