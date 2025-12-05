from fastapi import HTTPException
from config.db_config import user_collection
from core.utils.auth_utils import generate_login_tokens
from core.utils.response_mixin import CustomResponseMixin
from datetime import datetime

response = CustomResponseMixin()


async def google_login_controller(payload):
    email = payload.email
    name = payload.name
    google_id = payload.google_id

    # 1. Check if user already exists
    user = await user_collection.find_one({"email": email})
    if not user:
        # 2. Create new Google user
        new_user = {
            "username": name or email.split("@")[0],
            "email": email,
            "password": None,
            "membership_type": "free",
            "is_verified": False,
            "created_at": datetime.utcnow(),
            "google_login_id": google_id,
        }

        result = await user_collection.insert_one(new_user)
        new_user["_id"] = result.inserted_id
        user = new_user

    # 3. Generate tokens
    access_token, refresh_token = generate_login_tokens(user)

    return response.success_message(
        "Login successful",
        data=[{
            "access_token": access_token,
            "refresh_token": refresh_token
        }]
    )
