from fastapi import APIRouter, Depends, Query, Path, Form
from api.controller.contest_controller import *
from core.utils.permissions import UserPermission
from core.utils.pagination import pagination_params, StandardResultsSetPagination
from schemas.response_schema import Response

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


@router.get("/contest_details/{contest_id}")
async def get_contest_details(
    contest_id: str = Path(..., description="Contest ID"),
    current_user: dict = Depends(UserPermission(["user"])),
    lang: str = Query("en")
):
    """
    Fetch contest details for logged-in user

    Path params:
    - contest_id

    Response includes:
    - contest status & visibility
    - banner, description, prize pool
    - important dates
    - participants preview
    - current standings (if voting started)
    - CTA state (participate / vote)
    """
    return await get_contest_details_controller(
        contest_id=contest_id,
        current_user=current_user,
        lang=lang
    )

@router.get(
    "/{contest_id}/view_participants",
    response_model=Response
)
async def get_contest_participants(
    contest_id: str,
    pagination: StandardResultsSetPagination = Depends(pagination_params),
    current_user: dict = Depends(UserPermission(["user"])),
    lang: str = Query("en")
):
    return await get_contest_participants_controller(
        contest_id=contest_id,
        current_user=current_user,
        pagination=pagination,
        lang=lang
    )

@router.post("/{contest_id}/participate", response_model=Response)
async def participate_in_contest(
    contest_id: str,
    contest_history_id: str = Form(...),
    images: List[UploadFile] = File(...),
    current_user: dict = Depends(UserPermission(["user"])),
    lang: str = Query("en")
):
    return await participate_in_contest_controller(
        contest_id,
        contest_history_id,
        images,
        current_user,
        lang
    )

@router.get("/leaderboard/{contest_id}")
async def get_full_leaderboard(
    contest_id: str,
    pagination: StandardResultsSetPagination = Depends(pagination_params),
    current_user: dict = Depends(UserPermission(["user"])),
    lang: str = Query("en")
):
    return await get_full_leaderboard_controller(
        contest_id=contest_id,
        pagination=pagination,
        lang=lang
    )

@router.post("/{contest_id}/vote")
async def cast_vote(
    contest_id: str,
    payload: VoteRequestSchema,
    current_user: dict = Depends(UserPermission(["user"])),
    lang: str = Query("en")
):
    return await cast_vote_controller(
        contest_id=contest_id,
        participant_user_id=payload.participant_user_id,
        current_user=current_user,
        lang=lang
    )

