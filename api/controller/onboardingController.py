from datetime import datetime, date
from enum import Enum
from typing import Dict, Any, List, Optional

from bson import ObjectId
from fastapi import HTTPException
from pymongo import ReturnDocument

from config.db_config import (
    onboarding_collection,
    file_collection,
    user_collection,
    countries_collection,
    interest_categories_collection
)
from core.utils.response_mixin import CustomResponseMixin
from core.utils.helper import serialize_datetime_fields
from api.controller.files_controller import generate_file_url
from core.utils.helper import convert_objectid_to_str
from fastapi import HTTPException , status
from bson import ObjectId
from datetime import datetime
from core.utils.response_mixin import CustomResponseMixin
from fastapi import UploadFile
from api.controller.files_controller import save_file
from config.models.user_models import Files
from core.utils.helper import serialize_datetime_fields
from services.translation import translate_message
from core.utils.age_calculation import calculate_age

response = CustomResponseMixin()

MIN_GALLERY_IMAGES = 1
MAX_GALLERY_IMAGES = 3


response = CustomResponseMixin()

def normalize_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    ## Use inbuild function for this 
    """
    Convert Enum values into formats that can be stored in MongoDB.
    """
    for key, value in list(payload.items()):
        if isinstance(value, date):
            payload[key] = datetime.combine(value, datetime.min.time())

        elif isinstance(value, Enum):
            payload[key] = value.value

        elif isinstance(value, list):
            payload[key] = [
                v.value if isinstance(v, Enum) else v
                for v in value
            ]
    return payload

