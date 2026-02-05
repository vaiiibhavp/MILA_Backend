from datetime import datetime
from core.utils.response_mixin import CustomResponseMixin
from config.models.transaction_model import TransactionModel
from core.utils.pagination import build_paginated_response
from services.translation import translate_message
from config.db_config import system_config_collection

response = CustomResponseMixin()


async def fetch_all_transactions_controller(
    tab,
    search,
    status,
    date_from,
    date_to,
    pagination,
    lang="en"
):
    try:
        result = await TransactionModel.fetch_all_transactions(
            tab=tab,
            search=search,
            status=status,
            date_from=date_from,
            date_to=date_to,
            pagination=pagination
        )

        records = result.get("data", [])
        total_records = result.get("total", 0)

        # ---------------- COMMON PAGINATION RESPONSE ----------------
        page = pagination.page if pagination and pagination.page else 1
        page_size = (
            pagination.page_size
            if pagination and pagination.page_size
            else len(records)
        )

        paginated_response = build_paginated_response(
            records=records,
            page=page,
            page_size=page_size,
            total_records=total_records
        )

        return response.success_message(
            translate_message("TRANSACTIONS_FETCHED_SUCCESSFULLY", lang),
            data=[paginated_response],
            status_code=200
        )

    except Exception as e:
        print("the error is", str(e))
        return response.error_message(
            translate_message("FAILED_TO_FETCH_TRANSACTIONS", lang),
            data=str(e),
            status_code=500
        )


async def get_subscription_bonus_token_controller(lang="en"):
    try:
        data = await TransactionModel.get_subscription_bonus_token()

        return response.success_message(
            translate_message("SUBSCRIPTION_BONUS_TOKEN_FETCHED_SUCCESSFULLY" , lang),
            data=[data],
            status_code=200
        )

    except Exception as e:
        return response.error_message(
            translate_message("FAILED_TO_FETCH_SUBSCRIPTION_BONUS_TOKEN",lang),
            data=str(e),
            status_code=500
        )


async def update_subscription_bonus_token_controller(tokens: int ,lang="en"):
    try:
        if tokens < 0:
            raise ValueError("Token value cannot be negative")

        data = await TransactionModel.update_subscription_bonus_token(tokens)

        return response.success_message(
            translate_message("SUBSCRIPTION_BONUS_TOKEN_UPDATED_SUCCESSFULLY",lang),
            data=data,
            status_code=200
        )

    except Exception as e:
        return response.error_message(
            translate_message("FAILED_TO_UPDATE_SUBSCRIPTION_BONUS_TOKEN",lang),
            data=str(e),
            status_code=500
        )
