import asyncio
from datetime import datetime, timedelta
import uuid
from api.controller.files_controller import *
from core.utils.auth_utils import *

from config.models.user_models import store_token
from core.utils.helper import serialize_datetime_fields,convert_objectid_to_str
from schemas.admin_schema import *
from tasks import send_password_reset_email_task
from config.db_config import *
from services.translation import translate_message
from core.utils.auth_utils import generate_verification_code
from core.utils.helper import validate_pwd , validate_new_pwd , validate_confirm_new_password



#controller for login the admin_login 
async def login_controller(request: AdminLogin, lang: str = "en"):
    """
    Authenticate an admin user using email and password, generate tokens, 
    and return user data including profile photo URL.
    """
    try:
        # Step 1: Find user by email
        admin = await admin_collection.find_one({"email": request.email})
        if not admin:
            return response.error_message(
                translate_message("INVALID_CREDENTIALS", lang=lang),
                data={}, status_code=400
            )
        
        # Step 2: Check role
        if admin.get("role") != "admin":
            return response.error_message(
                translate_message("INVALID_ADMIN_CREDENTIALS", lang=lang),
                data={}, status_code=400
            )
        
        # Step 3: Validate password
        if not verify_password(request.password, admin["password"]):
            return response.error_message(
                translate_message("INVALID_CREDENTIALS", lang=lang),
                data={}, status_code=400
            )

        # Step 4: Generate access & refresh tokens
        token_payload = {
            "sub": admin["email"],
            "user_id": str(admin["_id"])
        }
        access_token = create_access_token(token_payload)
        refresh_token = create_refresh_token(token_payload)


        access_token_expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        refresh_token_expire = datetime.utcnow() + timedelta(minutes=REFRESH_TOKEN_EXPIRE_MINUTES)

        # Step 5: Store tokens in DB
        values = store_token(
            user_id=str(admin["_id"]),
            email=admin["email"],
            access_token=access_token,
            refresh_token=refresh_token,
            access_token_expire=access_token_expire,
            refresh_token_expire=refresh_token_expire
        )   


        # Step 6: Prepare user data for response
        user_data = admin.copy()
        user_data.pop("password", None)
        user_data["user_id"] = str(user_data.pop("_id"))

        # Convert ObjectId fields in user_data to string
        user_data = convert_objectid_to_str(user_data)

        # Step 7: Get profile photo URL
        # profile_url = await get_profile_photo_url(current_user=admin)
        # user_data["profile_url"] = profile_url if profile_url else None


        # Step 8: Prepare response
        response_data = {
            "token_type": "bearer",
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user_data": user_data,
        }

        # Serialize datetime fields in response
        response_data = serialize_datetime_fields(response_data)

        return response.success_message(
            translate_message("LOGIN_SUCCESS", lang=lang),
            data=response_data
        )

    except Exception as e:
        return response.raise_exception(
            translate_message("FAILED_LOGIN", lang=lang),
            data=str(e),
            status_code=500
        )

#controller for refresh_token
async def refresh_token(request: RefreshTokenRequest, lang: str = "en"):
    """
    Refresh the access token using a valid refresh token.
    """
    # Check if the token exists in the collection
    result  = await token_collection.find_one({"refresh_token": request.refresh_token})
    existing_token = await result if isinstance(result, asyncio.Future) else result
    if not existing_token:
        raise response.raise_exception(message=translate_message("Refresh token not found.", lang), data={}, status_code=400)

    # Check if the token is blacklisted
    if existing_token.get("is_blacklisted", True):
        raise response.raise_exception(
            message=translate_message("The refresh token is blacklisted.", lang), data={}, status_code=401
        )

    # Verify token and generate new access token
    token_data = verify_refresh_token(request.refresh_token)

    await token_collection.update_one(
        {"refresh_token": request.refresh_token},
        {"$set": {"is_blacklisted": True}}
    )
    user = await admin_collection.find_one({"email": token_data["sub"]})
    if not user:
        return response.raise_exception(
            message="User not found.",
            data={},
            status_code=404
        )

    new_access_token, new_refresh_token = generate_login_tokens(user)

    return response.success_message(
        "Token refreshed successfully",
        data={
            "access_token": new_access_token,
            "refresh_token": new_refresh_token
        }
    )

