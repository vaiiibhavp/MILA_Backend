from fastapi import APIRouter, Depends, Query, Path

from api.controller.admin.admin_token_controller import create_token_package_plan, update_token_package_plan_controller, \
    soft_delete_token_package_plan_controller, fetch_active_token_package_plans
from core.utils.pagination import StandardResultsSetPagination, pagination_params
from core.utils.permissions import AdminPermission
from schemas.token_package_schema import TokenPackagePlanResponseModel, TokenPackageCreateRequestModel, \
    TokenPackagePlanUpdateRequestModel

admin_router = APIRouter(prefix="/api/admin/token-plans", tags=["Admin • Token Plans"])
supported_langs = ["en", "fr"]

@admin_router.get("")
async def list_token_plans(
    current_user: dict = Depends(AdminPermission(allowed_roles=["admin"])),
    pagination: StandardResultsSetPagination = Depends(pagination_params),
    search:str = Query(None),
    lang: str = Query(None)
):
    """
    List all token package plans.
    Soft-deleted plans are excluded.
    """

    lang = lang if lang in supported_langs else "en"

    return await fetch_active_token_package_plans(
        pagination=pagination,
        search=search,
        lang=lang
    )

@admin_router.post("", response_model=TokenPackagePlanResponseModel)
async def create_token_plan(
    request: TokenPackageCreateRequestModel,
    current_user: dict = Depends(AdminPermission(allowed_roles=["admin"])),
    lang: str = Query(None)
):
    """
    Create a new token package plan (Admin only).
    """

    lang = lang if lang in supported_langs else "en"
    user_id = str(current_user["_id"])
    return await create_token_package_plan(request=request, user_id=user_id, lang=lang)

@admin_router.put("/{plan_id}")
async def update_token_plan(
    request: TokenPackagePlanUpdateRequestModel,
    plan_id: str = Path(..., description="Token package plan ID"),
    current_user: dict = Depends(AdminPermission(allowed_roles=["admin"])),
    lang: str = Query(None)
):
    """
    Fully update a token package plan (Admin only).
    All fields are required and must not be empty.
    """

    lang = lang if lang in supported_langs else "en"

    return await update_token_package_plan_controller(
        plan_id=plan_id,
        payload=request,
        current_user=current_user,
        lang=lang
    )

@admin_router.delete("/{plan_id}")
async def soft_delete_token_plan(
    plan_id: str = Path(..., description="Token package plan ID"),
    current_user: dict = Depends(AdminPermission(allowed_roles=["admin"])),
    lang: str = Query(None)
):
    """
    Soft delete token package plan (Admin only).
    Marks the plan as deleted.
    """

    lang = lang if lang in supported_langs else "en"

    return await soft_delete_token_package_plan_controller(
        plan_id=plan_id,
        current_user=current_user,
        lang=lang
    )