from fastapi import APIRouter, Depends , File , Query ,Body
from datetime import datetime
from core.utils.permissions import AdminPermission
from api.controller.admin.transaction_controller import fetch_all_transactions_controller ,get_subscription_bonus_token_controller,update_subscription_bonus_token_controller
from core.utils.pagination import StandardResultsSetPagination ,pagination_params
from core.utils.core_enums import TransactionTab

admin_router = APIRouter(prefix="/admin", tags=["Admin transactions"])


@admin_router.get("/transactions")
async def get_all_transactions(
    tab: TransactionTab = Query(...),
    search: str | None = Query(None),
    status: str | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    pagination: StandardResultsSetPagination = Depends(pagination_params),
    lang: str = "en",
    admin: dict = Depends(AdminPermission(allowed_roles=["admin"]))
):
    return await fetch_all_transactions_controller(
        tab=tab,
        search=search,
        status=status,
        date_from=date_from,
        date_to=date_to,
        pagination=pagination,
        lang=lang
    )

@admin_router.get("/subscription-bonus-token")
async def get_subscription_bonus_token(
    admin: dict = Depends(AdminPermission(allowed_roles=["admin"])),
    lang :str = "en"
):
    return await get_subscription_bonus_token_controller(lang=lang)


@admin_router.patch("/subscription-bonus-token")
async def update_subscription_bonus_token(
    tokens: int = Body(..., embed=True),
    admin: dict = Depends(AdminPermission(allowed_roles=["admin"])),
    lang :str = "en"
):
    return await update_subscription_bonus_token_controller(tokens, lang=lang)
