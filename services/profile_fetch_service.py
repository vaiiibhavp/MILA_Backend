#services/profile_fetch_service.py

from bson import ObjectId
from config.models.user_models import get_user_details
from config.models.onboarding_model import get_onboarding_details

async def fetch_basic_profile_data(user_id: str):
    user = await get_user_details(
        {"_id": ObjectId(user_id)},
        fields=[
            "_id",
            "username",
            "email",
            "is_verified",
            "wallet_address",
            "two_factor_enabled"
        ]
    )

    onboarding = await get_onboarding_details(
        {"user_id": user_id},
        fields=[
            "bio",
            "birthdate",
            "gender",
            "country",
            "interested_in",
            "sexual_orientation",
            "marital_status",
            "passions",
            "sexual_preferences",
            "preferred_country"
        ]
    )

    return user, onboarding
