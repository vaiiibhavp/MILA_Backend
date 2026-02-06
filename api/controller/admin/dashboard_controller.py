from core.utils.response_mixin import CustomResponseMixin
from services.translation import translate_message
from config.models.dashboard_model import DashboardModel


response = CustomResponseMixin()

async def get_dashboard_controller(
    filter_type: str,
    lang: str = "en"
):
    try:
        data = await DashboardModel.get_dashboard_stats(filter_type)

        return response.success_message(
            translate_message("DASHBOARD_FETCHED_SUCCESSFULLY", lang),
            data=data,
            status_code=200
        )

    except Exception as e:
        return response.error_message(
            translate_message("FAILED_TO_FETCH_DASHBOARD", lang),
            data=str(e),
            status_code=500
        )
