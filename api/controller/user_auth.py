#controller/user_auth.py

import asyncio
from datetime import datetime
import math
import json
from api.controller.files_controller import *
from bson import ObjectId
from core.utils.auth_utils import *
from fastapi import Request
from jose import jwt,JWTError
from core.utils.helper import serialize_datetime_fields,convert_objectid_to_str
from schemas.user_schemas import *
from config.db_config import *
from core.utils.redis_helper import redis_client 
from core.utils.pagination import StandardResultsSetPagination   
from services.translation import translate_message
from core.templates.email_templates import *
from core.utils.core_enums import *
from bson import ObjectId
from config.models.user_models import *
from config.models.onboarding_model import *
from core.utils.helper import *
from bson.errors import InvalidId

ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES"))
REFRESH_TOKEN_EXPIRE_MINUTES =int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES"))

response = CustomResponseMixin()

#controller for refresh_token
async def refresh_token(request: RefreshTokenRequest, lang: str = "en"):
    """
    Refresh the access token using a valid refresh token.
    """
    # Check if the token exists in the collection
    result  = await token_collection.find_one({"refresh_token": request.refresh_token})
    existing_token = await result if isinstance(result, asyncio.Future) else result
    if not existing_token:
        raise response.raise_exception(message=translate_message("REFRESH_TOKEN_NOT_FOUND", lang), data={}, status_code=400)

    # Check if the token is blacklisted
    if existing_token.get("is_blacklisted", True):
        raise response.raise_exception(
            message=translate_message("REFRESH_TOKEN_BLACKLISTED", lang), data={}, status_code=401
        )

    # Verify token and generate new access token
    token_data = verify_refresh_token(request.refresh_token)

    await token_collection.update_one(
        {"refresh_token": request.refresh_token},
        {"$set": {"is_blacklisted": True}}
    )
    user = await user_collection.find_one({"email": token_data["sub"]})
    if not user:
        return response.raise_exception(
            message="USER_NOT_FOUND",
            data={},
            status_code=404
        )

    new_access_token, new_refresh_token = generate_login_tokens(user)

    return response.success_message(
        "TOKEN_REFRESHED_SUCCESSFULLY",
        data=[{
            "access_token": new_access_token,
            "refresh_token": new_refresh_token
        }]
    )

#controller for logout
async def logout(request: LogoutRequest, lang: str = "en"):
    """
    Logout a user by blacklisting their refresh token.
    """
    try:
        # Verify the token
        token_data = verify_token(request.refresh_token)
    except Exception as e:
        raise response.raise_exception(message=translate_message("INVALID_REFRESH_TOKEN", lang), data={}, status_code=400)

    # Find the token in the database
    existing_token = await token_collection.find_one({"refresh_token": request.refresh_token})

    if not existing_token:
        raise response.raise_exception(message=translate_message("REFRESH_TOKEN_NOT_FOUND", lang), data={}, status_code=400)

    user_id = existing_token.get("user_id")
    if not user_id:
        raise response.raise_exception(
            message=translate_message("USER_ID_NOT_FOUND", lang),
            data={},
            status_code=400
        )

    # Blacklist the token
    await token_collection.update_many(
        {"user_id": user_id, "is_blacklisted": False},
        {"$set": {"is_blacklisted": True, "updated_at": datetime.utcnow()}}
    )

    # Update user login status
    await user_collection.update_one(
        {"_id": ObjectId(user_id)},
        {
            "$set": {
                "login_status": LoginStatus.INACTIVE,
                "last_logout_at": datetime.utcnow()
            }
        }
    )
    return response.success_message(translate_message("LOGOUT_SUCCESSFUL", lang), data={})


