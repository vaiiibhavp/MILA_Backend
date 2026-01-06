from fastapi import APIRouter, Depends, Body, Query
from api.controller.fcm_controller import *
from core.utils.permissions import UserPermission
from core.utils.pagination import StandardResultsSetPagination, pagination_params

router = APIRouter(prefix="",tags=["fcm"])

@router.post("/register-fcm-token")
async def register_fcm_token(
    payload: dict = Body(...),
    current_user: dict = Depends(UserPermission(["user", "admin"])),
    lang: str = Query("en")
):
    return await register_fcm_token_controller(
        payload=payload,
        current_user=current_user,
        lang=lang
    )

@router.get("/tokens")
async def get_fcm_tokens(
    pagination: StandardResultsSetPagination = Depends(pagination_params),
    current_user: dict = Depends(UserPermission(["user", "admin"])),
    lang: str = Query("en")
):
    return await get_fcm_tokens_controller(
        current_user=current_user,
        pagination=pagination,
        lang=lang
    )


@router.patch("/deactivate")
async def deactivate_fcm_token(
    payload: dict = Body(...),
    current_user: dict = Depends(UserPermission(["user", "admin"])),
    lang: str = Query("en")
):
    return await deactivate_fcm_token_controller(payload, current_user, lang)


@router.delete("/delete")
async def delete_fcm_token(
    payload: dict = Body(...),
    current_user: dict = Depends(UserPermission(["user", "admin"])),
    lang: str = Query("en")
):
    return await delete_fcm_token_controller(payload, current_user, lang)