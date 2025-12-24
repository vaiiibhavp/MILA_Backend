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
        data=formatted
    )



@router.post("/onboarding/add-details")
async def handle_onboarding(
    payload: OnboardingStepUpdate,
    current_user: dict = Depends(get_current_user),
):
    """
    Add or update onboarding details for the authenticated user.

    Workflow:
    ----------
    1. Validate authenticated user
       - Extracts the logged-in user's ID from JWT.
       - Returns 401 error if user is invalid.

    2. Validate incoming payload
       - Only updates fields that are present in the request (exclude_unset=True).
       
    3. Validate gallery images (if provided)
       - Ensures at least 1 and at most 3 images.
       - Ensures each image ID is a valid Mongo ObjectId.
       - Ensures each image exists inside the file_collection and is not deleted.

    4. Validate selfie image (if provided)
       - Ensures selfie ID is a valid Mongo ObjectId.
       - Ensures selfie image exists in file storage.

    5. Save onboarding data
       - Calls `save_onboarding_step()` to upsert (create/update) the onboarding record.
       - Converts date formats, enums, and sets created_at / updated_at timestamps.

    6. Format onboarding response
       - Replaces image IDs with objects: {file_id, url}.
       - Generates a public URL for each file using `generate_file_url()`.
       - Removes internal fields like user_id from the output.

    7. If onboarding is completed
       - Adds a success message at the top of the response:
         { "message": "Onboarding completed successfully.", ... }

    Returns:
    ----------
    A fully formatted onboarding profile including:
        - Basic details (bio, birthdate, gender, etc.)
        - Structured image list → { file_id, url }
        - Structured selfie image → { file_id, url }
        - created_at, updated_at timestamps
        - onboarding_completed flag
        - onboarding record id
    """
    lang = current_user.get("language", "en")
    user_id = str(current_user["_id"])
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid user")

    payload_dict = payload.model_dump(exclude_unset=True)

    if "images" in payload_dict:
        new_images = payload_dict.get("images") or []

        if len(new_images) != len(set(new_images)):
            raise HTTPException(400, "Duplicate image IDs are not allowed.")

        if len(new_images) < MIN_GALLERY_IMAGES:
            raise HTTPException(400, f"At least {MIN_GALLERY_IMAGES} image(s) required")

        if len(new_images) > MAX_GALLERY_IMAGES:
            raise HTTPException(400, f"Maximum {MAX_GALLERY_IMAGES} images allowed")

        for fid in new_images:
            if not ObjectId.is_valid(fid):
                raise HTTPException(400, f"Invalid image ID format: {fid}")

            file_doc = await file_collection.find_one(
                {"_id": ObjectId(fid), "is_deleted": False}
            )
            if not file_doc:
                raise HTTPException(400, f"Image not found in storage: {fid}")

    if "selfie_image" in payload_dict and payload_dict["selfie_image"]:
        selfie_id = payload_dict["selfie_image"]

        if not ObjectId.is_valid(selfie_id):
            raise HTTPException(400, f"Invalid selfie image ID: {selfie_id}")

        selfie_doc = await file_collection.find_one(
            {"_id": ObjectId(selfie_id), "is_deleted": False}
        )
        if not selfie_doc:
            raise HTTPException(400, f"Selfie image not found: {selfie_id}")

        if "images" in payload_dict and selfie_id in payload_dict.get("images", []):
            raise HTTPException(400, "Selfie image cannot be added to gallery images.")

    updated_doc = await save_onboarding_step(user_id, payload_dict)

    if isinstance(updated_doc, list) and len(updated_doc) > 0:
        updated_doc = updated_doc[0]

    formatted = await format_onboarding_response(updated_doc)

    response_data = serialize_datetime_fields({
        "onboarding_completed": updated_doc.get("onboarding_completed", False),
        "onboarding": formatted
    })

    return response.success_message(
        translate_message("ONBOARDING_SAVED", lang),
        data=response_data
    )


@router.get("/user/basic-profile/{user_id}")
async def get_basic_user_profile_route(
    user_id: str,
    current_user: dict = Depends(get_current_user)
):
    lang = current_user.get("language", "en")
    return await get_basic_user_profile(user_id=user_id, lang=lang)


@router.post("/onboarding/add-images")
async def upload_image(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    return await upload_onboarding_image(
        file=file,
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

