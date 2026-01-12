from services.translation import translate_message
from core.utils.response_mixin import CustomResponseMixin
from config.models.contest_model import *
from fastapi.encoders import jsonable_encoder
from core.utils.pagination import StandardResultsSetPagination

response = CustomResponseMixin()

async def get_contests_controller(
    current_user: dict,
    contest_type: str,
    pagination: StandardResultsSetPagination,
    lang: str = "en"
):
    # Verification gate
    if not current_user.get("is_verified"):
        return response.success_message(
            translate_message("VERIFICATION_PENDING", lang),
            data=[{"verification_required": True}]
        )

    contests, total = await get_contests_paginated(
        contest_type=contest_type,
        pagination=pagination
    )

    return response.success_message(
        translate_message("CONTESTS_FETCHED", lang),
        data=[{
            "results": jsonable_encoder(contests),
            "page": pagination.page,
            "page_size": pagination.page_size,
            "total": total
        }]
    )

