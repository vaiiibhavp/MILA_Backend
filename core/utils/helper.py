import time
from fastapi import HTTPException, UploadFile, File
from bson import ObjectId
import re
from .response_mixin import CustomResponseMixin
import os, ssl, asyncio
from uuid import uuid4
from datetime import datetime, timezone, date, time, timedelta
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
from dateutil.relativedelta import relativedelta
from typing import Optional, Tuple

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
        return {k: convert_objectid_to_str(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_objectid_to_str(item) for item in obj]
    elif isinstance(obj, ObjectId):
        return str(obj)
    else:
        return obj

def get_membership_period(validity_value: int, validity_unit: str, current_expiry: Optional[datetime] = None) -> Tuple[datetime, datetime]:
    """
       Returns (start_date, end_date) in UTC.

       - If no current_expiry: start = now (UTC)
       - If current_expiry in the future or today: start = next day after expiry at 00:00 UTC
    """
    unit_map = {
        "day": relativedelta(days=validity_value),
        "month": relativedelta(months=validity_value),
        "year": relativedelta(years=validity_value),
    }

    validity_unit = validity_unit.lower()
    if validity_unit not in unit_map:
        raise ValueError("validity_unit must be 'day', 'month', or 'year'")

    now_utc = datetime.now(timezone.utc)

    # --- Determine start_date ---
    if current_expiry is None:
        # No previous membership
        start_date = now_utc
    else:
        # current_expiry might be date or datetime; normalize to a date
        if isinstance(current_expiry, datetime):
            expiry_date = current_expiry.date()
        elif isinstance(current_expiry, date):
            expiry_date = current_expiry
        else:
            raise TypeError("current_expiry must be datetime, date, or None")

        today_utc = now_utc.date()

        if expiry_date >= today_utc:
            # Start from the next day after the expiry date, at 00:00 UTC
            next_day = expiry_date + timedelta(days=1)
            start_date = datetime.combine(next_day, time.min, tzinfo=timezone.utc)
        else:
            # Existing membership already expired in the past → start now
            start_date = now_utc

        # --- Determine end_date ---
    end_date = start_date + unit_map[validity_unit]

    return start_date, end_date