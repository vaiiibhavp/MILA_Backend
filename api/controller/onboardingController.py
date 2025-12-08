from datetime import datetime
from bson import ObjectId
from pymongo import ReturnDocument
from config.db_config import onboarding_collection , file_collection
from datetime import datetime, date
from api.controller.files_controller import *
from enum import Enum
from pymongo import ReturnDocument

def serialize(data):
    """
    Convert a MongoDB document into a clean JSON-serializable dictionary.

    Purpose:
    ----------
    MongoDB stores document identifiers under `_id` using `ObjectId`,
    which is not JSON serializable. This utility function standardizes the
    document format before sending it to the client by converting `_id` to a
    string-based `id` field and removing internal fields.

    Workflow:
    ----------
    1. Handle empty input:
       - If the document is None or empty → return {} instead of failing.

    2. Convert `_id` → `id`:
       - If `_id` exists:
           * Convert `_id` (ObjectId) to a string.
           * Assign it to a new field: `id`.
           * Remove the original `_id` field.

    3. Handle repeated serialization:
       - If `_id` was already removed and `id` exists:
         Convert `id` to string again to ensure consistent formatting.

    4. Remove internal fields:
       - Removes `user_id` from output so it is never exposed to the frontend
         even though it remains stored internally in MongoDB.

    """
    if not data:
        return {}

    if "_id" in data:
        data["_id"] = str(data["_id"])
        data["id"] = data["_id"]
        del data["_id"]

    elif "id" in data:
        data["id"] = str(data["id"])

    if "user_id" in data:
        del data["user_id"]

    return data


async def get_onboarding(user_id: str):
    """
    Retrieve the onboarding document for a given user.

    Purpose:
    ----------
    Fetches the onboarding record associated with the provided user_id.
    Used by the GET onboarding profile route to load onboarding details.

    Workflow:
    ----------
    1. Query the onboarding_collection for a document matching user_id.
    2. If found → serialize the MongoDB document (convert _id → id, remove user_id).
    3. If not found → return None.

    Returns:
    ----------
    - A serialized onboarding document, or
    - None if the user has not started onboarding.

    Example Output:
    ----------
    {
        "id": "69366e98efc708ded7ddb826",
        "bio": "...",
        "images": ["fileId1", "fileId2"],
        ...
    }
    """
    data = await onboarding_collection.find_one({"user_id": user_id})
    return serialize(data) if data else None


async def save_onboarding_step(user_id: str, payload: dict):
    """
    Save or update onboarding fields for the user.

    Purpose:
    ----------
    Handles partial updates for onboarding (step-by-step saving).
    Converts date and Enum fields into proper stored formats, applies
    timestamps, and upserts the onboarding document.

    Workflow:
    ----------
    1. Normalize payload values:
        - Convert datetime.date → datetime
        - Convert Enum values → string
        - Convert list of Enums → list of strings

    2. Add/update timestamps:
        - updated_at is always refreshed
        - created_at is set only when inserting a new onboarding document

    3. Upsert onboarding document:
        - If onboarding exists → update fields
        - If onboarding does not exist → create a new record

    4. Serialize result before returning:
        - Converts _id to id
        - Removes internal fields (user_id)
    """

    for key, value in payload.items():
        if isinstance(value, date):
            payload[key] = datetime.combine(value, datetime.min.time())

        elif isinstance(value, Enum):
            payload[key] = value.value

        elif isinstance(value, list):
            payload[key] = [
                v.value if isinstance(v, Enum) else v
                for v in value
            ]

    payload["updated_at"] = datetime.utcnow()

    result = await onboarding_collection.find_one_and_update(
        {"user_id": user_id},
        {
            "$set": payload,
            "$setOnInsert": {
                "user_id": user_id,
                "created_at": datetime.utcnow(),
            },
        },
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )

    return serialize(result)

async def complete_onboarding(user_id: str):
    result = await onboarding_collection.find_one_and_update(
        {"user_id": user_id},
        {"$set": {"onboarding_completed": True}},
        return_document=ReturnDocument.AFTER,
    )

    return serialize(result)

async def format_onboarding_response(onboarding_doc):
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
    images_out = []

    for fid in onboarding_doc.get("images", []):
        file_doc = await file_collection.find_one({
            "_id": ObjectId(fid),
            "is_deleted": False
        })
        if file_doc:
            url = await generate_file_url(
                storage_key=file_doc["storage_key"],
                backend=file_doc["storage_backend"]
            )
            images_out.append({
                "file_id": fid,
                "url": url
            })

    selfie_out = None
    selfie_id = onboarding_doc.get("selfie_image")

    if selfie_id:
        selfie_doc = await file_collection.find_one({
            "_id": ObjectId(selfie_id),
            "is_deleted": False
        })
        if selfie_doc:
            selfie_out = {
                "file_id": selfie_id,
                "url": await generate_file_url(
                    storage_key=selfie_doc["storage_key"],
                    backend=selfie_doc["storage_backend"]
                )
            }

    response = serialize(onboarding_doc)

    response["images"] = images_out
    response["selfie_image"] = selfie_out

    return response
