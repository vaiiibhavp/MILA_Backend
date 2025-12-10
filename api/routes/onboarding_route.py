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
from services.lists import sexual_preferences , passions , city
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
    """
    API wrapper for get_basic_user_profile()
    Returns response using success_message() helper.
    """

    lang = current_user.get("language", "en")

    data = await get_basic_user_profile(user_id)

    # Serialize datetime safely (age is int so safe)
    serialized = serialize_datetime_fields(data)

    return response.success_message(
        translate_message("USER_BASIC_PROFILE", lang),
        data=serialized
    )

@router.post("/onboarding/add-images")
async def upload_image(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """
    Upload a gallery image for the user's onboarding profile.

    Purpose:
    ----------
    Allows the authenticated user to upload one onboarding gallery image.
    Each upload returns file metadata including file_id and a public URL.
    These file IDs must later be sent in `/onboarding/add-details` as
    `"images": ["fileId1", "fileId2", ...]`.

    Workflow:
    ----------
    1. Authenticate user:
       - Extracts user_id from JWT.
       - If invalid, FastAPI will block the request before reaching controller.

    2. Save file to storage (LOCAL or S3):
       - Uses `save_file()` helper.
       - Generates:
            * `public_url`: URL accessible by client
            * `storage_key`: path inside storage system
            * backend (LOCAL / S3)

    3. Save metadata in file_collection:
       - Inserts a new document with:
            * storage_key
            * backend
            * file_type = "onboarding_image"
            * uploaded_by = user_id
            * uploaded_at timestamp

    4. Return upload result:
       {
           "message": "File uploaded successfully",
           "file_id": "<mongo_id>",
           "storage_key": "onboarding_image/<user>/<timestamp>.png",
           "url": "http://127.0.0.1:8080/uploads/onboarding_image/...png"
       }

    """

    lang = current_user.get("language", "en")
    user_id = str(current_user["_id"])

    public_url, storage_key, backend = await save_file(
        file_obj=file,
        file_name=file.filename,
        user_id=user_id,
        file_type="onboarding_image",
    )

    file_doc = Files(
        storage_key=storage_key,
        storage_backend=backend,
        file_type="onboarding_image",
        uploaded_by=user_id,
        uploaded_at=datetime.utcnow(),
    )

    inserted = await file_collection.insert_one(file_doc.model_dump(by_alias=True))
    file_id = str(inserted.inserted_id)

    response_data = serialize_datetime_fields({
        "file_id": file_id,
        "storage_key": storage_key,
        "url": public_url,
    })
    return response.success_message(
        translate_message("FILE_UPLOADED_SUCCESS", lang),
        data=response_data
    )


@router.post("/onboarding/upload-selfie")
async def upload_selfie(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    """
    Upload or replace the user's selfie image for onboarding verification.

    Purpose:
    ----------
    Handles uploading a selfie image that will be used for identity verification.
    A user may upload a selfie multiple times — the previous selfie (if any)
    is automatically soft-deleted (`is_deleted = True`).

    Workflow:
    ----------
    1. Authenticate user:
       - Extracts user_id from JWT.

    2. Fetch existing onboarding document:
       - Checks if the user already has a selfie stored.
       - If yes → old selfie file is soft-deleted after new upload.

    3. Save selfie image:
       - Uses `save_file()` helper.
       - Creates a storage_key inside `/selfie/<userid>/<timestamp>.ext`
       - Returns:
            * public_url
            * storage_key
            * backend

    4. Save metadata in file_collection:
       - Creates a new record with:
            * file_type = "selfie"
            * uploaded_by = user_id
            * uploaded_at timestamp

    5. Soft-delete the previous selfie:
       - If an old selfie exists → set `is_deleted: true`.

    6. Update onboarding document:
       - `selfie_image` field is set to the new file_id.
       - Upsert ensures the record is created if it doesn't exist yet.

    7. Response returned:
       {
           "message": "Selfie uploaded successfully",
           "file_id": "<mongo_file_id>",
           "storage_key": "selfie/<user>/<timestamp>.jpg",
           "url": "http://127.0.0.1:8080/uploads/selfie/...jpg"
       }
    """

    lang = current_user.get("language", "en")
    user_id = str(current_user["_id"])

    onboarding = await onboarding_collection.find_one({"user_id": user_id})
    old_selfie_id = onboarding.get("selfie_image") if onboarding else None

    public_url, storage_key, backend = await save_file(
        file_obj=file,
        file_name=file.filename,
        user_id=user_id,
        file_type="selfie",
    )

    file_doc = Files(
        storage_key=storage_key,
        storage_backend=backend,
        file_type="selfie",
        uploaded_by=user_id,
        uploaded_at=datetime.utcnow(),
    )

    inserted = await file_collection.insert_one(file_doc.model_dump(by_alias=True))
    new_file_id = str(inserted.inserted_id)

    if old_selfie_id:
        try:
            await file_collection.update_one(
                {"_id": ObjectId(old_selfie_id)},
                {"$set": {"is_deleted": True}}
            )
        except Exception:
            pass

    await onboarding_collection.update_one(
        {"user_id": user_id},
        {"$set": {"selfie_image": new_file_id}},
        upsert=True
    )

    response_data = serialize_datetime_fields({
        "file_id": new_file_id,
        "storage_key": storage_key,
        "url": public_url,
    })

    return response.success_message(
        translate_message("SELFIE_UPLOADED_SUCCESS", lang),
        data=response_data
    )

@router.get("/onboarding/sexual-preferences")
async def get_sexual_preferences(current_user: dict = Depends(get_current_user)):
    lang = current_user.get("language", "en")

    return response.success_message(
        translate_message("FETCH_SUCCESS", lang=lang),
        data={"sexual_preferences": sexual_preferences}
    )

@router.get("/onboarding/passions")
async def get_passions_list(current_user: dict = Depends(get_current_user)):
    lang = current_user.get("language", "en")

    return response.success_message(
        translate_message("FETCH_SUCCESS", lang=lang),
        data={"passions": passions}
    )

@router.get("/onboarding/city")
async def get_city(current_user:dict = Depends(get_current_user)):
    lang = current_user.get("language", "en")

    return response.success_message(
        translate_message("FETCH_SUCCESS" , lang=lang),
        data = {"city":city}
    )