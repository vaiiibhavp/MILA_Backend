from fastapi import APIRouter,Depends,Request,Query

from core.utils.pagination import StandardResultsSetPagination, pagination_params
from schemas.response_schema import Response
from core.utils.permissions import UserPermission
from api.controller.token_controller import get_user_token_details

api_router = APIRouter()
supported_langs = ["en", "fr"]

class TokenRoutes:
    @api_router.get("/token-history")
    async def get_token_history(request: Request, current_user: dict = Depends(UserPermission(allowed_roles=["user"])), lang: str = Query(None), pagination: StandardResultsSetPagination = Depends(pagination_params)):
        """
            Get subscription plans:-
            Retrieves the active subscription plan details.
        """
        user_id = str(current_user["_id"])
        lang = lang if lang in supported_langs else "en"
        return await get_user_token_details(user_id=user_id, lang=lang, pagination=pagination)