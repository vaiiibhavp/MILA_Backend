from fastapi import APIRouter, Depends, HTTPException , File
from bson import ObjectId
from fastapi import UploadFile
from config.models.onboarding_model import OnboardingStepUpdate
from config.db_config import *
from core.utils.response_mixin import CustomResponseMixin
from core.utils.helper import serialize_datetime_fields
from services.translation import translate_message
from api.controller.files_controller import save_file
from config.models.user_models import Files
from api.controller.onboardingController import *
from core.auth import get_current_user

router = APIRouter()
response = CustomResponseMixin()

@router.get("/onboarding/profile")
async def fetch_onboarding(
    current_user: dict = Depends(get_current_user),
):
    """
    Fetch the onboarding profile of the authenticated user.

    Workflow:
    ----------
    1. Authenticate user
       - Extracts user_id from the access token.
       - Returns 401 error if user_id is missing or invalid.

    2. Retrieve onboarding data
       - Fetches the onboarding document from `onboarding_collection`
         using the authenticated user's ID.
       - If no onboarding document exists → returns 404.

    3. Format onboarding response
       - Calls `format_onboarding_response()` to:
            * Replace image IDs with objects: {file_id, url}
            * Replace selfie image ID with: {file_id, url}
            * Generate publicly accessible URL using storage_key
            * Remove internal fields like user_id
            * Attach timestamps and other onboarding fields
    """
    lang = current_user.get("language", "en")
    user_id = str(current_user.get("_id"))

    if not user_id:
        raise HTTPException(401, "Invalid user")

    data = await get_onboarding(user_id)
    if not data:
        return response.raise_exception(
            message=translate_message("ONBOARDING_NOT_FOUND", lang),
            status_code=404
        )

    formatted = await format_onboarding_response(data)

    formatted = serialize_datetime_fields(formatted)

    return response.success_message(
        translate_message("ONBOARDING_FETCHED", lang),
        data=[formatted]
    )



@router.post("/onboarding/add-details")
async def handle_onboarding(
    payload: OnboardingStepUpdate,
    current_user: dict = Depends(get_current_user),
):
    user_id = str(current_user["_id"])
    lang = current_user.get("language", "en")

    if not user_id:
        return response.raise_exception(
            translate_message("INVALID_USER", lang),
            status_code=401
        )

    payload_dict = payload.model_dump(exclude_unset=True)

    return await save_onboarding_step(
        user_id=user_id,
        payload=payload_dict,
        lang=lang
    )


@router.get("/user/basic-profile/{user_id}")
async def get_basic_user_profile_route(
    user_id: str,
    current_user: dict = Depends(get_current_user)
):
    lang = current_user.get("language", "en")
    return await get_basic_user_profile(user_id=user_id, lang=lang)


@router.post("/onboarding/add-images")
async def upload_images(
    images: List[UploadFile] = File(...),
    current_user: dict = Depends(get_current_user),
):
    return await upload_onboarding_images(
        images=images,
        current_user=current_user
    )


@router.post("/onboarding/upload-selfie")
async def upload_selfie(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    return await upload_onboarding_selfie(
        file=file,
        current_user=current_user
    )

@router.get("/onboarding/steps")
async def get_onboarding_steps(
    current_user: dict = Depends(get_current_user),
    lang: str = "en"
):
    return await get_onboarding_steps_by_user_id(
        user_id=str(current_user["_id"]),
        lang=lang
    )

@router.get("/country-list")
async def get_country_list(
    current_user: dict = Depends(get_current_user),
    lang: str = "en"
):
    return await list_of_country(lang=lang)

 
@router.get("/intrest-category-list")
async def get_intrest_categories(
    current_user: dict = Depends(get_current_user),
    lang: str = "en"
):
    return await intrest_and_categories(lang=lang)

