from fastapi import APIRouter,Depends,Request,Query

from core.utils.pagination import StandardResultsSetPagination, pagination_params
from core.utils.permissions import UserPermission
from api.controller.token_controller import get_user_token_details, verify_token_purchase, \
    validate_remaining_token_payment, request_withdrawn_token_amount, fetch_withdraw_token_transactions
from schemas.user_token_history_schema import (TokenTransactionRequestModel, CompleteTokenTransactionRequestModel,
    WithdrawnTokenRequestModel)

api_router = APIRouter()
supported_langs = ["en", "fr"]

class TokenRoutes:
    @api_router.get("/token-history")
    async def get_token_history(request: Request, current_user: dict = Depends(UserPermission(allowed_roles=["user"])), lang: str = Query(None), pagination: StandardResultsSetPagination = Depends(pagination_params)):
        """
            Get User Token Details:
            Description:
            - Retrieves the user's token information.

            Response Fields:
            - available_tokens: Number of tokens currently available for the user.
            - history: List of token transactions, including usage, credits, and timestamps.
        """
        user_id = str(current_user["_id"])
        lang = lang if lang in supported_langs else "en"
        return await get_user_token_details(user_id=user_id, lang=lang, pagination=pagination)

    @api_router.post("/verify-token-purchase")
    async def validate_token_purchase(request: TokenTransactionRequestModel,current_user: dict = Depends(UserPermission(allowed_roles=["user"], require_verified=True)), lang: str = Query(None)):
        """
            Validates a token purchase transaction for the authenticated user.

            This endpoint verifies the provided transaction details, ensures the
            transaction status and destination wallet are valid, and processes
            the token purchase accordingly.

            :param request: TokenTransactionRequestModel contains the transaction
                            identifier and token package details.
            :param current_user: Authenticated user details provided by the permission
                                 dependency.
            :param lang: Optional language code for localized responses.
            :return: Response containing the validated token purchase details.
        """

        user_id = str(current_user["_id"])
        lang = lang if lang in supported_langs else "en"
        return await verify_token_purchase(request=request, user_id=user_id, lang=lang)


    @api_router.post("/complete-token-purchase")
    async def complete_token_purchase(request: CompleteTokenTransactionRequestModel, current_user:dict = Depends(UserPermission(allowed_roles=["user"], require_verified=True)), lang: str = Query(None)):
        """
            Verifies and completes the remaining payment for a token purchase.

            This endpoint validates the remaining subscription payment transaction,
            ensures the payment status is correct, and completes the token purchase
            flow for the authenticated user.

            :param request: CompleteTokenTransactionRequestModel containing the
                            remaining transaction and subscription details.
            :param current_user: Authenticated user details obtained from the
                                 permission dependency.
            :param lang: Optional language code for localized responses.
            :return: Response containing the result of the token purchase completion.
        """
        user_id = str(current_user["_id"])
        lang = lang if lang in supported_langs else "en"
        return await validate_remaining_token_payment(request, user_id, lang)

    @api_router.post("/withdraw-token-request")
    async def withdraw_token_request(request: WithdrawnTokenRequestModel, current_user: dict = Depends(UserPermission(allowed_roles=["user"])), lang: str = Query(None)):
        """
            Submits a request to withdraw tokens for the authenticated user.

            This endpoint validates the withdrawal request, ensures the user has
            sufficient tokens, and initiates the token withdrawal process.
            :param request: WithdrawnTokenRequestModel containing the withdrawal
                    amount and related details.
            :param current_user: Authenticated user details provided by the permission
                                 dependency.
            :param lang: Optional language code for localized responses.
            :return: Response indicating the status of the token withdrawal request.
        """
        user_id = str(current_user["_id"])
        lang = lang if lang in supported_langs else "en"
        return await request_withdrawn_token_amount(request, user_id, lang)

    @api_router.get("/withdraw-transactions")
    async def get_withdraw_transactions_history(
            request: Request,
            current_user: dict = Depends(UserPermission(allowed_roles=["user"])),
            lang: str = Query(None),
            pagination: StandardResultsSetPagination = Depends(pagination_params)
    ):
        """
            Retrieves the token withdrawal transaction history for the authenticated user.

            This endpoint returns a paginated list of token withdrawal transactions,
            allowing users to view their withdrawal history with localized response messages.
        """
        user_id = str(current_user["_id"])
        lang = lang if lang in supported_langs else "en"
        return await fetch_withdraw_token_transactions(user_id=user_id, lang=lang, pagination=pagination)
