from fastapi import APIRouter,Depends,Request,Query
from config.models.user_models import PyObjectId, UserCreate
from core.utils.response_mixin import CustomResponseMixin
from core.utils.auth_utils import *
from typing import List, Optional
from schemas.user_schemas import *
from api.controller.user_auth import *
from schemas.response_schema import Response
from core.utils.permissions import UserPermission, AdminPermission
from core.utils.pagination import StandardResultsSetPagination, pagination_params
import time
from fastapi import Body


supported_langs = ["en", "fr"]


# Initializing the router instance
router = APIRouter()

class AuthViews:
    """
    Authentication-related endpoints for user login, registration,
    token management, and password operations.
    """

    #api for refresh-token an admin and user
    @router.post("/refresh-token", response_model=Response)
    async def refresh_token_endpoint(request_body: RefreshTokenRequest, request: Request, lang: str = Query(None)):
        """
        Refresh JWT token endpoint.
        """
        lang = lang if lang in supported_langs else "en"
        return await refresh_token(request_body, lang)

    #api for logout
    @router.post("/logout", response_model=Response)
    async def logout(request: LogoutRequest, lang: str = Query(None)):
        """
        Logout endpoint to invalidate user session.
        """
        lang = lang if lang in supported_langs else "en"
        return await logout(request, lang)

# api for getting user-profile-details
@router.get("/user-profile-details", response_model=Response)
async def user_profile_route(request: Request, current_user: dict = Depends(UserPermission(allowed_roles=["user","admin"])), lang: str = Query(None)):
    """
    Get User Profile Details:-
    Retrieves the profile details of the current user.
    """

    lang = lang if lang in supported_langs else "en"
    return await get_user_profile_details(request,current_user,lang)

@router.post("/register", response_model=Response)
async def signup_user(payload: Signup, lang: str = "en"):
    return await signup_controller(payload, lang)

@router.post("/verify-email")
async def verify_otp(payload: VerifyOTP, lang: str = "en"):
    return await verify_signup_otp_controller(payload, lang)

@router.post("/resend-otp")
async def resend_otp(payload: ResendOTP, lang: str = "en"):
    return await resend_otp_controller(payload, lang)

@router.post("/login", response_model=Response)
async def login_user(payload: LoginRequest, lang: str = "en"):
    """
    User login API (with optional 2FA OTP)
    """
    return await login_controller(payload, lang)

@router.post("/login/verify-otp", response_model=Response)
async def verify_login_otp(payload: VerifyLoginOtpRequest, lang: str = "en"):
    """
    Verify OTP for login (2FA)
    """
    return await verify_login_otp_controller(payload, lang)

@router.post("/login/resend-otp", response_model=Response)
async def resend_login_otp(payload: ResendOtpRequest, lang: str = "en"):
    """
    Resend Login OTP
    """
    return await resend_login_otp_controller(payload, lang)

@router.post("/forgot-password", response_model=Response)
async def send_reset_password_otp(payload: ForgotPasswordRequest, lang: str = "en"):
    return await send_reset_password_otp_controller(payload, lang)

@router.post("/verify-reset-otp", response_model=Response)
async def verify_reset_password_otp(payload: VerifyResetOtpRequest, lang: str = "en"):
    return await verify_reset_password_otp_controller(payload, lang)

@router.post("/password-reset", response_model=Response)
async def reset_password(payload: ResetPasswordRequest, lang: str = "en"):
    return await reset_password_controller(payload, lang)

@router.get("/{user_id}", response_model=Response)
async def get_user_by_id(
    user_id: str,
    current_user: dict = Depends(UserPermission(allowed_roles=["admin", "user"])),
    lang: str = "en"
):
    return await get_user_by_id_controller(user_id, lang)

@router.get("", response_model=Response)
async def get_all_users(
    pagination: StandardResultsSetPagination = Depends(pagination_params),
    current_user: dict = Depends(UserPermission(allowed_roles=["admin", "user"])),
    lang: str = "en"
):
    """
    Get all users (Admin only) with standard pagination
    """
    return await get_all_users_controller(pagination, lang)