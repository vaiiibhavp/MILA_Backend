from datetime import datetime
from core.utils.response_mixin import CustomResponseMixin
from config.models.event_managment_model import ContestModel
from schemas.event_management_schema import ContestUpdateSchema
from services.translation import translate_message


response = CustomResponseMixin()


async def create_contest(
    payload,
    admin_id: str,
    lang: str = "en"
):
    try:
        result = await ContestModel.create_contest(
            payload=payload,
            admin_id=admin_id,
            lang=lang
        )

        if result.get("error"):
            return response.error_message(
                message=result["message"],
                data=[],
                status_code=result["status_code"]
            )

        return response.success_message(
            translate_message("CONTEST_CREATED_SUCCESSFULLY", lang),
            data=[result["data"]],
            status_code=201
        )

    except Exception as e:
        return response.error_message(
            translate_message("FAILED_TO_CREATE_CONTEST", lang),
            data=str(e),
            status_code=500
        )



async def upload_contest_banner(
    image,
    admin: dict
):
    try:
        lang = admin.get("language", "en")
        admin_id = str(admin["_id"])

        result = await ContestModel.upload_contest_banner(
            image=image,
            admin_id=admin_id,
            lang=lang
        )

        if result.get("error"):
            return response.error_message(
                message=result["message"],
                data=[],
                status_code=result["status_code"]
            )

        return response.success_message(
            translate_message("FILE_UPLOADED_SUCCESS", lang),
            data=[result["data"]],
            status_code=200
        )

    except Exception as e:
        return response.raise_exception(
            translate_message("ERROR_WHILE_UPLOADING_FILE", lang),
            data=str(e),
            status_code=500
        )

async def fetch_contests(
    search: str | None,
    date_from,
    date_to,
    visibility,
    frequency,
    pagination,
    lang: str = "en"
):
    try:
        result = await ContestModel.fetch_contests(
            search=search,
            date_from=date_from,
            date_to=date_to,
            visibility=visibility,
            frequency=frequency,
            pagination=pagination,
            lang=lang
        )

        return response.success_message(
            translate_message("CONTESTS_FETCHED_SUCCESSFULLY", lang),
            data=result["data"],
            status_code=200
        )

    except Exception as e:
        return response.error_message(
            translate_message("FAILED_TO_FETCH_CONTESTS", lang),
            data=str(e),
            status_code=500
        )

async def get_contest_details_controller(
    contest_id: str,
    lang: str = "en"
):
    try:
        result = await ContestModel.get_contest_details(
            contest_id=contest_id,
            lang=lang
        )

        if result.get("error"):
            return response.error_message(
                message=result["message"],
                data=[],
                status_code=result["status_code"]
            )

        return response.success_message(
            translate_message("CONTEST_DETAILS_FETCHED_SUCCESSFULLY", lang),
            data=[result["data"]],
            status_code=200
        )

    except Exception as e:
        return response.error_message(
            translate_message("FAILED_TO_FETCH_CONTEST_DETAILS", lang),
            data=str(e),
            status_code=500
        )

async def update_contest_controller(
    contest_id: str,
    payload: ContestUpdateSchema,
    admin_id: str,
    lang: str = "en"
):
    try:
        result = await ContestModel.update_contest(
            contest_id=contest_id,
            payload=payload,
            admin_id=admin_id,
            lang=lang
        )

        if result.get("error"):
            return response.error_message(
                message=result["message"],
                data=[],
                status_code=result["status_code"]
            )

        return response.success_message(
            translate_message("CONTEST_UPDATED_SUCCESSFULLY", lang),
            data=[result["data"]],
            status_code=200
        )

    except Exception as e:
        return response.error_message(
            translate_message("FAILED_TO_UPDATE_CONTEST", lang),
            data=str(e),
            status_code=500
        )

async def delete_contest_controller(
    contest_id: str,
    admin_id: str,
    lang: str = "en"
):
    try:
        result = await ContestModel.delete_contest(
            contest_id=contest_id,
            admin_id=admin_id,
            lang=lang
        )

        if result.get("error"):
            return response.error_message(
                message=result["message"],
                data=[],
                status_code=result["status_code"]
            )

        return response.success_message(
            translate_message("CONTEST_DELETED_SUCCESSFULLY", lang),
            data=[result["data"]],
            status_code=200
        )

    except Exception as e:
        return response.error_message(
            translate_message("FAILED_TO_DELETE_CONTEST", lang),
            data=str(e),
            status_code=500
        )

async def get_contest_participants_controller(
    contest_id: str,
    search: str | None,
    pagination,
    lang: str = "en"
):
    try:
        result = await ContestModel.get_contest_participants(
            contest_id=contest_id,
            search=search,
            pagination=pagination,
            lang=lang
        )

        return response.success_message(
            translate_message("CONTEST_PARTICIPANTS_FETCHED_SUCCESSFULLY", lang),
            data=result["data"],
            status_code=200
        )

    except Exception as e:
        return response.error_message(
            translate_message("FAILED_TO_FETCH_CONTEST_PARTICIPANTS", lang),
            data=str(e),
            status_code=500
        )
