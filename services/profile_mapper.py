#services/profile_mapper.py

from core.utils.age_calculation import calculate_age
from core.utils.core_enums import MembershipType
from core.utils.helper import *

async def build_basic_profile_response(user: dict, onboarding: dict, profile_photo: str):
    birthdate = onboarding.get("birthdate") if onboarding else None
    age = calculate_age(birthdate) if birthdate else None

    country_name = await get_country_name_by_id(onboarding.get("country"), countries_collection)

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
            "country": country_name,
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

def build_selectable_options(all_options: list, selected_values):
    if not selected_values:
        selected_values = []

    if not isinstance(selected_values, list):
        selected_values = [selected_values]

    return [
        {
            "key": option,
            "selected": option in selected_values
        }
        for option in all_options
    ]

def build_edit_profile_response(user: dict, onboarding: dict):
    onboarding = onboarding or {}
    is_premium = user.get("membership_type") == MembershipType.PREMIUM

    data = {
        "basic_details": {
            "bio": onboarding.get("bio"),
            "country": onboarding.get("country"),

            "gender": build_selectable_options(
                enum_values(GenderEnum),
                onboarding.get("gender")
            ),

            "sexual_orientation": build_selectable_options(
                enum_values(SexualOrientationEnum),
                onboarding.get("sexual_orientation")
            ),

            "marital_status": build_selectable_options(
                enum_values(MaritalStatusEnum),
                onboarding.get("marital_status")
            )
        },

        "interests": {
            "passions": build_selectable_options(
                onboarding.get("passions", []),   # passions are free-text / config-based
                onboarding.get("passions", [])
            ),

            "interested_in": build_selectable_options(
                enum_values(InterestedInEnum),
                onboarding.get("interested_in", [])
            ),

            "preferred_country": onboarding.get("preferred_country", [])
        },

        "security": {
            "wallet_address": user.get("wallet_address"),
            "two_factor_enabled": user.get("two_factor_enabled", False)
        },

        "premium": {
            "enabled": is_premium
        }
    }

    if is_premium:
        data["interests"]["sexual_preferences"] = build_selectable_options(
            enum_values(SexualPreferenceEnum),
            onboarding.get("sexual_preferences", [])
        )

    return data
