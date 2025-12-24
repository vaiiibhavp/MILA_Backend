from fastapi import Request

from core.utils.exceptions import CustomValidationError
from services.translation import translate_message
from core.utils.response_mixin import CustomResponseMixin
from core.utils.helper import serialize_datetime_fields, convert_objectid_to_str
from config.db_config import subscription_plan_collection
from core.utils.transaction_helper import get_transaction_details, validate_destination_wallet, \
    validate_transaction_status, build_transaction_model, handle_full_payment, mark_full_payment_received
from schemas.transcation_schema import TransactionRequestModel, CompleteTransactionRequestModel
from core.utils.core_enums import TransactionStatus, TransactionType

response = CustomResponseMixin()
from config.models.transaction_models import store_transaction_details, get_existing_transaction, get_subscription_payment_details, update_transaction_details
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
        await get_existing_transaction(request.tron_txn_id, lang=lang)

        transaction_details = await get_transaction_details(request.tron_txn_id, lang=lang)

        # Fetch subscription plan details
        plan_data = await get_subscription_plan(request.plan_id, lang=lang)

        validate_destination_wallet(transaction_details["to"], lang=lang)

        validate_transaction_status(transaction_details["status"], lang=lang)

        transaction_data = await build_transaction_model(
            user_id=user_id,
            plan_data=plan_data,
            transaction_details=transaction_details,
            trans_type=TransactionType.SUBSCRIPTION_TRANSACTION.value
        )

        if transaction_data.status == TransactionStatus.PARTIAL.value:
            transaction_data.payment_details = [transaction_data.payment_details]
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
    except CustomValidationError as error:
        return response.error_message(
            message=error.message,
            data=error.data,
            status_code=error.status_code
        )
    except Exception as e:
        return response.raise_exception(
            translate_message("ERROR_VERIFYING_TRANSACTION_DETAILS", lang=lang),
            data=str(e),
            status_code=500
        )

async def validate_remaining_transaction_payment(request: CompleteTransactionRequestModel, user_id:str, lang: str = "en"):
    """
        Validate remaining transaction payment details associated with subscription plans
        """
    try:
        await get_existing_transaction(request.tron_txn_id, lang=lang)

        transaction_details = await get_transaction_details(request.tron_txn_id, lang=lang)


        partial_payment_data = await get_subscription_payment_details(request.subscription_id, lang=lang)

        # Fetch subscription plan details
        plan_data = await get_subscription_plan(partial_payment_data.get('plan_id'), lang=lang)

        validate_destination_wallet(transaction_details["to"], lang=lang)

        validate_transaction_status(transaction_details["status"], lang=lang)

        transaction_data = await build_transaction_model(
            user_id=user_id,
            plan_data=plan_data,
            transaction_details=transaction_details,
            partial_payment_data=partial_payment_data,
            trans_type=TransactionType.SUBSCRIPTION_TRANSACTION.value
        )

        if transaction_data.status == TransactionStatus.PARTIAL.value:
            doc = await update_transaction_details(transaction_data, request.subscription_id)
        else:
            doc = await mark_full_payment_received(
                transaction_data=transaction_data,
                plan_data=plan_data,
                user_id=user_id,
                subscription_id=request.subscription_id
            )

        doc = serialize_datetime_fields(doc)
        doc = convert_objectid_to_str(doc)


        return response.success_message(
            translate_message("TRANSACTION_DETAILS_VERIFIED_SUCCESSFULLY", lang=lang),
            data=doc
        )

    except CustomValidationError as error:
        return response.error_message(
            message=error.message,
            data=error.data,
            status_code=error.status_code
        )
    except Exception as e:
        return response.raise_exception(
            translate_message("ERROR_VERIFYING_TRANSACTION_DETAILS", lang=lang),
            data=str(e),
            status_code=500
        )


