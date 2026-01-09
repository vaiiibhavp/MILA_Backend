from fastapi import APIRouter, Depends, Query
from api.controller.contest_controller import *
from core.utils.permissions import UserPermission
from core.utils.pagination import pagination_params, StandardResultsSetPagination

router = APIRouter(prefix="", tags=["contest"])

@router.get("/active-past-contests")
async def get_contests(
    contest_type: str = Query(..., enum=["active", "past"]),
    pagination: StandardResultsSetPagination = Depends(pagination_params),
    current_user: dict = Depends(UserPermission(["user"])),
    lang: str = Query("en")
):
    """
    Fetch contests for logged-in user

    Query params:
    - contest_type=active
    - contest_type=past
    - page, page_size
    """
    return await get_contests_controller(
        current_user=current_user,
        contest_type=contest_type,
        pagination=pagination,
        lang=lang
    )

