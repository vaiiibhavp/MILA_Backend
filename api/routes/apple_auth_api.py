from api.controller.apple_login_controller import apple_login_controller
from fastapi import APIRouter
from schemas.user_schemas import AppleLoginRequest
from schemas.response_schema import Response

router = APIRouter()

@router.post("/apple-login", response_model=Response)
async def apple_login(payload: AppleLoginRequest):
    """
    Apple login API
    """
    return await apple_login_controller(payload)
