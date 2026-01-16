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
from core.utils.core_enums import MembershipType
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


async def save_onboarding_step(
    user_id: str,
    payload: Dict[str, Any],
    lang: str = "en"
):
    REQUIRED_FIELDS = [
        "birthdate",
        "gender",
        "sexual_orientation",
        "marital_status",
        "country",
        "passions",
        "interested_in",
        "preferred_country",
        "images",
        "selfie_image"
    ]

    payload = normalize_payload(payload)
    payload["updated_at"] = datetime.utcnow()

    user_doc = await user_collection.find_one(
        {"_id": ObjectId(user_id)},
        {"membership_type": 1}
    )

    if not user_doc:
        return response.raise_exception(
            translate_message("INVALID_USER", lang),
            data=[],
            status_code=401
        )

    membership_type = user_doc.get("membership_type",MembershipType.FREE.value)
    is_premium_user = membership_type == MembershipType.PREMIUM.value

    if not is_premium_user and "sexual_preferences" in payload:
        return response.raise_exception(
            translate_message("SEXUAL_PREFERENCES_PREMIUM_ONLY", lang),
            data=[],
            status_code=403
        )

    if "images" in payload:
        images = payload.get("images") or []

        if len(images) != len(set(images)):
            return response.raise_exception(
                translate_message("DUPLICATE_IMAGE_IDS", lang),
                data=[images],
                status_code=400
            )

        if len(images) < MIN_GALLERY_IMAGES:
            return response.raise_exception(
                translate_message("MIN_IMAGES_REQUIRED", lang),
                data=[],
                status_code=400
            )

        if len(images) > MAX_GALLERY_IMAGES:
            return response.raise_exception(
                translate_message("MAX_IMAGES_EXCEEDED", lang),
                data=[],
                status_code=400
            )

        for fid in images:
            if not ObjectId.is_valid(fid):
                return response.raise_exception(
                    translate_message("INVALID_IMAGE_ID", lang),
                    data=[],
                    status_code=400
                )

            if not await file_collection.find_one(
                {"_id": ObjectId(fid), "is_deleted": False}
            ):
                return response.raise_exception(
                    translate_message("IMAGE_NOT_FOUND", lang),
                    data=[],
                    status_code=400
                )

        payload["images"] = images

        # -------- ADD IMAGES TO PUBLIC GALLERY --------
        existing_doc = await onboarding_collection.find_one(
            {"user_id": user_id},
            {"public_gallery": 1}
        )

        existing_gallery = (
            existing_doc.get("public_gallery", [])
            if existing_doc else []
        )

        existing_file_ids = {
            item.get("file_id") for item in existing_gallery
        }

        new_gallery_items = [
            {
                "file_id": fid,
                "uploaded_at": datetime.utcnow()
            }
            for fid in images
            if fid not in existing_file_ids
        ]

        payload["public_gallery"] = existing_gallery + new_gallery_items

    # --------------------------------------------------
    # COUNTRY VALIDATION
    # --------------------------------------------------
    if payload.get("country"):
        cid = payload["country"]

        if not ObjectId.is_valid(cid):
            return response.raise_exception(
                translate_message("INVALID_COUNTRY_ID", lang),
                data=[],
                status_code=400
            )

        if not await countries_collection.find_one({"_id": ObjectId(cid)}):
            return response.raise_exception(
                translate_message("COUNTRY_NOT_FOUND", lang),
                data=[],
                status_code=400
            )

        payload["country"] = cid

    if payload.get("preferred_country"):
        preferred = payload["preferred_country"]

        if not isinstance(preferred, list):
            return response.raise_exception(
                translate_message("PREFERRED_COUNTRY_MUST_BE_LIST", lang),
                data=[],
                status_code=400
            )

        unique_ids = set(preferred)

        for cid in unique_ids:
            if not ObjectId.is_valid(cid):
                return response.raise_exception(
                    translate_message("INVALID_COUNTRY_ID", lang),
                    data=[],
                    status_code=400
                )

        count = await countries_collection.count_documents({
            "_id": {"$in": [ObjectId(cid) for cid in unique_ids]}
        })

        if count != len(unique_ids):
            return response.raise_exception(
                translate_message("PREFERRED_COUNTRY_NOT_FOUND", lang),
                data=[],
                status_code=400
            )

        payload["preferred_country"] = list(unique_ids)

    if payload.get("selfie_image"):
        fid = payload["selfie_image"]

        if not ObjectId.is_valid(fid):
            return response.raise_exception(
                translate_message("INVALID_IMAGE_ID", lang),
                data=[],
                status_code=400
            )

        payload["selfie_image"] = fid

    doc = await onboarding_collection.find_one_and_update(
        {"user_id": user_id},
        {
            "$set": payload,
            "$setOnInsert": {
                "user_id": user_id,
                "created_at": datetime.utcnow(),
                "onboarding_completed": False,
            }
        },
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )

    if not doc:
        return response.raise_exception(
            translate_message("ONBOARDING_SAVE_FAILED", lang),
            data=[],
            status_code=500
        )

    completed = True
    for field in REQUIRED_FIELDS:
        if field not in doc or doc.get(field) in (None, "", []):
            completed = False
            break

    if completed and len(doc.get("images", [])) < MIN_GALLERY_IMAGES:
        completed = False

    if completed and not doc.get("onboarding_completed"):
        await onboarding_collection.update_one(
            {"_id": doc["_id"]},
            {"$set": {"onboarding_completed": True}}
        )
        doc["onboarding_completed"] = True

    formatted = await format_onboarding_response(doc)

    return response.success_message(
        translate_message("ONBOARDING_SAVED", lang),
        data=[
            serialize_datetime_fields({
                "onboarding_completed": doc.get("onboarding_completed", False),
                "onboarding": formatted
            })
        ]
    )

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
    try:
        if not ObjectId.is_valid(user_id):
            return response.raise_exception(
                translate_message("INVALID_USER_ID", lang),
                data=[],
                status_code=400
            )

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

        user = await user_collection.find_one(
            {"_id": ObjectId(user_id)},
            {"_id": 0, "username": 1},
        )

        if not user:
            return response.raise_exception(
                translate_message("USER_NOT_FOUND", lang),
                data=[],
                status_code=404
            )

        username = user.get("username")

        birthdate_value = onboarding_data.get("birthdate")
        age = None
        if birthdate_value:
            dob = (
                birthdate_value.date()
                if isinstance(birthdate_value, datetime)
                else birthdate_value
            )
            age = calculate_age(dob)

        country_out = None
        country_id = onboarding_data.get("country")

        if country_id and ObjectId.is_valid(country_id):
            country_doc = await countries_collection.find_one(
                {"_id": ObjectId(country_id)},
                {"_id": 1, "name": 1}
            )

            if country_doc:
                country_out = {
                    "id": str(country_doc["_id"]),
                    "name": country_doc.get("name"),
                }

        profile = {
            "username": username,
            "bio": onboarding_data.get("bio"),
            "age": age,
            "country": country_out,
            "interested_in": onboarding_data.get("interested_in"),
        }

        return response.success_message(
            translate_message("USER_BASIC_PROFILE", lang),
            data=[profile]
        )

    except HTTPException:
        raise

    except Exception as e:
        return response.raise_exception(
            translate_message("ERROR_WHILE_FETCHING_USER_PROFILE", lang),
            data={},
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

    formatted = await format_onboarding_response(onboarding)

    country_out = None
    country_id = formatted.get("country")

    if country_id:
        try:
            country_doc = await countries_collection.find_one(
                {"_id": ObjectId(country_id)}
            )
        except Exception:
            country_doc = None

        if country_doc:
            country_out = {
                "id": str(country_doc["_id"]),
                "name": country_doc.get("name")
            }

    preferred_country_out = []
    preferred_ids = formatted.get("preferred_country", [])

    if preferred_ids:
        cursor = countries_collection.find(
            {"_id": {"$in": [ObjectId(cid) for cid in preferred_ids if ObjectId.is_valid(cid)]}}
        )
        async for doc in cursor:
            preferred_country_out.append({
                "id": str(doc["_id"]),
                "name": doc.get("name")
            })

    def serialize(value):
        return value.isoformat() if hasattr(value, "isoformat") else value

    steps = [
        {"key": "birthdate", "value": serialize(formatted.get("birthdate"))},
        {"key": "gender", "value": formatted.get("gender")},
        {"key": "sexual_orientation", "value": formatted.get("sexual_orientation")},
        {"key": "bio", "value": formatted.get("bio")},
        {"key": "passions", "value": formatted.get("passions", [])},

        {"key": "country", "value": country_out},
        {"key": "preferred_country", "value": preferred_country_out},

        {"key": "interested_in", "value": formatted.get("interested_in", [])},
        {"key": "marital_status", "value": formatted.get("marital_status")},
        {"key": "sexual_preferences", "value": formatted.get("sexual_preferences", [])},

        {"key": "images", "value": formatted.get("images", [])},
        {"key": "selfie_image", "value": formatted.get("selfie_image")},
    ]

    return response.success_message(
        translate_message("ONBOARDING_STEPS_FETCHED", lang),
        data=[{
            "user_id": user_id,
            "onboarding_completed": formatted.get("onboarding_completed", False),
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
                "images": 1,
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
        
        country_data = None
        country_id = user_data.get("country")

        if country_id:
            country_doc = await countries_collection.find_one(
                {"_id": ObjectId(country_id)},
                {"name": 1}
            )

            if country_doc:
                country_data = {
                    "id": str(country_doc["_id"]),
                    "name": country_doc.get("name")
                }
        
        # Profile photo
        profile_photo = None
        images = user_data.get("images", [])

        if images:
            first_image_id = images[0]

            file_doc = await file_collection.find_one(
                {"_id": ObjectId(first_image_id)},
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
            "country": country_data, 
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

async def upload_onboarding_images(
    images: List[UploadFile],
    current_user: dict
):
    try:
        lang = current_user.get("language", "en")
        user_id = str(current_user["_id"])

        uploaded_files = []

        for file in images:
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

            uploaded_files.append(
                serialize_datetime_fields({
                    "file_id": str(inserted.inserted_id),
                    "storage_key": storage_key,
                    "url": public_url,
                })
            )

        return response.success_message(
            translate_message("FILE_UPLOADED_SUCCESS", lang),
            data=[uploaded_files],
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

async def update_profile_image_onboarding(
    image: UploadFile,
    current_user: dict
):
    try:
        lang = current_user.get("language", "en")
        user_id = str(current_user["_id"])

        # ---------------- SAVE FILE ----------------
        public_url, storage_key, backend = await save_file(
            file_obj=image,
            file_name=image.filename,
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

        new_file_id = str(inserted.inserted_id)

        # ---------------- FETCH ONBOARDING ----------------
        onboarding = await onboarding_collection.find_one(
            {"user_id": user_id},
            {"images": 1}
        )

        if not onboarding:
            return response.error_message(
                translate_message("ONBOARDING_NOT_FOUND", lang),
                status_code=404
            )

        images = onboarding.get("images", [])

        # ---------------- UPDATE 0th INDEX ----------------
        if images:
            images[0] = new_file_id
        else:
            images = [new_file_id]

        # ---------------- UPDATE ONBOARDING ----------------
        await onboarding_collection.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "images": images,
                    "updated_at": datetime.utcnow()
                }
            }
        )

        # ---------------- RESPONSE ----------------
        return response.success_message(
            translate_message("PROFILE_IMAGE_UPDATED", lang),
            data={
                "file_id": new_file_id,
                "storage_key": storage_key,
                "url": public_url
            },
            status_code=200
        )

    except Exception as e:
        return response.raise_exception(
            translate_message("ERROR_WHILE_UPLOADING_FILE", lang),
            data=str(e),
            status_code=500
        )
