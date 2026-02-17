from fastapi import APIRouter ,Depends ,Query
from core.auth import get_current_user
from api.controller.home_controller import get_home_suggestions
from config.models.userPass_model import(
     add_to_fav , 
     like_user , 
     pass_user , 
     get_my_favorites , 
     get_users_who_liked_me, 
     get_user_login_status_internal,
     get_matched_users_controller
)
from core.utils.response_mixin import CustomResponseMixin
from services.translation import translate_message
from schemas.userpass_schema import( 
    AddFavoriteRequest , 
    PassUserRequest,
    LikeUserRequest
)

router = APIRouter()
response = CustomResponseMixin()

@router.get("/home")
async def home(
    current_user: dict = Depends(get_current_user),
    lang: str = "en"
):
    return await get_home_suggestions(
        user_id=str(current_user["_id"]),
        lang=lang
    )


# Route to handle user like flow
@router.post("/user/like", response_model=dict)
async def like_user_route(
    request: LikeUserRequest,
    current_user: dict = Depends(get_current_user),
    lang: str = "en"
):
    user_id = str(current_user["_id"])

    return await like_user(
        user_id=user_id,
        liked_user_id=request.liked_user_id,
        lang=lang
    )

# Route to add users in fav list 
@router.post("/user/add-fav", response_model=dict)
async def add_favorite_user(
    request: AddFavoriteRequest,
    current_user: dict = Depends(get_current_user)
):
    logged_in_user_id = str(current_user["_id"])

    return await add_to_fav(
        user_id=logged_in_user_id,
        favorite_user_id=request.favorite_user_id
    )


# API to return the passed user.
@router.post("/user/pass", response_model=dict)
async def pass_user_route(
    request: PassUserRequest,
    current_user: dict = Depends(get_current_user),
    lang: str = "en"
):
    user_id = str(current_user["_id"])

    return await pass_user(
        user_id=user_id,
        passed_user_id=request.passed_user_id,
        lang=lang
    )

# Route to get list of the users from favorites collection
@router.get("/user/favorites", response_model=dict)
async def get_favorite_users(
    current_user: dict = Depends(get_current_user),
    lang: str = "en"
):
    user_id = str(current_user["_id"])
    return await get_my_favorites(user_id, lang)

# Rotue to get user who liked my profile
@router.get("/user/liked-me", response_model=dict)
async def get_liked_me_users(
    current_user: dict = Depends(get_current_user),
    lang: str = "en"
):
    user_id = str(current_user["_id"])
    return await get_users_who_liked_me(user_id, lang)

@router.get("/user/login-status")
async def get_user_login_status_api(
    user_id: str,
    lang: str = "en"
):
    """
    Internal API: Get user login status
    """
    return await get_user_login_status_internal(user_id, lang)

@router.get("/users/matches")
async def get_matched_users(
    current_user: dict = Depends(get_current_user),
    lang: str = Query("en")
):
    return await get_matched_users_controller(current_user, lang)
