from fastapi import APIRouter, Depends
from schemas.block_report_schema import BlockUserRequest , ReportUserRequest
from api.controller.block_report_controller import block_user_controller , report_user_controller , get_blocked_users_list,get_reported_users_list
from core.auth import get_current_user

router = APIRouter(
    prefix="/user",
)

@router.post("/block-report")
async def block_or_report_user(
    payload: BlockUserRequest,
    current_user: dict = Depends(get_current_user),
    lang: str = "en"
):
    return await block_user_controller(
        blocker_id=str(current_user["_id"]),
        blocked_id=payload.blocked_user_id,
        lang=lang
    )

@router.post("/report")
async def report_user(
    payload: ReportUserRequest,
    current_user: dict = Depends(get_current_user),
    lang: str = "en"
):
    return await report_user_controller(
        reporter_id=str(current_user["_id"]),
        reported_id=payload.reported_user_id,
        reason=payload.reason,
        lang=lang
    )

@router.get("/blocked-users")
async def get_blocked_users_api(
    current_user: dict = Depends(get_current_user),
    lang: str = "en"
):
    return await get_blocked_users_list(
        user_id=str(current_user["_id"]),
        lang=lang
    )

@router.get("/reported-users")
async def get_reported_users_api(
    current_user: dict = Depends(get_current_user),
    lang: str = "en"
):
    return await get_reported_users_list(
        user_id=str(current_user["_id"]),
        lang=lang
    )
