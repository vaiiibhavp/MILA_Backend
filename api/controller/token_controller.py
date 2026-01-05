from bson import ObjectId

from core.utils.core_enums import TransactionType, TransactionStatus
from core.utils.exceptions import CustomValidationError
from core.utils.pagination import StandardResultsSetPagination
from config.models.user_token_history_model import get_user_token_history
from config.models.token_packages_plan_model import get_token_packages_plans, get_token_packages_plan
from schemas.transcation_schema import TokenWithdrawTransactionCreateModel
from schemas.user_token_history_schema import TokenHistoryResponse, TokenTransactionRequestModel, \
    CompleteTokenTransactionRequestModel, WithdrawnTokenRequestModel
from services.translation import translate_message
from core.utils.helper import serialize_datetime_fields, convert_objectid_to_str
from core.utils.transaction_helper import get_transaction_details, validate_destination_wallet, \
    validate_transaction_status, build_transaction_model, handle_full_payment, mark_full_payment_received, \
    handle_token_full_payment, mark_token_full_payment_received, validate_withdrawal_tokens, \
    calculate_tokens_based_on_amount
from config.models.transaction_models import (store_transaction_details, get_existing_transaction,
                                              get_subscription_payment_details, update_transaction_details,
                                              store_withdrawn_token_request, ensure_no_pending_token_withdrawal)
from config.models.user_models import get_user_details
from core.utils.response_mixin import CustomResponseMixin
response = CustomResponseMixin()


async def get_user_token_details(
        user_id:str,
        lang:str,
        pagination:StandardResultsSetPagination
):
    try:
        token_history = await get_user_token_history(user_id=user_id,lang=lang,pagination=pagination)
        available_tokens = await get_user_details(condition={"_id":ObjectId(user_id)}, fields=["tokens"])
        token_plans = await get_token_packages_plans()
        token_plans = convert_objectid_to_str(token_plans)
        data = TokenHistoryResponse(
            history=token_history,
            available_tokens=str(available_tokens.get("tokens", "0")),
            token_plans=token_plans
        ).model_dump()
        data = serialize_datetime_fields(data)
        return response.success_message(
            translate_message("SUBSCRIPTION_PLAN_FETCHED", lang=lang),
            data=[data]
        )
    except Exception as e:
        return response.raise_exception(
            translate_message("ERROR_WHILE_FETCHING_TOKEN_DETAILS", lang=lang),
            data=str(e),
            status_code=500
        )
async def verify_token_purchase(request: TokenTransactionRequestModel,user_id:str, lang: str = "en"):
    """
        Verifies a token purchase transaction and processes token credit based on the transaction status.

        This function validates the transaction ID, retrieves transaction and token
        package details, verifies the destination wallet and transaction status, and
        builds the transaction model. For partial payments, it stores the transaction
        without crediting tokens. For fully paid transactions, it credits tokens to
        the user's account, updates token history, and persists the transaction.
        Finally, it formats the response data and returns a success message.

        :param request: TokenTransactionRequestModel containing transaction ID and
                        token package identifier.
        :param user_id: Unique identifier of the user initiating the token purchase.
        :param lang: Language code used for localized messages (default is "en").
        :return: Success response containing the verified transaction details.
    """
    try:
        await get_existing_transaction(request.tron_txn_id, lang=lang)

        transaction_details = await get_transaction_details(request.tron_txn_id, lang=lang)

        # Fetch token package plan details
        plan_data = await get_token_packages_plan(request.package_id, lang=lang)

        validate_destination_wallet(transaction_details["to"], lang=lang)

        validate_transaction_status(transaction_details["status"], lang=lang)

        transaction_data = await build_transaction_model(
            user_id=user_id,
            plan_data=plan_data,
            transaction_details=transaction_details,
            trans_type=TransactionType.TOKEN_TRANSACTION.value
        )

        if transaction_data.status == TransactionStatus.PARTIAL.value:
            transaction_data.payment_details = [transaction_data.payment_details]
            doc = await store_transaction_details(transaction_data)
        else:
            doc = await handle_token_full_payment(
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

async def validate_remaining_token_payment(request: CompleteTokenTransactionRequestModel, user_id:str, lang: str = "en"):
    """
        Verifies and processes a token purchase transaction, including partial payments.

        This flow validates the blockchain transaction, retrieves existing transaction and
        partial payment details, fetches the associated token package plan, and validates
        the destination wallet and transaction status.

        The system then builds a transaction model using both blockchain and internal
        payment data. If the transaction remains partially paid, it updates the existing
        transaction record. If the payment is complete, it marks the transaction as fully
        paid, credits tokens to the user, and records the token transaction history.

        Finally, the system serializes the transaction document and prepares it for the response.
    """

    try:
        await get_existing_transaction(request.tron_txn_id, lang=lang)

        transaction_details = await get_transaction_details(request.tron_txn_id, lang=lang)

        partial_payment_data = await get_subscription_payment_details(request.trans_id, lang=lang)

        # Fetch token package plan details
        plan_data = await get_token_packages_plan(partial_payment_data.get('plan_id'), lang=lang)

        validate_destination_wallet(transaction_details["to"], lang=lang)

        validate_transaction_status(transaction_details["status"], lang=lang)

        transaction_data = await build_transaction_model(
            user_id=user_id,
            plan_data=plan_data,
            transaction_details=transaction_details,
            partial_payment_data=partial_payment_data,
            trans_type=TransactionType.TOKEN_TRANSACTION.value
        )

        if transaction_data.status == TransactionStatus.PARTIAL.value:
            doc = await update_transaction_details(transaction_data, request.trans_id)
        else:
            doc = await mark_token_full_payment_received(
                transaction_data=transaction_data,
                plan_data=plan_data,
                user_id=user_id,
                package_id=request.trans_id
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

async def request_withdrawn_token_amount(request: WithdrawnTokenRequestModel, user_id:str, lang: str = "en"):

    try:
        await ensure_no_pending_token_withdrawal(user_id=user_id, lang=lang)

        available_tokens = await get_user_details(condition={"_id": ObjectId(user_id)}, fields=["tokens"])
        await validate_withdrawal_tokens(int(available_tokens.get("tokens", "0")), lang=lang)

        withdrawn_token = await calculate_tokens_based_on_amount(request.amount)

        if int(withdrawn_token) > int(available_tokens.get("tokens", "0")):
            return response.error_message(
                message=translate_message("INSUFFICIENT_AMOUNT", lang=lang),
                data=[],
                status_code=400
            )
        withdrawn_request_data = TokenWithdrawTransactionCreateModel(
            user_id=str(ObjectId(user_id)),
            request_amount=request.amount,
            remaining_amount=request.amount,
            status=TransactionStatus.PENDING.value,
            tokens=withdrawn_token,
            wallet_address=request.wallet_address,
        )
        doc = await store_withdrawn_token_request(doc=withdrawn_request_data)
        doc = serialize_datetime_fields(doc)
        doc = convert_objectid_to_str(doc)
        return response.success_message(
            translate_message("WITHDRAWAL_REQUEST_SUBMITTED", lang=lang),
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
            translate_message("WITHDRAWAL_REQUEST_PROCESSING_ERROR", lang=lang),
            data=str(e),
            status_code=500
        )


    

