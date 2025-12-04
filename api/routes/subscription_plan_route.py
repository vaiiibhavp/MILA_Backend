from fastapi import APIRouter,Depends,Request,Query
from schemas.response_schema import Response
from core.utils.permissions import UserPermission
from api.controller.subscriptionPlan import get_subscription_list

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
