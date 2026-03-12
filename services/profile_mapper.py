#services/profile_mapper.py

from core.utils.age_calculation import calculate_age
from core.utils.core_enums import MembershipType
from core.utils.helper import *
from api.controller.files_controller import *

async def build_basic_profile_response(user: dict, onboarding: dict, profile_photo: str, lang: str = "en"):
    birthdate = onboarding.get("birthdate") if onboarding else None
    age = calculate_age(birthdate) if birthdate else None

    country_name = await get_country_name_by_id(onboarding.get("country"), countries_collection, lang)
    preferred_countries = []

    for cid in onboarding.get("preferred_country", []):
        if not cid:
            continue

        country_name = await get_country_name_by_id(
            cid,
            countries_collection,
            lang
        )

        if country_name:
            preferred_countries.append({
                "id": str(cid),
                "name": country_name
            })
        gender = onboarding.get("gender") if onboarding else None
        marital_status = onboarding.get("marital_status") if onboarding else None
        orientation = onboarding.get("sexual_orientation") if onboarding else None
        interested_in = onboarding.get("interested_in") if onboarding else None

        gender_translated = translate_message(gender.upper(), lang) if gender else None
        marital_translated = translate_message(marital_status.upper(), lang) if marital_status else None
        orientation_translated = translate_message(orientation.upper(), lang) if orientation else None
        interest_translated = translate_message(interested_in.upper(), lang) if interested_in else None

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
            "gender": gender_translated,
            "dob": birthdate,
            "country": country_name,
            "interested_in": interest_translated,
            "sexual_orientation": orientation_translated,
            "marital_status": marital_translated
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
            "preferred_country": preferred_countries
        }
    }

def build_selectable_options(all_options: list, selected_values, lang: str):
    if not selected_values:
        selected_values = []

    if not isinstance(selected_values, list):
        selected_values = [selected_values]

    result = []

    for option in all_options:
        translated_label = translate_message(option.upper(), lang)

        result.append({
            "key": option,              # stable value (for backend)
            "label": translated_label,  # translated display text
            "selected": option in selected_values
        })

    return result

async def build_edit_profile_response(user: dict, onboarding: dict, lang):
    onboarding = onboarding or {}
    is_premium = user.get("membership_type") == MembershipType.PREMIUM

    country_name = await get_country_name_by_id(
        onboarding.get("country"),
        countries_collection,
        lang
    )

    preferred_countries = []

    for cid in onboarding.get("preferred_country", []):
        if not cid:
            continue

        country_name = await get_country_name_by_id(
            cid,
            countries_collection,
            lang
        )

        if country_name:
            preferred_countries.append({
                "id": str(cid),
                "name": country_name
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
                onboarding.get("gender"),
                lang
            ),
            "age": age,
            "sexual_orientation": build_selectable_options(
                enum_values(SexualOrientationEnum),
                onboarding.get("sexual_orientation"),
                lang
            ),

            "marital_status": build_selectable_options(
                enum_values(MaritalStatusEnum),
                onboarding.get("marital_status"),
                lang
            )
        },

        "interests": {
            "passions": build_selectable_options(
                onboarding.get("passions", []),   # passions are free-text / config-based
                onboarding.get("passions", []),
                lang
            ),

            "interested_in": build_selectable_options(
                enum_values(InterestedInEnum),
                onboarding.get("interested_in", []),
                lang
            ),

            # SHOW FOR ALL USERS
            "sexual_preferences": build_selectable_options(
                enum_values(SexualPreferenceEnum),
                onboarding.get("sexual_preferences", []),
                lang
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
