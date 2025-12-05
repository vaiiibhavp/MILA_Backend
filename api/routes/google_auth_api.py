from api.controller.google_login_controller import google_login_controller
from fastapi import APIRouter
from schemas.user_schemas import GoogleLoginRequest
from schemas.response_schema import Response

router = APIRouter()

@router.post("/google-login", response_model=Response)
async def google_login(payload: GoogleLoginRequest):
    """
    Google login API
    """
    return await google_login_controller(payload)
