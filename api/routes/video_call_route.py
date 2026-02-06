from fastapi import APIRouter
from api.controller.video_call_controller import get_user_details_controller
router = APIRouter()

@router.get("/user/{user_id}")
async def get_user_details(
    user_id: str,
    lang: str = "en"
):
    return await get_user_details_controller(user_id, lang)

