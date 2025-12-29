#services/profile_mapper.py

from core.utils.age_calculation import calculate_age

def build_basic_profile_response(user: dict, onboarding: dict, profile_photo: str):
    birthdate = onboarding.get("birthdate") if onboarding else None
    age = calculate_age(birthdate) if birthdate else None

    return {
        "header": {
            "name": user.get("username"),
            "age": age,
            "is_verified": user.get("is_verified", False),
            "profile_photo": profile_photo
        },

        "personal_info": {
            "bio": onboarding.get("bio") if onboarding else None,
            "email": user.get("email"),
            "gender": onboarding.get("gender") if onboarding else None,
            "dob": birthdate,
            "country": onboarding.get("country") if onboarding else None,
            "interested_in": onboarding.get("interested_in") if onboarding else None,
            "sexual_orientation": onboarding.get("sexual_orientation") if onboarding else None,
            "marital_status": onboarding.get("marital_status") if onboarding else None
        },

        "payment_info": {
            "wallet_address": user.get("wallet_address")
        },

        "security": {
            "two_factor_enabled": user.get("two_factor_enabled", False)
        },

        "preferences": {
            "hobbies": onboarding.get("passions", []) if onboarding else [],
            "sexual_preferences": onboarding.get("sexual_preferences", []) if onboarding else [],
            "preferred_country": onboarding.get("preferred_country", []) if onboarding else []
        }
    }
