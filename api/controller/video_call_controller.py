from core.utils.response_mixin import CustomResponseMixin
from services.translation import translate_message
from api.controller.onboardingController import fetch_user_by_id

response = CustomResponseMixin()

async def get_user_details_controller(current_user: dict, lang: str = "en"):
    try:
        user_id = str(current_user.get("_id") or current_user.get("id"))

        user_data = await fetch_user_by_id(user_id, lang)

        return response.success_message(
            translate_message("USER_DETAILS_FETCHED_SUCCESSFULLY", lang),
            data=[user_data],
            status_code=200
        )

    except Exception as e:
        return response.error_message(
            translate_message("ERROR_WHILE_FETCHING_USER_DETAILS", lang),
            data=[str(e)],
            status_code=500
        )
