from fastapi import Request
from services.translation import translate_message
from core.utils.response_mixin import CustomResponseMixin
from core.utils.helper import serialize_datetime_fields, convert_objectid_to_str
from config.db_config import subscription_plan_collection
from core.utils.transaction_helper import get_transaction_details, validate_destination_wallet, \
    validate_transaction_status, build_transaction_model, handle_full_payment
from schemas.transcation_schema import TransactionRequestModel
from core.utils.core_enums import TransactionStatus
response = CustomResponseMixin()
from config.models.transaction_models import store_transaction_details, get_existing_transaction
from config.models.subscription_plan_models import get_subscription_plan


async def get_subscription_list(request: Request, lang: str = "en"):
    """
    Get all active subscription plan list.
    """
    try:
        cursor = subscription_plan_collection.find({f"status": "active"})
        subscription_docs = await cursor.to_list(length=None)  # <- correct: await on to_list, not on cursor
        subscription_docs = serialize_datetime_fields(subscription_docs)
        subscription_list = convert_objectid_to_str(subscription_docs)
        return response.success_message(
            translate_message("SUBSCRIPTION_PLAN_FETCHED", lang=lang),
            data=subscription_list
        )
    except Exception as e:
        return response.raise_exception(
            translate_message("ERROR_FETCHING_SUBSCRIPTION_PLAN", lang=lang),
            data=str(e),
            status_code=500
        )

async def transaction_verify(request: TransactionRequestModel,user_id:str, lang: str = "en"):
    """
    Validate transaction details associated with subscription plans
    """
    try:
        transaction = await get_existing_transaction(request.txn_id)
        if transaction is not None:
            return response.error_message(
                translate_message("ALREADY_SUBSCRIBED_USING_THIS_TRANSACTION_ID", lang=lang),
                data=[],
                status_code=409
            )
        transaction_details = await get_transaction_details(request.txn_id)

        if transaction_details is None or transaction_details['status'] is None:
            return response.raise_exception(
                translate_message("ERROR_WHILE_FETCHING_TRANSACTION_DETAILS", lang=lang),
                data=[],
                status_code=502
            )
        # Fetch subscription plan details
        plan_data = await get_subscription_plan(request.plan_id, lang=lang)

        validate_destination_wallet(transaction_details["to"], lang=lang)

        validate_transaction_status(transaction_details["to"], lang=lang)

        transaction_data = await build_transaction_model(user_id, plan_data, transaction_details)

        if transaction_data.status == TransactionStatus.PARTIAL.value:
            doc = await store_transaction_details(transaction_data)
        else:
            doc = await handle_full_payment(
                transaction_data=transaction_data,
                plan_data=plan_data,
                user_id=user_id,
            )

        doc = serialize_datetime_fields(doc)
        doc = convert_objectid_to_str(doc)


        return response.success_message(
            translate_message("TRANSACTION_DETAILS_VERIFIED_SUCCESSFULLY", lang=lang),
            data=doc
        )

    except Exception as e:
        return response.raise_exception(
            translate_message("ERROR_VERIFYING_TRANSACTION_DETAILS", lang=lang),
            data=str(e),
            status_code=500
        )

