#services/gallery_service.py

from bson import ObjectId
from config.db_config import file_collection
from api.controller.files_controller import generate_file_url, save_file
from datetime import datetime
from config.models.user_models import Files, FileType
from config.db_config import onboarding_collection
from core.utils.response_mixin import CustomResponseMixin
from fastapi import UploadFile
from services.translation import translate_message
from config.basic_config import settings

response = CustomResponseMixin()

async def validate_image_size(file: UploadFile, lang: str):
    file.file.seek(0, 2)
    size = file.file.tell()
    file.file.seek(0)

    if size > settings.MAX_IMAGE_SIZE_BYTES:
        return response.error_message(
            translate_message(
                "IMAGE_SIZE_EXCEEDS_THE_ALLOWED_LIMIT_(5MB)",
                lang=lang
            ),
            status_code=400
        )
    return None

async def resolve_gallery_items(gallery: list):
    """
    Converts gallery file_ids into URLs
    """
    resolved = []

    for item in gallery:
        file_id = item.get("file_id")
        if not file_id:
            continue

        file_doc = await file_collection.find_one(
            {"_id": ObjectId(file_id), "is_deleted": {"$ne": True}}
        )
        if not file_doc:
            continue

        url = await generate_file_url(
            storage_key=file_doc["storage_key"],
            backend=file_doc["storage_backend"]
        )

        resolved.append({
            "file_id": file_id,
            "url": url,
            "uploaded_at": item.get("uploaded_at"),
            "price": item.get("price")
        })

    return resolved

async def create_and_store_file(
    file_obj,
    user_id: str,
    file_type: FileType
):
    """
    Saves file physically + stores DB record
    Returns: file_id, uploaded_at
    """
    _, storage_key, backend = await save_file(
        file_obj=file_obj,
        file_name=file_obj.filename,
        user_id=user_id,
        file_type=file_type.value
    )

    file_doc = Files(
        storage_key=storage_key,
        storage_backend=backend,
        file_type=file_type,
        uploaded_by=user_id
    )

    result = await file_collection.insert_one(file_doc.dict(by_alias=True))

    return {
        "file_id": str(result.inserted_id),
        "uploaded_at": datetime.utcnow()
    }

async def append_gallery_items(
    user_id: str,
    gallery_field: str,
    items: list
):
    await onboarding_collection.update_one(
        {"user_id": user_id},
        {
            "$push": {gallery_field: {"$each": items}},
            "$setOnInsert": {
                "user_id": user_id,
                "created_at": datetime.utcnow()
            },
            "$set": {"updated_at": datetime.utcnow()}
        },
        upsert=True
    )