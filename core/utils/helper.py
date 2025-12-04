import time
from fastapi import HTTPException, UploadFile, File
from bson import ObjectId
import re
from .response_mixin import CustomResponseMixin
import os, ssl, asyncio
from uuid import uuid4
from datetime import datetime
from tasks import send_contact_us_email_task
from fastapi import Depends, Request
from jose import jwt,JWTError
from core.utils.auth_utils import SECRET_ACCESS_KEY,ALGORITHM
response = CustomResponseMixin()
import boto3
from botocore.exceptions import ClientError
from datetime import datetime
from config.db_config import user_collection, file_collection
import base64
import aiohttp
import uuid
from dotenv import load_dotenv
import os
from bson import ObjectId
from config.basic_config import settings
from config.models.user_models import *

load_dotenv()

ADMIN_EMAIL = os.getenv("TEST_ADMIN_EMAIL")
AWS_S3_BUCKET_NAME = os.getenv("AWS_S3_BUCKET_NAME")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_S3_REGION = os.getenv("AWS_S3_REGION")


# Helper function for validate_pwd
def validate_pwd(password):
    # Validate password strength
    if not re.match(r"^(?=.*[A-Z])(?=.*[a-z])(?=.*\d)(?=.*[@$!%*?&#])[A-Za-z\d@$!%*?&#]{8,16}$", password):
        # Password must be 8-16 characters, include one uppercase, one lowercase, one digit, and one special character
        return response.raise_exception(message="Password must be 8-16 characters long, include one uppercase letter, one lowercase letter, one number, and one special character.",status_code=400)


# Helper function for validate_new_pwd
def validate_new_pwd(new_password):
    # Validate password strength
    if not re.match(r"^(?=.*[A-Z])(?=.*[a-z])(?=.*\d)(?=.*[@$!%*?&#])[A-Za-z\d@$!%*?&#]{8,16}$", new_password):
        # Password must be 8-16 characters, include one uppercase, one lowercase, one digit, and one special character
        return response.raise_exception(message="new_password must be 8-16 characters long, include one uppercase letter, one lowercase letter, one number, and one special character.",status_code=400)


# Helper function for validate_confirm_new_password
def validate_confirm_new_password(confirm_new_password):
    # Validate password strength
    if not re.match(r"^(?=.*[A-Z])(?=.*[a-z])(?=.*\d)(?=.*[@$!%*?&#])[A-Za-z\d@$!%*?&#]{8,16}$", confirm_new_password):
        # Password must be 8-16 characters, include one uppercase, one lowercase, one digit, and one special character
        return response.raise_exception(message="confirm_new_password must be 8-16 characters long, include one uppercase letter, one lowercase letter, one number, and one special character.",status_code=400)


#helper function for serialize_datetime_fields
def serialize_datetime_fields(data):
    """
    Recursively serialize datetime fields in a dictionary to ISO format strings.
    This function handles nested dictionaries and lists.
    """
    if isinstance(data, dict):
        serialized = {}
        for key, value in data.items():
            if isinstance(value, datetime):
                serialized[key] = value.strftime('%Y-%m-%d %H:%M:%S')
            elif isinstance(value, (dict, list)):
                serialized[key] = serialize_datetime_fields(value)
            else:
                serialized[key] = value
        return serialized
    elif isinstance(data, list):
        return [serialize_datetime_fields(item) for item in data]
    else:
        return data


#helper function for convert_objectid_to_str
def convert_objectid_to_str(obj):
    """
    Recursively convert ObjectId fields to strings in a dict or list.
    """
    if isinstance(obj, dict):
        return [{k: convert_objectid_to_str(v) for k, v in obj.items()}]
    elif isinstance(obj, list):
        return [convert_objectid_to_str(item) for item in obj]
    elif isinstance(obj, ObjectId):
        return str(obj)
    else:
        return obj