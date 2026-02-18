
from fastapi import APIRouter, Depends, Request, Query
from bson import ObjectId
import time
from datetime import datetime
from config.models.user_models import Files, FileType
from core.utils.permissions import UserPermission
from config.db_config import *
from core.utils.response_mixin import CustomResponseMixin
from services.translation import translate_message
from fastapi import UploadFile
import os
import aiofiles
import boto3
from botocore.exceptions import ClientError


# ENV VAR
STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "LOCAL")  # LOCAL or S3
# Local uploads
UPLOAD_DIR = os.getenv("UPLOAD_DIR") 
BASE_URL = os.getenv("BASE_URL")

# S3 settings
AWS_S3_BUCKET_NAME = os.getenv("AWS_S3_BUCKET_NAME")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_S3_REGION = os.getenv("AWS_S3_REGION")

response = CustomResponseMixin()


#helper function to save the profile picture
async def save_file(file_obj: UploadFile, file_name: str, user_id: str, file_type="profile_photo", content: bytes = None):
    """
    Save uploaded file to LOCAL or S3 based on STORAGE_BACKEND.
    Returns: (public_url, storage_key, backend)
    """
    try:
        ext = os.path.splitext(file_name)[-1].lower().lstrip(".")

        allowed_images = ["jpg", "jpeg", "png"]
        allowed_audio = ["mp3", "wav", "m4a"]

        if ext not in allowed_images + allowed_audio:
            raise ValueError("Invalid file type")

        if content is None:
            content = await file_obj.read()

        timestamp = int(time.time())

        # Storage key: always use forward slashes
        storage_key = f"{file_type}/{user_id}/{timestamp}.{ext}"

        if STORAGE_BACKEND == "LOCAL":
            # Local save: use os.path.join for actual filesystem path
            dir_path = os.path.join(UPLOAD_DIR, file_type, user_id)
            os.makedirs(dir_path, exist_ok=True)
            file_path = os.path.join(dir_path, f"{timestamp}.{ext}")

            async with aiofiles.open(file_path, "wb") as out_file:
                await out_file.write(content)
            public_url = f"{BASE_URL}/{file_type}/{user_id}/{timestamp}.{ext}"
            return public_url, storage_key, "LOCAL"

        elif STORAGE_BACKEND == "S3":

            # Initialize S3 client here
            import boto3
            s3_client = boto3.client(
                "s3",
                region_name=AWS_S3_REGION,
                aws_access_key_id=AWS_ACCESS_KEY_ID,
                aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            )

            if ext in allowed_images:
                content_type = "image/jpeg" if ext in ["jpg", "jpeg"] else f"image/{ext}"
            elif ext == "mp3":
                content_type = "audio/mpeg"
            elif ext == "wav":
                content_type = "audio/wav"
            elif ext == "m4a":
                content_type = "audio/mp4"
            else:
                content_type = "application/octet-stream"

            s3_client.put_object(
                Bucket=AWS_S3_BUCKET_NAME,
                Key=storage_key,
                Body=content,
                ContentType=content_type
            )

            public_url = s3_client.generate_presigned_url(
                ClientMethod="get_object",
                Params={"Bucket": AWS_S3_BUCKET_NAME, "Key": storage_key},
                ExpiresIn=3600
            )
            return public_url, storage_key, "S3"

    except Exception as e:
        raise RuntimeError(f"Failed to save file: {str(e)}")

#helper function to genrate the profile picture url
async def generate_file_url(storage_key: str, backend: str):
    """
    Generate fetch URL for an existing file.
    """
    if backend == "LOCAL":
        return f"{BASE_URL}/{storage_key}"

    elif backend == "S3":
        s3_client = boto3.client(
            "s3",
            region_name=AWS_S3_REGION,
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        )
        try:
            return s3_client.generate_presigned_url(
                ClientMethod="get_object",
                Params={"Bucket": AWS_S3_BUCKET_NAME, "Key": storage_key},
                ExpiresIn=3600
            )
        except ClientError:
            return None

    return None