#controller for update_password_controller
async def update_password_controller(
        request: ResetPasswordRequest, 
        email: str,
        lang: str = "en"
    ):
    """
    Update a user's password after verifying the current password.
    """
    # Step 1: Find the user by email
    user = await user_collection.find_one({"email": email})

    if not user:
        raise response.raise_exception(status_code=404, message=translate_message("User not found", lang))

    # Step 2: Verify current password
    if not pwd_context.verify(request.current_password, user["password"]):
        raise response.raise_exception(message=translate_message("Current password is incorrect", lang),status_code=400)

    # Step 3: Validate password strength
    validate_pwd(request.new_password)

    # Step 4: Validate new password
    if request.new_password != request.confirm_new_password:
        raise response.raise_exception(message=translate_message("New password and confirm password do not match", lang),status_code=400)

    # Step 5: Check if the new password is the same as the current password
    if request.new_password == request.current_password:
        raise response.raise_exception(message=translate_message("New password cannot be the same as the current password", lang), status_code=400)

    # Step 6: Hash and update the new password
    hashed_password = pwd_context.hash(request.new_password)

    await user_collection.update_one(
        {"_id": user["_id"]},
        {"$set": {"password": hashed_password, "updated_at": datetime.utcnow()}}
    )

    return response.success_message(translate_message("Password reset successful", lang), data={})

