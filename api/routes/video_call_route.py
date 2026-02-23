from fastapi import APIRouter , Depends
from schemas.video_call_schema import StartVideoCallRequest ,EndVideoCallRequest ,VideoCallTickRequest
from core.auth import get_current_user
from api.controller.video_call_controller import start_video_call ,end_video_call ,video_call_tick

router = APIRouter()

# Route to start video call session
@router.post("/user/video-call/start", response_model=dict)
async def start_video_call_route(
    request: StartVideoCallRequest,
    current_user: dict = Depends(get_current_user),
    lang: str = "en"
):
    user_id = str(current_user["_id"])

    return await start_video_call(
        user_id=user_id,
        receiver_user_id=request.receiver_user_id,
        lang=lang
    )


@router.post("/user/video-call/end", response_model=dict)
async def end_video_call_route(
    request: EndVideoCallRequest,
    current_user: dict = Depends(get_current_user),
    lang: str = "en"
):
    user_id = str(current_user["_id"])

    return await end_video_call(
        user_id=user_id,
        call_id=request.call_id,
        total_call_seconds=request.total_call_seconds,
        lang=lang
    )

@router.post("/user/video-call/tick", response_model=dict)
async def video_call_tick_route(
    request: VideoCallTickRequest,
    current_user: dict = Depends(get_current_user),
    lang: str = "en"
):
    user_id = str(current_user["_id"])

    return await video_call_tick(
        user_id=user_id,
        call_id=request.call_id,
        elapsed_seconds=request.elapsed_seconds,
        lang=lang
    )