#helper function to get the profile picture
async def get_profile_photo_url(current_user: dict):
    """Return profile photo URL or None (dict only, no JSONResponse)"""
    user_id = str(current_user["_id"])
    user_doc = await user_collection.find_one({"_id": ObjectId(user_id)})
    file_id = user_doc.get("profile_photo_id")

    if not file_id:
        return None

    # file_doc = await file_collection.find_one({"_id": str(file_id), "is_deleted": {"$ne": True}})
    file_doc = await file_collection.find_one({"_id": ObjectId(file_id), "is_deleted": {"$ne": True}})
    if not file_doc:
        return None

    url = await generate_file_url(file_doc["storage_key"], STORAGE_BACKEND)
    return url


#controller for getting the profile photo 
async def get_profile_photo_controller(current_user: dict, lang: str = "en"):
    """
    Fetch the profile photo URL for the current user and return JSONResponse.
    Uses `get_profile_photo_url` helper.
    """
    try:
        url = await get_profile_photo_url(current_user)
        if not url:
            return response.success_message(
                translate_message("NO_PROFILE_PHOTO_FOUND", lang),
                data={"url": None},
                status_code=200
            )

        return response.success_message(
            translate_message("PROFILE_PHOTO_FETCH_SUCCESS", lang),
            data={"url": url},
            status_code=200
        )

    except Exception as e:
        return response.raise_exception(
            translate_message("FAILED_TO_FETCH_PROFILE_PHOTO", lang) + f": {str(e)}",
            status_code=500
        )


#controller for uploading the profile photo 
async def upload_profile_photo_controller(
    current_user: dict, file_obj: UploadFile, file_name: str, overwrite: bool = False, lang: str = "en"
):
    """
    Uploads a profile photo for the user (LOCAL or S3) and returns the fetch URL.
    """

    try:
        user_id = str(current_user["_id"])

        # Check existing photo
        user_doc = await user_collection.find_one({"_id": ObjectId(user_id)})
        existing_file_id = user_doc.get("profile_photo_id")
        if existing_file_id and not overwrite:
            return response.error_message(
                translate_message("PROFILE_PHOTO_ALREADY_EXISTS", lang),
                data={},
                status_code=403)

        # Save file
        public_url, storage_key, backend = await save_file(file_obj, file_name, user_id)

        # Save file metadata
        file_doc = Files(
            storage_key=storage_key,
            storage_backend=backend,
            file_type=FileType.PROFILE_PHOTO,
            uploaded_by=user_id
        )
        result = await file_collection.insert_one(file_doc.dict(by_alias=True))
        new_file_id = str(result.inserted_id)

        # Handle overwrite
        if existing_file_id and overwrite:
            await file_collection.update_one(
                {"_id": ObjectId(existing_file_id)},
                {"$set": {"is_deleted": True, "deleted_at": datetime.utcnow()}}
            )

        # Update user profile_photo_id
        await user_collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"profile_photo_id": new_file_id, "updated_at": datetime.utcnow()}}
        )

        return response.success_message(
            translate_message("PROFILE_PHOTO_UPLOAD_SUCCESS", lang),
            data={
                "file_id": str(new_file_id),
                "url": public_url,
                "storage_key": storage_key,
                "backend": backend
            }
        )

    except Exception as e:
        return response.raise_exception(
            translate_message("PROFILE_PHOTO_UPLOAD_FAILED", lang) + f": {str(e)}",
            status_code=500
        )


