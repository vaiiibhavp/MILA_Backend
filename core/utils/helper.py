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
from services.translation import translate_message
from core.utils.core_enums import *
from config.models.onboarding_model import *
from core.utils.auth_utils import *
from enum import Enum
from typing import List
from decimal import Decimal, ROUND_HALF_UP
from config.basic_config import settings
from schemas.user_token_history_schema import CreateTokenHistory
from config.models.user_token_history_model import create_user_token_history

TOKEN_TO_USDT_RATE = Decimal("0.05")

load_dotenv()

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")
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

async def finalize_login_response(user: dict, lang: str):
    """
    Common login finalization logic:
    - generate tokens
    - update login status
    - fetch onboarding completion
    - return standardized response
    """
    access_token, refresh_token = generate_login_tokens(user)

    await user_collection.update_one(
        {"_id": user["_id"]},
        {
            "$set": {
                "login_status": LoginStatus.ACTIVE,
                "last_login_at": datetime.utcnow()
            }
        }
    )

    onboarding_completed = await get_onboarding_completed_status(str(user["_id"]))

    return response.success_message(
        translate_message("LOGIN_SUCCESSFUL", lang=lang),
        data=[{
            "access_token": access_token,
            "refresh_token": refresh_token,
            "onboarding_completed": onboarding_completed,
            "two_factor_enabled": user.get("two_factor_enabled", False)
        }],
        status_code=200
    )

def enum_values(enum_cls: Enum) -> List[str]:
    """
    Extract enum values as a list of strings
    """
    return [e.value for e in enum_cls]

def convert_datetime_to_date(obj, date_format="%Y-%m-%d"):
    """
     Recursively convert datetime objects to formatted date string.
    """
    if isinstance(obj, datetime):
        return obj.strftime(date_format)
    elif isinstance(obj, dict):
        return {k: convert_datetime_to_date(v, date_format) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_datetime_to_date(item, date_format) for item in obj]
    else:
        return obj

def get_subscription_status(expires_at) -> str:
    """
    Determine subscription status based on expiry date.
    """
    if not expires_at:
        return MembershipStatus.EXPIRED.value

    now = datetime.now(timezone.utc)

    # Ensure timezone-aware comparison
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    return MembershipStatus.EXPIRED.value if expires_at < now else MembershipStatus.ACTIVE.value

async def get_country_name_by_id(
    country_id: str | ObjectId,
    countries_collection
) -> Optional[str]:
    """
    Fetch country name using country ObjectId
    """
    if not country_id:
        return None

    try:
        country_doc = await countries_collection.find_one(
            {"_id": ObjectId(country_id)}
        )
        return country_doc.get("name") if country_doc else None
    except Exception:
        return None

def calculate_usdt_amount(tokens: int) -> Decimal:
    """
    Calculate USDT amount based on token volume.

    Rules:
    - 1 Token = 0.05 USDT
    - Result rounded to 2 decimal places

    :param tokens: Number of token
    :return: USDT amounts
    """
    if tokens <= 0:
        raise ValueError("Tokens must be greater than 0")

    usdt_amount = Decimal(tokens) * TOKEN_TO_USDT_RATE

    return usdt_amount.quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)


async def credit_tokens_for_verification(user_id: str, admin_id: str):
    """
    Credits 100 tokens only once after verification approval
    """

    # Check if already rewarded
    already_rewarded = await user_token_history_collection.find_one({
        "user_id": user_id,
        "reason": TokenTransactionReason.ACCOUNT_VERIFIED
    })

    if already_rewarded:
        return  # Prevent double credit

    # Fetch current balance
    user = await user_collection.find_one(
        {"_id": ObjectId(user_id)},
        {"tokens": 1}
    )

    balance_before = int(user.get("tokens") or 0)
    balance_after = balance_before + settings.VERIFICATION_REWARD_TOKENS

    # Atomic token update
    await user_collection.update_one(
        {"_id": ObjectId(user_id)},
        {
            "$inc": {"tokens": settings.VERIFICATION_REWARD_TOKENS},
            "$set": {"updated_at": datetime.utcnow()}
        }
    )

    # Insert history
    token_history = CreateTokenHistory(
        user_id=user_id,
        delta=settings.VERIFICATION_REWARD_TOKENS,
        type=TokenTransactionType.CREDIT,
        reason=TokenTransactionReason.ACCOUNT_VERIFIED,
        balance_before=str(balance_before),
        balance_after=str(balance_after)
    )

    await create_user_token_history(token_history)

def calculate_visibility(start_date, end_date):
    now = datetime.utcnow()

    if now < start_date:
        return ContestVisibility.upcoming.value
    elif start_date <= now <= end_date:
        return ContestVisibility.in_progress.value
    else:
        return ContestVisibility.completed.value

async def get_admin_id_by_email() -> str | None:
    if not ADMIN_EMAIL:
        return None

    admin = await admin_collection.find_one(
        {"email": ADMIN_EMAIL},
        {"_id": 1}
    )

    return str(admin["_id"]) if admin else None
