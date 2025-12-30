from core.utils.core_enums import MembershipType
from core.utils.response_mixin import CustomResponseMixin
from services.translation import translate_message

response = CustomResponseMixin()

def require_premium(current_user: dict, lang: str = "en"):
    """
    Ensures the user is a premium member.
    Returns an error response if not premium, otherwise None.
    """
    if current_user.get("membership_type") != MembershipType.PREMIUM:
        return response.error_message(
            translate_message("PREMIUM_REQUIRED", lang),
            status_code=403,
            data={"premium_required": True}
        )
    return None