# helper function -Dependency to extract user email from token
def get_current_user_email(request: Request):
    """
    Dependency to extract the email of the current user from the Authorization header in /change-password api.
    """
    # Extract token from Authorization header
    authorization = request.headers.get("Authorization")
    if not authorization or not authorization.startswith("Bearer "):
        raise response.raise_exception( message="Invalid or missing token",status_code=401)
    token = authorization.split(" ")[1]
    try:
        # Decode the token
        payload = jwt.decode(token, SECRET_ACCESS_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise response.raise_exception(message="Invalid token: email not found",data={},status_code=401)
        return email
    except JWTError:
        raise response.raise_exception( message="Invalid or expired token",status_code=401)

#controller for verify_forgot_pwd_otp
async def verify_forgot_pwd_otp_admin(otp: ForgotPasswordOtpVerify, lang: str = "en"):
    """
    Verify Forgot Password OTP (Forgot Password Flow)
    """

    # ✅ Step 1: Validate input
    if not otp.email or not otp.otp:
        raise response.raise_exception(
            message=translate_message("Email or OTP cannot be empty", lang),
            status_code=400
        )

    # ✅ Step 2: Validate email existence (IMPORTANT FIX)
    admin = await admin_collection.find_one(
        {"email": otp.email},
        {"_id": 1}
    )

    if not admin:
        raise response.raise_exception(
            message=translate_message("EMAIL_NOT_FOUND", lang),
            status_code=404
        )

    # ✅ Step 3: Fetch stored OTP
    stored_code = await get_from_redis(f"password_reset:{otp.email}")

    if not stored_code:
        raise response.raise_exception(
            message=translate_message("OTP_EXPIRED_OR_INVALID", lang),
            status_code=400
        )

    if stored_code != otp.otp:
        raise response.raise_exception(
            message=translate_message("INVALID_OTP", lang),
            status_code=400
        )

    # ✅ Step 4: Generate reset token
    temp_token = str(uuid.uuid4())

    redis_key = f"reset_token:{temp_token}"


    await store_in_redis(
        key=redis_key,
        value=otp.email,
        ttl=500  # 5 minutes
    )

    # (Optional cleanup) delete used OTP so it can't be reused
    await delete_from_redis(f"password_reset:{otp.email}")

    #  Step 4: Return reset_token to frontend
    return response.success_message(
        translate_message("OTP verified successfully", lang),
        data={"reset_token": temp_token}
    )


#controller for change_password
async def change_password_controller(request: ForgotPasswordRequest, lang: str = "en"):

    reset_token = request.reset_token

    # TOKEN ➝ EMAIL lookup
    redis_key = f"reset_token:{reset_token}"
    email = await get_from_redis(redis_key)


    if not email:
        raise response.raise_exception(
            message=translate_message("Invalid or expired reset token", lang),
            status_code=400
        )

    admin = await admin_collection.find_one({"email": email})
    if not admin:
        raise response.raise_exception(
            message=translate_message("User not found", lang),
            status_code=404
        )

    #  Validate passwords
    validate_new_pwd(request.new_password)
    validate_confirm_new_password(request.confirm_new_password)

    if request.new_password != request.confirm_new_password:
        raise response.raise_exception(
            message=translate_message("New password and confirm password do not match", lang),
            status_code=400
        )

    hashed_password = pwd_context.hash(request.new_password)

    await admin_collection.update_one(
        {"_id": admin["_id"]},
        {"$set": {"password": hashed_password, "updated_at": datetime.utcnow()}}
    )

    #  Clean Redis
    await delete_from_redis(f"reset_token:{reset_token}")
    await delete_from_redis(f"password_reset:{email}")

    return response.success_message(
        translate_message("Password reset successful", lang),
        data={}
    )

#controller for request_password_reset
async def request_password_reset_admin(request: RequestResetPassword, lang: str = "en"):
        """
        Request Password Reset (Forgot Password Flow):-
        Sends a password reset request for the user based on the provided email.
        If the user exists, an OTP or reset link will be sent to their registered email.
        """

        #  Validate email is not empty
        if not request.email or not request.email.strip():
            return response.error_message(
                translate_message("Email is required", lang),
                data={}, 
                status_code=400
            )
        
        email = request.email.strip()

        # Step 1: Check if the user exists
        admin = await admin_collection.find_one({"email": email})

        if not admin:
            return response.error_message(
                translate_message("Admin not found with this email", lang),
                data={}, 
                status_code=404
            )

        # Step 2: Generate the reset code
        reset_code = generate_verification_code()

        # Step 3: Store the reset code in Redis with an expiration time of 15 minutes
        try:
            await store_in_redis(f"password_reset:{email}", reset_code, ttl=15 * 60)  # 15 minutes TTL
        except Exception as e:
            print(f"Error storing reset code in Redis: {e}")
            return response.error_message(
                translate_message("Failed to process password reset request. Please try again.", lang),
                data={}, 
                status_code=500
            )

        # Step 4: Send the reset code to the user's email
        try:
            email_subject = translate_message("Password Reset Request", lang)
            email_body = translate_message(
                "Your password reset code is: {reset_code}. It will expire in 15 minutes.",
                lang=lang,
                reset_code=reset_code
            )

            # Send email asynchronously and handle failures gracefully
            send_password_reset_email_task.delay(admin['email'], email_subject, email_body)
            
            # Step 5: Return success message
            return response.success_message(
                translate_message("Password reset code sent to email", lang), 
                data={"email": email},
                status_code=200
            )
            
        except Exception as e:
            print(f"Error sending password reset email: {e}")
            # Even if email fails, we still return success to prevent user enumeration
            # The reset code is still stored in Redis
            return response.success_message(
                translate_message("Password reset code sent to email", lang), 
                data={"email": email},
                status_code=200
            )

#controller for logout
async def logout_admin(request: LogoutRequest, lang: str = "en"):
    """
    Logout a user by blacklisting their refresh token.
    """

    try:
        # Verify the token
        token_data = verify_token(request.refresh_token)
    except Exception as e:
        raise response.raise_exception(message=translate_message("Invalid refresh token.", lang), data={}, status_code=400)

    # Find the token in the database
    existing_token = await token_collection.find_one({"refresh_token": request.refresh_token})

    if not existing_token:
        raise response.raise_exception(message=translate_message("Refresh token not found.", lang), data={}, status_code=400)

    # Step 3: Check if the token is already blacklisted
    if existing_token.get("is_blacklisted", True):
        raise response.raise_exception(message=translate_message("This token is already blacklisted.", lang), data={}, status_code=400)

    login_user = existing_token.get("user_id", "")
    if not login_user:
        raise response.raise_exception(message=translate_message("User ID not found.", lang),  data={}, status_code=400)

    # Blacklist the token
    await token_collection.update_one(
        {"refresh_token": request.refresh_token},
        {"$set": {"is_blacklisted": True}}
    )

    return response.success_message(translate_message("Logout successful.", lang), data={})

