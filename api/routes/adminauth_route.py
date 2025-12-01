from fastapi import Query, Request , APIRouter , Depends
from core.utils.auth_utils import *
from schemas.admin_schema import AdminLogin , RefreshTokenRequest  , LogoutRequest ,RequestResetPassword ,ForgotPasswordRequest,ForgotPasswordOtpVerify
from schemas.response_schema import Response
from api.controller.adminAuth import admin_login_verfication , refresh_token , verify_forgot_pwd_otp_admin , change_password_admin ,request_password_reset_admin , logout_admin
router = APIRouter()

supported_langs = ["en", "fr"]

# Login fot Admin
@router.post("/admin/login", response_model=dict)
async def admin_login(request: AdminLogin, lang: str = Query(None)):
    """
    Admin login endpoint. JWT token
    """
    lang = lang if lang in supported_langs else "en"
    return await admin_login_verfication(request, lang)


# api for request-password-reset
@router.post("/request-password-reset")
async def request_password_reset(request: RequestResetPassword, lang: str = Query(None)):
    """
    Request Password Reset (Forgot Password Flow):-
    Sends a password reset request for the admin based on the provided email.
    If the admin exists, an OTP or reset link will be sent to their registered email.
    """
    lang = lang if lang in supported_langs else "en"
    return await request_password_reset_admin(request, lang)


# Api for forgot password otpverification
@router.post("/forgot_pwd_otp_ver")
async def verify_forgot_pwd_otp(otp :ForgotPasswordOtpVerify, lang: str = Query(None)):
    """
    Verify Forgot Password OTP (Forgot Password Flow):-
    Verifies the OTP sent to the user during the forgot password process.
    """
    lang = lang if lang in supported_langs else "en"
    return await verify_forgot_pwd_otp_admin(otp, lang)

# api for forgot-password
@router.post("/forgot-password")
async def change_password(request: ForgotPasswordRequest, lang: str = Query(None)):
    """
    Change Password (Forgot Password Flow):-
    Allows the user to set a new password after successful OTP verification.
    """
    lang = lang if lang in supported_langs else "en"
    return await change_password_admin(request, lang)


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
    return await logout_admin(request, lang)

