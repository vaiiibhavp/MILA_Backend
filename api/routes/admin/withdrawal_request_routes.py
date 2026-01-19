from typing import Optional
from fastapi import APIRouter, Depends, Query, Path
from api.controller.admin.admin_withdrawal_controller import fetch_withdrawal_requests
from core.utils.pagination import StandardResultsSetPagination, pagination_params
from core.utils.permissions import AdminPermission

admin_router = APIRouter(prefix="/api/admin/withdrawals", tags=["Admin • Withdrawal Request"])
supported_langs = ["en", "fr"]

@admin_router.get("")
async def list_withdrawals(
    pagination: StandardResultsSetPagination = Depends(pagination_params),
    search: Optional[str] = Query(
        None,
        description="Global search by user name, email, wallet, status, or request ID"
    ),
    current_user: dict = Depends(AdminPermission(["admin"])),
    lang: str = Query(None)
):
    lang = lang if lang in supported_langs else "en"
    user_id = str(current_user["_id"])
    return await fetch_withdrawal_requests(
        user_id=user_id,
        pagination=pagination,
        search=search,
        lang=lang
    )