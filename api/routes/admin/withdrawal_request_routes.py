from typing import Optional
from fastapi import APIRouter, Depends, Query, Path
from api.controller.admin.admin_withdrawal_controller import fetch_withdrawal_requests, \
    reject_withdrawal_request_controller, complete_withdrawal_request_controller
from core.utils.pagination import StandardResultsSetPagination, pagination_params
from core.utils.permissions import AdminPermission
from schemas.withdrawal_request_schema import AdminWithdrawalCompleteRequestModel

admin_router = APIRouter(prefix="/api/admin/withdrawals", tags=["Admin • Withdrawal Request"])
supported_langs = ["en", "fr"]

@admin_router.get("")
async def list_withdrawals(
    pagination: StandardResultsSetPagination = Depends(pagination_params),
    search: Optional[str] = Query(
        None,
        description="Global search by user name, email, wallet, status, or request ID"
    ),
    status: Optional[str] = Query(
        None,
        description="Filter by withdrawal status"
    ),
    date_from: Optional[str] = Query(
        default=None
    ),
    date_to: Optional[str] = Query(
        default=None
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
        status=status,
        date_from=date_from,
        date_to=date_to,
        lang=lang
    )

@admin_router.post("/{request_id}/reject")
async def reject_withdrawal(
    request_id: str = Path(..., description="Withdrawal request ID"),
    current_user: dict = Depends(AdminPermission(["admin"])),
    lang: str = Query("en")
):
    """
    Reject a withdrawal request (Admin only).
    """
    lang = lang if lang in supported_langs else "en"
    user_id = str(current_user["_id"])
    return await reject_withdrawal_request_controller(
        request_id=request_id,
        user_id=user_id,
        lang=lang
    )

@admin_router.post("/{request_id}/approve")
async def complete_withdrawal(
    request_id: str,
    payload: AdminWithdrawalCompleteRequestModel,
    current_user: dict = Depends(AdminPermission(["admin"])),
    lang: str = Query("en")
):
    """
    Approve a withdrawal request after verifying on-chain transaction.
    """
    lang = lang if lang in supported_langs else "en"
    user_id = str(current_user["_id"])

    return await complete_withdrawal_request_controller(
        request_id=request_id,
        payload=payload,
        user_id=user_id,
        lang=lang
    )