# helper function -Dependency to extract user email from token
def get_current_user_email(request: Request):
    """
    Dependency to extract the email of the current user from the Authorization header in /change-password api.
    """
    # Extract token from Authorization header
    authorization = request.headers.get("Authorization")
    if not authorization or not authorization.startswith("Bearer "):
        raise response.raise_exception( message="INVALID_OR_MISSING_TOKEN", data=[], status_code=401)
    token = authorization.split(" ")[1]
    try:
        # Decode the token
        payload = jwt.decode(token, SECRET_ACCESS_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise response.raise_exception(message="INVALID_TOKEN_EMAIL_NOT_FOUND",data=[],status_code=401)
        return email
    except JWTError:
        raise response.raise_exception( message="INVALID_OR_EXPIRED_TOKEN",status_code=401)



#controller for get_user_profile_details 
async def get_user_profile_details(request: Request, current_user: dict, lang: str = "en"):
    """
    Get complete user profile info including profile photo URL (S3 presigned URL or LOCAL path).
    Uses Files model and helper to generate fetchable URL.
    """
    try:
        user_id = str(current_user["_id"])

        # Fetch all user fields
        user_data = await user_collection.find_one({"_id": ObjectId(user_id)})

        if not user_data:
            return response.success_message(
                translate_message("USER_NOT_FOUND", lang=lang),
                data=None
            )
        # Remove sensitive info
        user_data.pop("password", None)

        # Get profile photo URL
        profile_url = await get_profile_photo_url(current_user=user_data)
        user_data["profile_photo_url"] = profile_url if profile_url else None


        user_data = serialize_datetime_fields(user_data)
        # Convert ObjectId to str for all relevant fields
        user_data = convert_objectid_to_str(user_data)

        return response.success_message(
            translate_message("USER_PROFILE_FETCHED", lang=lang),
            data=user_data
        )

    except Exception as e:
        return response.raise_exception(
            translate_message("ERROR_FETCHING_PROFILE", lang=lang),
            data=str(e),
            status_code=500
        )



async def signup_controller(payload: Signup, lang):

    deleted_account = await deleted_account_collection.find_one({
        "email": payload.email
    })

    if deleted_account:
        return response.error_message(
            translate_message("EMAIL_CANNOT_BE_REUSED", lang=lang),
            status_code=400
        )
    # Step 1: Check if email already exists in DB
    existing = await user_collection.find_one({"email": payload.email})
    if existing:
        return response.error_message(translate_message("EMAIL_ALREADY_REGISTERED", lang=lang), status_code=400)

    existing_username = await user_collection.find_one({"username": payload.username})
    if existing_username:
        return response.error_message(
            translate_message("USERNAME_ALREADY_TAKEN", lang=lang),
            status_code=400
        )
    
    # Step 2: Generate OTP
    otp = generate_verification_code()
    # Step 3: Save signup data temporarily in Redis
    signup_data = {
        "username": payload.username,
        "email": payload.email,
        "password": get_hashed_password(payload.password)
    }

    await redis_client.setex(
        f"signup:{payload.email}:data",
        600,
        json.dumps(signup_data)
    )

    # Store OTP for 5 minutes
    await redis_client.setex(
        f"signup:{payload.email}:otp",
        60,
        otp
    )

    # Step 4: Send verification email
    subject, body = signup_verification_template(payload.username, otp, lang)
    is_html = True
    await send_email(payload.email, subject, body, is_html)

    return response.success_message(translate_message("OTP_SENT_SUCCESSFULLY", lang=lang), 
                                    data=[], status_code=200)

async def verify_signup_otp_controller(payload, lang):
    email = payload.email
    otp = payload.otp

    # Step 1: Get stored OTP
    stored_otp = await redis_client.get(f"signup:{email}:otp")
    if not stored_otp:
        return response.error_message(translate_message("OTP_EXPIRED_OR_NOT_FOUND", lang=lang), status_code=400)

    stored_otp = stored_otp.encode() if isinstance(stored_otp, bytes) else stored_otp

    # Step 2: Compare OTP
    if otp != stored_otp:
        return response.error_message(translate_message("INVALID_OTP", lang=lang), status_code=400)

    # Step 3: Get stored signup data
    temp_data = await redis_client.get(f"signup:{email}:data")
    if not temp_data:
        return response.error_message(translate_message("SIGNUP_SESSION_EXPIRED", lang=lang), status_code=400)

    temp_data = json.loads(temp_data.encode())

    # Step 4: Save verified user into MongoDB
    try:
        result = await user_collection.insert_one({
            "username": temp_data["username"],
            "email": temp_data["email"],
            "password": temp_data["password"],
            "membership_type": "free",
            "is_verified": False,
            "created_at": datetime.utcnow(),
            "updated_at": None,
            "two_factor_enabled": True,
            "language": lang or "en"
        })

        user_id = str(result.inserted_id)

    except Exception as e:
        return response.error_message(translate_message("FAILED_TO_CREATE_USER",lang=lang), data = [{str(e)}], status_code=500)

    # Step 5: Cleanup Redis keys
    await redis_client.delete(f"signup:{email}:otp")
    await redis_client.delete(f"signup:{email}:data")

    # user = await user_collection.find_one({"email": email})
    user = await user_collection.find_one({"_id": ObjectId(user_id)})

    access_token, refresh_token = generate_login_tokens(user)

    # Success Response
    return response.success_message(
        translate_message("EMAIL_VERIFIED_SUCCESSFULLY", lang=lang),
        data=[{
            "user_id": user_id,
            "access_token": access_token,
            "refresh_token": refresh_token            
            }], status_code=200
    )

async def resend_otp_controller(payload, lang):
    email = payload.email

    # Step 1: Check if signup session still exists
    temp_data = await redis_client.get(f"signup:{email}:data")
    if not temp_data:
        return response.error_message(translate_message("SIGNUP_SESSION_EXPIRED_START_AGAIN", lang=lang), status_code=400)

    # Step 2: Generate new OTP
    otp = generate_verification_code()

    await redis_client.setex(
        f"signup:{email}:otp",
        300,  # 5 minutes
        otp
    )

    # Step 3: Send email again
    subject, body = signup_verification_template(
        json.loads(temp_data)["username"],
        otp, lang
    )

    await send_email(email, subject, body, is_html=True)

    return response.success_message(translate_message("NEW_OTP_SENT_TO_EMAIL", lang=lang),
                                    data= [], status_code=200)

async def login_controller(payload: LoginRequest, lang):
    email = payload.email
    password = payload.password

    user = await get_user_details(
        condition={"email": email},
        fields=[
            "_id",
            "email",
            "username",
            "password",
            "two_factor_enabled",
            "membership_type",
            "is_verified",
            "is_deleted"
        ]
    )

    if not user:
        return response.error_message(
            translate_message("USER_NOT_REGISTERED", lang=lang),
            status_code=400
        )
    
    if user.get("is_deleted"):
        return response.error_message(
            translate_message("ACCOUNT_NOT_FOUND", lang=lang),
            status_code=400
        )
      
    # Check user accout is deleted or not
    deleted_account = await deleted_account_collection.find_one({
        "email": payload.email
    })

    if deleted_account:
        return response.error_message(
            translate_message("EMAIL_CANNOT_BE_REUSED", lang=lang),
            status_code=400
        )
    
    # check user is blocked or not
    blocked = await admin_blocked_users_collection.find_one({
        "user_id": str(user["_id"]),
    })

    if blocked:
        return response.error_message(
        translate_message("ACCOUNT_BLOCKED", lang),
        data=[],
        status_code=403
    )

    # check if user account is suspended
    now = datetime.utcnow()

    suspension = await user_suspension_collection.find_one(
        {
            "user_id": str(user["_id"]),
            "suspended_until": {"$exists": True}
        }
    )

    if suspension:
        suspended_until = suspension.get("suspended_until")

        if suspended_until and now <= suspended_until:
            remaining_seconds = (suspended_until - now).total_seconds()
            remaining_days = max(1, math.ceil(remaining_seconds / 86400))

            return response.error_message(
                translate_message("ACCOUNT_SUSPENDED", lang=lang),
                data=[{
                    "suspended_until": suspended_until.isoformat(),
                    "remaining_days": remaining_days
                }],
                status_code=403
            )

    if not verify_password(password, user["password"]):
        return response.error_message(translate_message("INVALID_EMAIL_OR_PASSWORD", lang=lang), status_code=400)

    # Step 3: If 2FA disabled → return tokens immediately
    if not user.get("two_factor_enabled", True):
        return await finalize_login_response(user, lang)

    # 2FA enabled → send OTP
    otp = generate_verification_code()

    await redis_client.setex(f"login:{email}:otp", 60, otp)

    subject, body = login_verification_template(user["username"], otp, lang)
    await send_email(email, subject, body, is_html=True)

    return response.success_message(
        translate_message("LOGIN_OTP_SENT", lang=lang),
        data=[],
        status_code=200    
    )

async def verify_login_otp_controller(payload, lang):
    email = payload.email
    otp = payload.otp

    stored_otp = await redis_client.get(f"login:{email}:otp")
    if not stored_otp:
        return response.error_message(translate_message("LOGIN_OTP_EXPIRED_OR_INVALID", lang=lang), status_code=400)

    stored_otp = stored_otp.decode() if isinstance(stored_otp, bytes) else stored_otp

    if otp != stored_otp:
        return response.error_message(translate_message("INCORRECT_OTP", lang=lang), status_code=400)

    user = await user_collection.find_one({"email": email})

    await redis_client.delete(f"login:{email}:otp")

    return await finalize_login_response(user, lang)

async def resend_login_otp_controller(payload, lang):
    email = payload.email

    # Check user exists
    user = await user_collection.find_one({"email": email})
    if not user:
        return response.error_message(translate_message("USER_NOT_FOUND", lang=lang), status_code=404)

    # Generate new OTP
    otp = generate_verification_code()

    await redis_client.setex(f"login:{email}:otp", 300, otp)

    subject, body = login_verification_template(user["username"], otp, lang)
    await send_email(email, subject, body, is_html=True)

    return response.success_message(
        translate_message("NEW_OTP_SENT_TO_EMAIL", lang=lang),
        data=[],
        status_code=200)

async def send_reset_password_otp_controller(payload: ForgotPasswordRequest, lang):
    email = payload.email

    # Step 1: Check user exists
    user = await user_collection.find_one({"email": email})
    if not user:
        return response.error_message(translate_message("NO_ACCOUNT_FOUND_WITH_EMAIL", lang=lang), status_code=404)

    # Step 2: Generate OTP
    otp = generate_verification_code()

    # Save OTP for 5 minutes
    await redis_client.setex(f"reset:{email}:otp", 300, otp)

    # Email Template
    subject, body = reset_password_otp_template(user["username"], otp, lang)

    await send_email(email, subject, body, is_html=True)

    return response.success_message(translate_message("NEW_OTP_SENT_TO_EMAIL", lang=lang), data=[], status_code=200)

async def verify_reset_password_otp_controller(payload, lang):
    email = payload.email
    otp = payload.otp

    stored_otp = await redis_client.get(f"reset:{email}:otp")

    if not stored_otp:
        return response.error_message(translate_message("OTP_EXPIRED_OR_NOT_FOUND", lang=lang), status_code=400)

    stored_otp = stored_otp.decode() if isinstance(stored_otp, bytes) else stored_otp

    if otp != stored_otp:
        return response.error_message(translate_message("INVALID_OTP", lang=lang), status_code=400)

    # Mark OTP as verified (valid for 10 minutes)
    await redis_client.setex(f"reset:{email}:verified", 600, "true")

    return response.success_message(translate_message("OTP_VERIFIED_SUCCESSFULLY", lang=lang), status_code=200)

async def reset_password_controller(payload, lang):
    email = payload.email
    new_password = payload.new_password

    # Ensure user completed OTP verification
    is_verified = await redis_client.get(f"reset:{email}:verified")
    if not is_verified:
        return response.error_message(translate_message("OTP_VERIFICATION_REQUIRED", lang=lang), status_code=400)

    # Hash new password
    hashed_password = get_hashed_password(new_password)

    # Update DB
    await user_collection.update_one(
        {"email": email},
        {"$set": {"password": hashed_password}}
    )

    # Remove reset session data
    await redis_client.delete(f"reset:{email}:otp")
    await redis_client.delete(f"reset:{email}:verified")

    return response.success_message(translate_message("PASSWORD_RESET_SUCCESSFULLY", lang=lang), status_code=200)

async def resend_forgot_password_otp_controller(payload, lang):
    email = payload.email

    # Step 1: Check user exists
    user = await user_collection.find_one({"email": email})
    if not user:
        return response.error_message(
            translate_message("NO_ACCOUNT_FOUND_WITH_EMAIL", lang=lang),
            status_code=404
        )

    otp_key = f"reset:{email}:otp"
    resend_key = f"reset:{email}:resend"

    # Step 2: Optional rate limit (1 resend per 60 seconds)
    resend_block = await redis_client.get(resend_key)
    if resend_block:
        return response.error_message(
            translate_message("OTP_RESEND_TOO_SOON", lang=lang),
            status_code=429
        )

    # Step 3: Generate new OTP
    otp = generate_verification_code()

    # Step 4: Store OTP again (5 minutes)
    await redis_client.setex(otp_key, 300, otp)

    # Step 5: Set resend lock (60 seconds)
    await redis_client.setex(resend_key, 60, "1")

    # Step 6: Send email
    subject, body = reset_password_otp_template(user["username"], otp, lang)
    await send_email(email, subject, body, is_html=True)

    return response.success_message(
        translate_message("OTP_RESENT_SUCCESSFULLY", lang=lang),
        data=[],
        status_code=200
    )

async def get_user_by_id_controller(user_id: str, lang: str):
    if not ObjectId.is_valid(user_id):
        return response.error_message(translate_message("INVALID_USER_ID", lang=lang), status_code=400)

    user = await get_user_details(
        condition={"_id": ObjectId(user_id), "is_deleted": {"$ne": True}},
        fields=[
            "_id",
            "username",
            "email",
            "role",
            "two_factor_enabled",
            "login_status",
            "last_login_at",
            "created_at",
            "updated_at",
            "membership_type",
            "is_verified",
            "tokens",
        ]
    )

    if not user:
        return response.error_message(translate_message("USER_NOT_FOUND", lang=lang), status_code=404)

    # Normalize ID
    user["id"] = user.pop("_id")

    user = convert_objectid_to_str(user)
    user = serialize_datetime_fields(user)

    return response.success_message(
        translate_message("USER_PROFILE_FETCHED", lang=lang),
        data=[user],
        status_code=200
    )

async def get_all_users_controller(
    pagination: StandardResultsSetPagination,
    lang: str
):
    users, total = await get_users_list(
        condition={"is_deleted": {"$ne": True}},
        fields=[
            "_id",
            "username",
            "email",
            "role",
            "two_factor_enabled",
            "login_status",
            "last_login_at",
            "created_at",
            "updated_at",
            "membership_type",
            "is_verified",
            "tokens",
        ],
        skip=pagination.skip,
        limit=pagination.limit
    )

    for user in users:
        user["id"] = user.pop("_id")

    users = convert_objectid_to_str(users)
    users = serialize_datetime_fields(users)

    return response.success_message(
        translate_message("USER_PROFILE_FETCHED", lang=lang),
        data=[{
            "results": users,
            "page": pagination.page,
            "page_size": pagination.page_size,
            "total": total
        }],
        status_code=200
    )

async def upload_audio_controller(
    audio: UploadFile,
    current_user: dict,
    receiver_id: str,
    lang: str = "en"
):
    user_id = str(current_user["_id"])

    if not audio:
        return response.error_message(
            translate_message("AUDIO_FILE_REQUIRED", lang=lang),
            status_code=400
        )

    try:
        # ---------------- RECEIVER VALIDATION ----------------

        # Validate ObjectId format
        try:
            receiver_object_id = ObjectId(receiver_id)
        except InvalidId:
            return response.error_message(
                translate_message("INVALID_RECEIVER_ID", lang=lang),
                status_code=400
            )

        # Prevent sending audio to self
        if receiver_id == user_id:
            return response.error_message(
                translate_message("CANNOT_SEND_AUDIO_TO_SELF", lang=lang),
                status_code=400
            )

        # Check receiver exists and not deleted
        receiver = await user_collection.find_one(
            {"_id": receiver_object_id, "is_deleted": {"$ne": True}}
        )

        if not receiver:
            return response.error_message(
                translate_message("RECEIVER_NOT_FOUND", lang=lang),
                status_code=404
            )

        # ---------------- FILE READ ----------------

        content = await audio.read()

        if len(content) > settings.CHAT_AUDIO_MAX_LIMIT:
            return response.error_message(
                translate_message("AUDIO_FILE_TOO_LARGE", lang=lang),
                status_code=400
            )

        if not audio.content_type.startswith("audio/"):
            return response.error_message(
                translate_message("INVALID_AUDIO_TYPE", lang=lang),
                status_code=400
            )

        # Save file
        _, storage_key, backend = await save_file(
            file_obj=audio,
            file_name=audio.filename,
            user_id=user_id,
            file_type="audio",
            content=content
        )

        file_doc = Files(
            storage_key=storage_key,
            storage_backend=backend,
            file_type=FileType.AUDIO,
            uploaded_by=user_id
        )

        file_result = await file_collection.insert_one(
            file_doc.dict(by_alias=True)
        )

        audio_doc = {
            "sender_id": user_id,
            "receiver_id": receiver_id,
            "file_id": str(file_result.inserted_id),
            "storage_key": storage_key,
            "file_size": len(content),
            "is_deleted": False,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        audio_result = await chat_audio_collection.insert_one(audio_doc)

        audio_url = await generate_file_url(storage_key, backend)

        return response.success_message(
            translate_message("AUDIO_UPLOAD_SUCCESSFULLY", lang=lang),
            data=[{
                "chat_audio_id": str(audio_result.inserted_id),
                "audio_url": audio_url
            }],
            status_code=200
        )

    except Exception as e:
        return response.error_message(str(e), status_code=500)