async def get_onboarding(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Get raw onboarding document for the user (no formatting).
    """
    data = await onboarding_collection.find_one({"user_id": user_id})
    return convert_objectid_to_str(data) if data else None


async def save_onboarding_step(user_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    payload = normalize_payload(payload)
    payload["updated_at"] = datetime.utcnow()

    set_on_insert = {
        "user_id": user_id,
        "created_at": datetime.utcnow(),
        "onboarding_completed": False,
    }

    doc = await onboarding_collection.find_one_and_update(
        {"user_id": user_id},
        {"$set": payload, "$setOnInsert": set_on_insert},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )

    if not doc:
        raise HTTPException(500, "Unable to save onboarding data")

    REQUIRED_FIELDS = [
        "birthdate", "gender", "sexual_orientation", "marital_status", "country",
        "passions", "interested_in", "preferred_country",
        "images", "selfie_image"
    ]

    all_filled = True

    for key in REQUIRED_FIELDS:
        value = doc.get(key)

        if value is None:
            all_filled = False
            break

        if isinstance(value, list) and len(value) == 0:
            all_filled = False
            break

    if all_filled and not doc.get("onboarding_completed"):
        doc = await onboarding_collection.find_one_and_update(
            {"_id": doc["_id"]},
            {"$set": {"onboarding_completed": True}},
            return_document=ReturnDocument.AFTER,
        )

    return convert_objectid_to_str(doc)

async def format_onboarding_response(onboarding_doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format onboarding data by replacing file IDs with full file metadata (file_id + url).

    Purpose:
    ----------
    The onboarding document stores only file IDs for gallery images and
    selfie image. This function enriches the response by converting each
    file ID into:
        {
            "file_id": "<mongo_id>",
            "url": "<public_accessible_url>"
        }

    This makes the response frontend-ready.

    Workflow:
    ----------
    1. Process gallery images:
        - Loop through onboarding_doc["images"]
        - Fetch corresponding file documents
        - Generate a public URL using storage_key and backend
        - Build final list:
            [
                { "file_id": "...", "url": "..." },
                ...
            ]

    2. Process selfie image:
        - Fetch selfie file document
        - Generate selfie's public URL
        - Build:
            { "file_id": "...", "url": "..." }

    3. Serialize base onboarding document:
        - Convert _id to id
        - Remove internal fields (user_id)

    4. Overlay enriched image fields:
        - Replace image ID list with structured data
        - Replace selfie_image ID with object   
    """

    if isinstance(onboarding_doc, list) and len(onboarding_doc) == 1 and isinstance(onboarding_doc[0], dict):
        onboarding_doc = onboarding_doc[0]

    images_out: List[Dict[str, str]] = []

    for fid in onboarding_doc.get("images", []):
        if not fid:
            continue
        try:
            file_doc = await file_collection.find_one(
                {"_id": ObjectId(fid), "is_deleted": False}
            )
        except Exception:
            # invalid ObjectId in DB – skip
            continue

        if file_doc:
            url = await generate_file_url(
                storage_key=file_doc["storage_key"],
                backend=file_doc["storage_backend"],
            )
            images_out.append({"file_id": str(file_doc["_id"]), "url": url})

    selfie_out = None
    selfie_id = onboarding_doc.get("selfie_image")

    if selfie_id:
        try:
            selfie_doc = await file_collection.find_one(
                {"_id": ObjectId(selfie_id), "is_deleted": False}
            )
        except Exception:
            selfie_doc = None

        if selfie_doc:
            selfie_out = {
                "file_id": str(selfie_doc["_id"]),
                "url": await generate_file_url(
                    storage_key=selfie_doc["storage_key"],
                    backend=selfie_doc["storage_backend"],
                ),
            }

    response = convert_objectid_to_str(onboarding_doc)

    if isinstance(response, list) and len(response) == 1 and isinstance(response[0], dict):
        response = response[0]

    response["images"] = images_out
    response["selfie_image"] = selfie_out

    return response

async def get_basic_user_profile(user_id: str, lang: str = "en") -> Dict[str, Any]:
    """
    Basic profile for list views:
      - username
      - bio
      - age
      - country
      - interested_in
    """
    try:
        onboarding_data = await onboarding_collection.find_one(
            {"user_id": user_id},
            {
                "_id": 0,
                "bio": 1,
                "birthdate": 1,
                "country": 1,
                "interested_in": 1,
            },
        )

        if not onboarding_data:
            return response.raise_exception(
                translate_message("FAILED_TO_FETCH_USER_DETAILS", lang),
                data=[],
                status_code=404
            )

        try:
            user = await user_collection.find_one(
                {"_id": ObjectId(user_id)},
                {"_id": 0, "username": 1},
            )
        except Exception:
            return response.raise_exception(
                translate_message("INVALID_USER_ID", lang),
                data=[],
                status_code=400
            )

        username = user.get("username") if user else None

        birthdate_value = onboarding_data.get("birthdate")
        age = None
        if birthdate_value:
            dob = (
                birthdate_value.date()
                if isinstance(birthdate_value, datetime)
                else birthdate_value
            )
            age = calculate_age(dob)

        profile = serialize_datetime_fields({
            "username": username,
            "bio": onboarding_data.get("bio"),
            "age": age,
            "country": onboarding_data.get("country"),
            "interested_in": onboarding_data.get("interested_in"),
        })

        return response.success_message(
            translate_message("USER_BASIC_PROFILE", lang),
            data=[profile]
        )

    except Exception as e:
        return response.raise_exception(
            translate_message("ERROR_WHILE_FETCHING_USER_PROFILE", lang),
            data=str(e),
            status_code=500
        )

async def get_onboarding_details(
    condition: Dict[str, Any],
    fields: Optional[List[str]] = None
):
    projection = None
    if fields:
        projection = {field: 1 for field in fields}
        if "_id" not in fields:
            projection["_id"] = 0

    return await onboarding_collection.find_one(condition, projection)


async def get_onboarding_steps_by_user_id(user_id: str, lang: str = "en"):
    onboarding = await get_onboarding_details(
        condition={"user_id": user_id},
        fields=[
            "birthdate",
            "gender",
            "sexual_orientation",
            "bio",
            "passions",
            "country",
            "preferred_country",
            "interested_in",
            "marital_status",
            "sexual_preferences",
            "images",
            "selfie_image", 
            "onboarding_completed"
        ]
    )

    if not onboarding:
        return response.error_message(
            translate_message("ONBOARDING_NOT_FOUND", lang),
            data=[],
            status_code=404
        )

    def serialize(value):
        return value.isoformat() if hasattr(value, "isoformat") else value

    steps = [
        {"key": "birthdate", "value": serialize(onboarding.get("birthdate"))},
        {"key": "gender", "value": onboarding.get("gender")},
        {"key": "sexual_orientation", "value": onboarding.get("sexual_orientation")},
        {"key": "bio", "value": onboarding.get("bio")},
        {"key": "passions", "value": onboarding.get("passions", [])},
        {"key": "country", "value": onboarding.get("country")},
        {"key": "preferred_country", "value": onboarding.get("preferred_country", [])},
        {"key": "interested_in", "value": onboarding.get("interested_in", [])},
        {"key": "marital_status", "value": onboarding.get("marital_status")},
        {"key": "sexual_preferences", "value": onboarding.get("sexual_preferences", [])},
        {"key": "images", "value": onboarding.get("images", [])},
        {"key": "selfie_image", "value": onboarding.get("selfie_image")},
    ]

    return response.success_message(
        translate_message("ONBOARDING_STEPS_FETCHED", lang),
        data=[{
            "user_id": user_id,
            "onboarding_completed": onboarding.get("onboarding_completed", False),
            "steps": steps
        }]
    )


async def list_of_country(lang: str = "en"):
    try:
        total = await countries_collection.count_documents({})

        if total == 0:
            return response.success_message(
                translate_message("NO_COUNTRIES_FOUND", lang),
                data=[{
                    "count": 0,
                    "results": []
                }]
            )

        cursor = countries_collection.find(
            {},
            {"name": 1, "code": 1}
        ).sort("name", 1)

        countries = await cursor.to_list(length=None)

        results = [
            {
                "id": str(c["_id"]),
                "name": c.get("name"),
                "code": c.get("code")
            }
            for c in countries
        ]

        return response.success_message(
            translate_message("COUNTRY_LIST_FETCHED", lang),
            data=[{
                "count": len(results),
                "results": results
            }]
        )

    except Exception as e:
        return response.raise_exception(
            translate_message("ERROR_WHILE_FETCHING_COUNTRY_LIST", lang),
            data=str(e),
            status_code=500
        )

 
async def intrest_and_categories(lang: str = "en"):
    try:
        cursor = interest_categories_collection.find(
            {},
            {"category": 1, "options": 1}
        )

        data = await cursor.to_list(length=None)

        results = [
            {
                "id": str(item["_id"]),
                "category": item.get("category"),
                "options": item.get("options", [])
            }
            for item in data
        ]

        return response.success_message(
            translate_message("INTEREST_CATEGORIES_FETCHED", lang),
            data=[{
                "count": len(results),
                "results": results
            }]
        )

    except Exception as e:
        return response.raise_exception(
            translate_message("ERROR_WHILE_FETCHING_INTEREST_CATEGORIES", lang),
            data=str(e),
            status_code=500
        )



async def fetch_user_by_id(user_id: str, lang: str):
    try:
        user_data = await onboarding_collection.find_one(
            {"user_id": user_id},
            {
                "_id": 0,
                "bio": 1,
                "passions": 1,
                "country": 1,
                "birthdate": 1,
                "tokens": 1,
            }
        )

        if not user_data:
            return response.raise_exception(
                translate_message("FAILED_TO_FETCH_USER_DETAILS", lang),
                data=[],
                status_code=500
            )

        user = await user_collection.find_one(
            {"_id": ObjectId(user_id)},
            {
                "_id": 0,
                "username": 1,
                "is_verified": 1,
                "profile_photo_id": 1,
                "login_status": 1
            }
        )

        if not user:
            return response.raise_exception(
                translate_message("USER_NOT_FOUND", lang),
                data=[],
                status_code=404
            )

        # Age calculation
        age = None
        if user_data.get("birthdate"):
            dob = (
                user_data["birthdate"].date()
                if hasattr(user_data["birthdate"], "date")
                else user_data["birthdate"]
            )
            age = calculate_age(dob)

        # Profile photo
        profile_photo = None
        if user.get("profile_photo_id"):
            file_doc = await file_collection.find_one(
                {"_id": ObjectId(user["profile_photo_id"])},
                {"storage_key": 1, "storage_backend": 1}
            )

            if file_doc:
                url = await generate_file_url(
                    storage_key=file_doc["storage_key"],
                    backend=file_doc.get("storage_backend")
                )
                profile_photo = {
                    "id": str(file_doc["_id"]),
                    "url": url
                }

        return serialize_datetime_fields({
            "user_id": user_id,
            "username": user.get("username"),
            "is_verified": user.get("is_verified"),
            "status": user.get("login_status"),
            "bio": user_data.get("bio"),
            "age": age,
            "country": user_data.get("country"),
            "tokens": user_data.get("tokens"),
            "passions": user_data.get("passions"),
            "profile_photo": profile_photo
        })

    except Exception as e:
        return response.raise_exception(
            translate_message("ERROR_WHILE_FETCHING_USER_DETAILS", lang),
            data=str(e),
            status_code=500
        )

async def upload_onboarding_image(
    file: UploadFile,
    current_user: dict
):
    try:
        lang = current_user.get("language", "en")
        user_id = str(current_user["_id"])

        public_url, storage_key, backend = await save_file(
            file_obj=file,
            file_name=file.filename,
            user_id=user_id,
            file_type="profile_photo",
        )

        file_doc = Files(
            storage_key=storage_key,
            storage_backend=backend,
            file_type="profile_photo",
            uploaded_by=user_id,
            uploaded_at=datetime.utcnow(),
        )

        inserted = await file_collection.insert_one(
            file_doc.model_dump(by_alias=True)
        )

        response_data = serialize_datetime_fields({
            "file_id": str(inserted.inserted_id),
            "storage_key": storage_key,
            "url": public_url,
        })

        return response.success_message(
            translate_message("FILE_UPLOADED_SUCCESS", lang),
            data=[response_data],
            status_code=200
        )

    except Exception as e:
        return response.raise_exception(
            translate_message("ERROR_WHILE_UPLOADING_FILE", lang),
            data=str(e),
            status_code=500
        )

async def upload_onboarding_selfie(
    file: UploadFile,
    current_user: dict
):
    try:
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

        inserted = await file_collection.insert_one(
            file_doc.model_dump(by_alias=True)
        )
        new_file_id = str(inserted.inserted_id)

        # Soft delete old selfie
        if old_selfie_id:
            await file_collection.update_one(
                {"_id": ObjectId(old_selfie_id)},
                {"$set": {"is_deleted": True}}
            )

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
            data=[response_data],
            status_code=200
        )

    except Exception as e:
        return response.raise_exception(
            translate_message("ERROR_WHILE_UPLOADING_SELFIE", lang),
            data=str(e),
            status_code=500
        )
