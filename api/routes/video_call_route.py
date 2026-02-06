from fastapi import APIRouter , Depends
from api.controller.video_call_controller import get_user_details_controller
from core.auth import get_current_user

router = APIRouter()

@router.get("/user-info")
async def get_user_details(
    current_user: dict = Depends(get_current_user),
    lang: str = "en"
):
    return await get_user_details_controller(current_user, lang)