# Helper function to save any file type
async def save_everytype_file(file_obj: UploadFile, file_name: str, user_id: str, file_type="document"):
    """
    Save uploaded file to LOCAL or S3 based on STORAGE_BACKEND.
    Returns: (public_url, storage_key, backend)
    """
    try:
        ext = os.path.splitext(file_name)[-1].lower().lstrip(".")
        ALLOWED_EXTENSIONS = [
            "jpg", "jpeg", "png", "pdf", "csv", "docx", "txt", 
            "json", "xlsx", "xls", "svg"
        ]

        if ext not in ALLOWED_EXTENSIONS:
            raise ValueError(f"Invalid file type: {ext}")

        timestamp = int(time.time())
        storage_key = f"{file_type}/{user_id}/{timestamp}.{ext}"

        if STORAGE_BACKEND == "LOCAL":
            dir_path = os.path.join(UPLOAD_DIR, file_type, user_id)
            os.makedirs(dir_path, exist_ok=True)
            file_path = os.path.join(dir_path, f"{timestamp}.{ext}")

            async with aiofiles.open(file_path, "wb") as out_file:
                content = await file_obj.read()
                await out_file.write(content)

            public_url = f"{BASE_URL}uploads/{file_type}/{user_id}/{timestamp}.{ext}"
            return public_url, storage_key, "LOCAL"

        elif STORAGE_BACKEND == "S3":
            import boto3
            import mimetypes

            s3_client = boto3.client(
                "s3",
                region_name=AWS_S3_REGION,
                aws_access_key_id=AWS_ACCESS_KEY_ID,
                aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            )

            content = await file_obj.read()
            mime_type, _ = mimetypes.guess_type(file_name)
            if not mime_type:
                mime_type = "application/octet-stream"

            s3_client.put_object(
                Bucket=AWS_S3_BUCKET_NAME,
                Key=storage_key,
                Body=content,
                ContentType=mime_type
            )

            public_url = s3_client.generate_presigned_url(
                ClientMethod="get_object",
                Params={"Bucket": AWS_S3_BUCKET_NAME, "Key": storage_key},
                ExpiresIn=3600
            )
            return public_url, storage_key, "S3"

    except Exception as e:
        raise RuntimeError(f"Failed to save file: {str(e)}")


#controller for uploading a sepicfic file 
async def upload_file_controller(
    current_user: dict,
    file_obj: UploadFile,
    file_name: str,
    file_type: str,
    lang: str = "en"
):
    """
    controller for uploading a sepicfic file 
    Uploads a file (doc, CSV, PDF, etc.) for the user (LOCAL or S3)
    and stores it in file_collection.
    """
    try:
        # Prevent uploading as profile picture
        if file_type == "profile_photo":
            return response.error_message(
                translate_message("UPLOADING_PROFILE_NOT_ALLOWED_TRY_OTHER_API", lang=lang),
                data={}, status_code=403
                )
        user_id = str(current_user["_id"])

        user_id_str = str(current_user["_id"])  # keep string for paths

        # Save file
        public_url, storage_key, backend = await save_everytype_file(file_obj, file_name, user_id_str, file_type)

        # Save metadata
        file_doc = Files(
            storage_key=storage_key,
            storage_backend=backend,
            file_type=file_type,
            uploaded_by=user_id_str  # stored as string
        )
        result = await file_collection.insert_one(file_doc.dict(by_alias=True))
        new_file_id_str = str(result.inserted_id)  # convert ObjectId to str

        # Store file IDs as strings in user document
        await user_collection.update_one(
            {"_id": ObjectId(user_id_str)},  # convert only here for Mongo query
            {"$push": {"uploaded_file_ids": new_file_id_str}, "$set": {"updated_at": datetime.utcnow()}}
        )

        return response.success_message(
            translate_message("FILE_UPLOADED_SUCCESS", lang=lang).format(file_type=file_type),
            data={
                "file_id": new_file_id_str,
                "url": public_url,
                "storage_key": storage_key,
                "backend": backend
            }
        )

    except Exception as e:
        return response.raise_exception(
            translate_message("FILE_UPLOAD_FAILED", lang=lang) + f": {str(e)}",
            status_code=500
        )


#controller for getting user all or  a sepicfic file 
async def get_user_files_controller(current_user: dict, file_type: str = None, lang: str = "en"):
    """
    Controller to fetch user files.
    Optionally filter by file_type.
    """
    try:
        user_id = str(current_user["_id"])
        user_doc = await user_collection.find_one({"_id": ObjectId(user_id)})
        file_ids = user_doc.get("uploaded_file_ids", [])

        files = []
        for fid in file_ids:
            query = {"_id": ObjectId(fid), "is_deleted": {"$ne": True}}
            if file_type:
                query["file_type"] = file_type

            file_doc = await file_collection.find_one(query)
            if file_doc:
                url = await generate_file_url(file_doc["storage_key"], STORAGE_BACKEND)
                files.append({
                    "file_id": str(fid),
                    "file_type": file_doc["file_type"],
                    "url": url
                })

        return response.success_message(
            translate_message("FILES_FETCHED_SUCCESS", lang=lang),
            data={"files": files}
        )

    except Exception as e:
        return response.raise_exception(
            translate_message("FILES_FETCH_FAILED", lang=lang) + f": {str(e)}",
            status_code=500
        )


