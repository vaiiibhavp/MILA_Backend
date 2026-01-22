#services/profile_mapper.py

from core.utils.age_calculation import calculate_age
from core.utils.core_enums import MembershipType
from core.utils.helper import *
from api.controller.files_controller import *

async def build_basic_profile_response(user: dict, onboarding: dict, profile_photo: str):
    birthdate = onboarding.get("birthdate") if onboarding else None
    age = calculate_age(birthdate) if birthdate else None

    country_name = await get_country_name_by_id(onboarding.get("country"), countries_collection)

    return {
        "header": {
            "name": user.get("username"),
            "age": age,
            "is_verified": user.get("is_verified", False),
            "profile_photo": profile_photo,
            "language": user.get("language", "en"),
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

async def build_edit_profile_response(user: dict, onboarding: dict):
    onboarding = onboarding or {}
    is_premium = user.get("membership_type") == MembershipType.PREMIUM

    country_name = await get_country_name_by_id(
        onboarding.get("country"),
        countries_collection
    )

    preferred_countries = []

    for cid in onboarding.get("preferred_country", []):
        if not cid:
            continue

        country = await countries_collection.find_one(
            {"_id": ObjectId(cid)},
            {"name": 1, "code": 1}
        )
        if country:
            preferred_countries.append({
                "id": str(country["_id"]),
                "name": country["name"],
            })

    birthdate = onboarding.get("birthdate") if onboarding else None
    age = calculate_age(birthdate) if birthdate else None

    data = {
        "username": user.get("username"),
        "is_verified": user.get("is_verified", False),        
        "profile_photo": await profile_photo_from_onboarding(onboarding),

        "basic_details": {
            "bio": onboarding.get("bio"),
            "country": country_name,
            "country_id": onboarding.get("country"),
            "gender": build_selectable_options(
                enum_values(GenderEnum),
                onboarding.get("gender")
            ),
            "age": age,
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

            # SHOW FOR ALL USERS
            "sexual_preferences": build_selectable_options(
                enum_values(SexualPreferenceEnum),
                onboarding.get("sexual_preferences", [])
            ),

            "preferred_country": preferred_countries
        },

        "security": {
            "wallet_address": user.get("wallet_address"),
            "two_factor_enabled": user.get("two_factor_enabled", False)
        },

        "premium": {
            "enabled": is_premium
        }
    }

    return data
