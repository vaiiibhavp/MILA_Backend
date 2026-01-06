from fastapi import APIRouter,Depends,Request,Query

from core.utils.pagination import StandardResultsSetPagination, pagination_params
from schemas.response_schema import Response
from core.utils.permissions import UserPermission
from api.controller.subscriptionPlan import get_subscription_list, transaction_verify, \
    validate_remaining_transaction_payment, fetch_subscription_transactions
from schemas.transcation_schema import TransactionRequestModel, CompleteTransactionRequestModel

supported_langs = ["en", "fr"]
api_router = APIRouter()

class SubscriptionPlan:

    # api for getting subscription plans
    @api_router.get("/", response_model=Response)
    async def get_subscription_plans(request: Request, current_user: dict = Depends(UserPermission(allowed_roles=["user","admin"])), lang: str = Query(None)):
        """
            Get subscription plans:-
            Retrieves the active subscription plan details.
        """
        lang = lang if lang in supported_langs else "en"
        return await get_subscription_list(request, lang)

    @api_router.post("/verify_transaction", response_model=Response)
    async def verify_transaction(request: TransactionRequestModel, current_user: dict = Depends(UserPermission(allowed_roles=["user"], require_verified=True)), lang: str = Query(None)):
        """
            check transaction details associated with subscription plans
        """
        user_id = str(current_user["_id"])
        lang = lang if lang in supported_langs else "en"
        return await transaction_verify(request,user_id,lang)

    @api_router.post("/complete-payment", response_model=Response)
    async def complete_payment(request: CompleteTransactionRequestModel, current_user:dict = Depends(UserPermission(allowed_roles=["user"], require_verified=True)), lang: str = Query(None)):
        """
            verify remaining subscription plans amount transaction details
        """
        user_id = str(current_user["_id"])
        lang = lang if lang in supported_langs else "en"
        return await validate_remaining_transaction_payment(request, user_id, lang)

    @api_router.get("/transactions")
    async def get_user_subscription_transactions(
            request: Request,
            current_user: dict = Depends(UserPermission(allowed_roles=["user"])),
            lang: str = Query(None),
            pagination: StandardResultsSetPagination = Depends(pagination_params)
    ):
        """
            Retrieves the subscription transaction history for the authenticated user.
            This endpoint returns a paginated list of subscription transactions,
            allowing users to view their subscription purchase history
            with localized response messages.
        """
        user_id = str(current_user["_id"])
        lang = lang if lang in supported_langs else "en"
        return await fetch_subscription_transactions(user_id=user_id, lang=lang, pagination=pagination)