#controller for deleting a sepicfic file of a user
async def delete_user_file_controller(file_id: str, user_id: str, lang: str = "en"):
    """
    Delete a user's uploaded file (S3 or LOCAL) and remove reference from user document.
    """
    try:
        # 1. Fetch file document
        file_doc = await file_collection.find_one({"_id": ObjectId(file_id)})
        if not file_doc or file_doc.get("is_deleted"):
            return response.success_message(
                translate_message("FILE_NOT_FOUND_OR_DELETED", lang=lang),
                data={}
            )

        # 2. Check if the file belongs to current user
        if str(file_doc.get("uploaded_by")) != str(user_id):
            return response.error_message(
                translate_message("UNAUTHORIZED_DELETE_FILE", lang=lang),
                data={}, status_code=403
            )

        storage_backend = STORAGE_BACKEND
        storage_key = str(file_doc.get("storage_key")).replace("\\", "/")

        # 3. Delete file from storage
        if storage_backend == "S3":
            s3_client = boto3.client(
                "s3",
                region_name=AWS_S3_REGION,
                aws_access_key_id=AWS_ACCESS_KEY_ID,
                aws_secret_access_key=AWS_SECRET_ACCESS_KEY
            )
            try:
                s3_client.delete_object(Bucket=AWS_S3_BUCKET_NAME, Key=storage_key)
            except ClientError as e:
                return response.raise_exception(
                    translate_message("S3_DELETION_ERROR", lang=lang) + f": {str(e)}",
                    status_code=500
                )

        elif storage_backend == "LOCAL":
            try:
                local_path = os.path.join(UPLOAD_DIR, *storage_key.split("/"))
                if os.path.exists(local_path):
                    os.remove(local_path)
            except Exception as e:
                return response.raise_exception(
                    translate_message("LOCAL_DELETION_ERROR", lang=lang) + f": {str(e)}",
                    status_code=500
                )
                
        # 4. Mark file as deleted in DB
        await file_collection.update_one(
            {"_id": ObjectId(file_id)},
            {"$set": {"is_deleted": True, "deleted_at": datetime.utcnow()}}
        )

        # 5. Remove reference from user document (if stored in list)
        await user_collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$pull": {"uploaded_file_ids": file_id}, "$set": {"updated_at": datetime.utcnow()}}
        )

        return response.success_message(
            translate_message("FILE_DELETED_SUCCESS", lang=lang),
            data={}
        )

    except Exception as e:
        return response.raise_exception(
            translate_message("FILE_DELETE_FAILED", lang=lang) + f": {str(e)}",
            status_code=500
        )
    
async def profile_photo_from_onboarding(onboarding: dict):
    """
    Priority:
    first image from images[]
    """
    if not onboarding:
        return None
    
    file_id = None

    if onboarding.get("images"):
        file_id = onboarding["images"][0]

    if not file_id:
        return None

    file_doc = await file_collection.find_one(
        {"_id": ObjectId(file_id), "is_deleted": {"$ne": True}}
    )

    if not file_doc:
        return None

    return await generate_file_url(
        file_doc["storage_key"],
        file_doc["storage_backend"]
    )

async def resolve_banner_url(file_id: str) -> str:
    file_doc = await file_collection.find_one(
        {"_id": ObjectId(file_id)},
        {"storage_key": 1, "storage_backend": 1}
    )

    if not file_doc:
        return None

    return await generate_file_url(
        storage_key=file_doc["storage_key"],
        backend=file_doc.get("storage_backend")
    )