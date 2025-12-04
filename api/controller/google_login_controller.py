from fastapi import HTTPException
from core.utils.google_auth import decode_google_id_token
from config.db_config import user_collection
from core.utils.auth_utils import generate_login_tokens
from core.utils.response_mixin import CustomResponseMixin
from datetime import datetime

response = CustomResponseMixin()


async def google_login_controller(id_token: str):
    # 1. Verify Google token
    google_info = decode_google_id_token(id_token)

    email = google_info["email"]

    # 2. Check if user exists
    user = await user_collection.find_one({"email": email})

    if not user:
        # 3. Auto-create account for new Google users
        new_user = {
            "username": google_info.get("name") or email.split("@")[0],
            "email": email,
            "password": None,
            "membership_type": "free",
            "is_verified": False,
            "created_at": datetime.utcnow(),
            "google_login_id": google_info.get("google_id")
        }

        result = await user_collection.insert_one(new_user)
        new_user["_id"] = result.inserted_id
        user = new_user

    # 4. Generate tokens
    access_token, refresh_token = generate_login_tokens(user)

    return response.success_message(
        "Login successful",
        data={
            "access_token": access_token,
            "refresh_token": refresh_token
        }
    )
