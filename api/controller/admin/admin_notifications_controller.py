# controllers/admin_notification_controller.py
from core.utils.response_mixin import CustomResponseMixin
from services.translation import translate_message
from config.models.admin_notification_model import NotificationModel


response = CustomResponseMixin()

async def get_admin_notifications_controller(current_admin, lang: str = "en"):
    try:
        admin_id = str(current_admin["_id"])

        data = await NotificationModel.get_admin_notifications(
            admin_id,
            lang
        )

        return response.success_message(
            translate_message("NOTIFICATION_FETCHED", lang),
            data=data,
            status_code=200
        )

    except Exception as e:
        return response.error_message(
            translate_message("SOMETHING_WENT_WRONG", lang),
            data=str(e),
            status_code=500
        )


async def mark_admin_notification_read(
    notification_id: str,
    current_admin,
    lang: str = "en"
):
    try:
        admin_id = str(current_admin["_id"])

        await NotificationModel.mark_admin_notification_read(
            notification_id,
            admin_id
        )

        return response.success_message(
            translate_message("NOTIFICATION_MARKED_AS_READ", lang),
            status_code=200
        )

    except ValueError as ve:
        return response.error_message(
            translate_message(str(ve), lang),
            status_code=400
        )

    except Exception as e:
        return response.error_message(
            translate_message("SOMETHING_WENT_WRONG", lang),
            data=str(e),
            status_code=500
        )

async def mark_all_admin_notifications_read(current_admin, lang: str = "en"):
    try:
        admin_id = str(current_admin["_id"])

        updated_count = await NotificationModel.mark_all_admin_notifications_read(
            admin_id
        )

        return response.success_message(
            translate_message("ALL_NOTIFICATION_MARKED_AS_READ", lang),
            data={"updated_count": updated_count},
            status_code=200
        )

    except Exception as e:
        return response.error_message(
            translate_message("SOMETHING_WENT_WRONG", lang),
            data=str(e),
            status_code=500
        )
