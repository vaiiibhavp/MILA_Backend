from typing import Optional
from datetime import datetime
from core.utils.response_mixin import CustomResponseMixin
from core.utils.pagination import StandardResultsSetPagination ,build_paginated_response
from services.translation import translate_message
from config.models.moderation_model import ModerationModel


response = CustomResponseMixin()

async def get_reported_users_controller(
    status: Optional[str],
    search: Optional[str],
    pagination: StandardResultsSetPagination,
    lang: str = "en"
):
    try:
        reports, total_records = await ModerationModel.get_reported_users_pipeline(
            status=status,
            search=search,
            pagination=pagination
        )

        for report in reports:
            if report.get("reported_at"):
                report["reported_at"] = report["reported_at"].isoformat()

        paginated_response = build_paginated_response(
            records=reports,
            page=pagination.page or 1,
            page_size=pagination.page_size or len(reports),
            total_records=total_records
        )

        return response.success_message(
            translate_message("REPORTED_USERS_FETCHED_SUCCESSFULLY", lang),
            data=paginated_response,
            status_code=200
        )

    except ValueError as ve:
        return response.error_message(
            translate_message("INVALID_REQUEST", lang),
            data=str(ve),
            status_code=400
        )

    except RuntimeError as re:
        return response.error_message(
            translate_message("FAILED_TO_FETCH_REPORTED_USERS", lang),
            data=str(re),
            status_code=500
        )

    except Exception as e:
        return response.error_message(
            translate_message("SOMETHING_WENT_WRONG", lang),
            data=str(e),
            status_code=500
        )

async def get_report_details_controller(report_id: str, lang: str = "en"):
    try:
        report = await ModerationModel.get_report_details_pipeline(report_id)

        if not report:
            return response.error_message(
                translate_message("REPORT_NOT_FOUND", lang),
                [],
                404
            )

        # ---------------- REPORTER IMAGE ----------------
        reporter_image_id = report["reporter"].pop("image_id", None)
        _, reporter_profile = await ModerationModel.get_user_photos(
            [reporter_image_id] if reporter_image_id else []
        )
        report["reporter"]["profile_image"] = reporter_profile

        # ---------------- REPORTED USER IMAGE ----------------
        reported_image_id = report["reported_user"].pop("image_id", None)
        _, reported_profile = await ModerationModel.get_user_photos(
            [reported_image_id] if reported_image_id else []
        )
        report["reported_user"]["profile_image"] = reported_profile

        # ---------------- DATE FORMAT ----------------
        if report.get("reported_at"):
            report["reported_at"] = report["reported_at"].isoformat()

        return response.success_message(
            translate_message("REPORT_DETAILS_FETCHED_SUCCESSFULLY", lang),
            report,
            200
        )

    except ValueError as ve:
        return response.error_message(
            translate_message("INVALID_REQUEST", lang),
            str(ve),
            400
        )

    except RuntimeError as re:
        return response.error_message(
            translate_message("FAILED_TO_FETCH_REPORT_DETAILS", lang),
            str(re),
            500
        )

    except Exception as e:
        return response.error_message(
            translate_message("SOMETHING_WENT_WRONG", lang),
            str(e),
            500
        )
