#user_model.py

from pydantic import BaseModel, EmailStr, Field, model_validator,field_validator
from typing import Optional, Union, Any, Callable, Dict, List
from pydantic import GetJsonSchemaHandler
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import core_schema
from bson import ObjectId
from datetime import datetime,date
from config.db_config import db
from config.db_config import user_collection,token_collection, file_collection, onboarding_collection
from core.utils.response_mixin import CustomResponseMixin
from enum import Enum
import asyncio
import re
from config.models.user_token_history_model import *

response = CustomResponseMixin()

# Custom class for handling MongoDB's ObjectId
class PyObjectId(str):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):  # Fixed parameter list
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return str(ObjectId(v))

    # Mandatory for Pydantic v2
    @classmethod
    def __get_pydantic_core_schema__(
        cls, 
        source_type: Any, 
        handler: Callable[[Any], core_schema.CoreSchema]
    ) -> core_schema.CoreSchema:
        return core_schema.str_schema()

    # Fixed JSON schema method
    @classmethod
    def __get_pydantic_json_schema__(
        cls, 
        _core_schema: core_schema.CoreSchema, 
        handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        json_schema = handler(_core_schema)
        json_schema["format"] = "objectId"
        return json_schema

FREE_FILTERS = {
    "country": ("country", "$in"),
    "genders": ("gender", "$in"),
}

PREMIUM_FILTERS = {
    "status": ("marital_status", "$in"),
    "orientations": ("sexual_orientation", "$in"),
    "age": ("birthdate", "range"),
}

# User Role Enum for validation
class UserRole(str, Enum):
    ADMIN = "admin"
    USER = "user"  # Keep existing default role


# FileType for validation
class FileType(str, Enum):
    PROFILE_PHOTO = "profile_photo"
    DOCUMENT = "document"
    INVOICE = "invoice"
    ONBOARDING_IMAGE = "onboarding_image"
    SELFIE = "selfie"
    PUBLIC_GALLERY = "public_gallery"
    PRIVATE_GALLERY = "private_gallery"
    GIFT = "gift"
    VERIFICATION_SELFIE = "verification_selfie"
    CONTEST = "contest"
    CONTEST_BANNER = "contest_banner"

# ---- Files model ----
class Files(BaseModel):
    id: Optional[PyObjectId] = Field(default=None)
    storage_key: str
    storage_backend: str  # LOCAL or S3
    file_type: FileType
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)
    uploaded_by: Optional[PyObjectId] = None
    is_deleted: bool = Field(default=False)


# ---- User model ----
class UserCreate(BaseModel):
    id: Optional[PyObjectId] = Field(default=None)
    first_name: str = Field(max_length=50)
    last_name: str = Field(max_length=50)
    email: EmailStr = Field()
    password: str
    role: UserRole = Field(default=UserRole.USER)  # Updated to use enum with validation
    membership_type: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = None  # Default to None, will be set upon update
    is_deactivated: bool = Field(default=False)  # Updated to use enum with validation
    is_deleted: bool = Field(default=False)  # Soft delete flag
    profile_photo_id: Optional[PyObjectId] = None  # Reference to Files
    two_factor_enabled: bool = Field(default=True)
    tokens : Optional[int] = None
    membership_trans_id : Optional[str] = None
    language : Optional[str] = None
    
    def update_user(self, updated_data: dict):
        """Method to update user and set the updated_at field."""
        self.__dict__.update(updated_data)
        self.updated_at = datetime.utcnow()  # Set updated_at on user modification
        
    class ConfigDict:
        json_encoders = {ObjectId: str}

    @model_validator(mode='before')
    def check_required_fields(cls, values):
        """Method to check_required_fields """
        required_fields = ["first_name", "last_name", "email","password","role"]
        missing_fields = [field for field in required_fields if field not in values]
        if missing_fields:
            raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")
        return values
    
    @field_validator("first_name")
    def validate_first_name(cls, v):
        """Ensure first name is not empty, contains no numbers, and is properly trimmed."""
        if not v or not v.strip():
            raise ValueError("First name cannot be empty or contain only spaces.")
        if any(char.isdigit() for char in v):
            raise ValueError("First name cannot contain numbers.")
        if len(v.strip()) < 2:
            raise ValueError("First name must be at least 2 characters long.")        
        # Regex pattern: only letters, hyphens, apostrophes, and spaces allowed
        if not re.match(r"^[a-zA-Z\s\-']+$", v):
            raise ValueError("First name must contain only letters")

        return v.strip()
    
    @field_validator("last_name")
    def validate_last_name(cls, v):
        """Ensure last name is not empty, contains no numbers, and is properly trimmed."""
        if not v or not v.strip():
            raise ValueError("Last name cannot be empty or contain only spaces.")
        if any(char.isdigit() for char in v):
            raise ValueError("Last name cannot contain numbers.")
        if len(v.strip()) < 2:
            raise ValueError("Last name must be at least 2 characters long.")
        # Regex pattern: only letters, hyphens, apostrophes, and spaces allowed
        if not re.match(r"^[a-zA-Z\s\-']+$", v):
            raise ValueError("Last name must contain only letters")
        return v.strip()
        
    @field_validator("role")
    def validate_role(cls, value):
        """Validate that the role is one of the allowed values"""
        if isinstance(value, str):
            try:
                return UserRole(value.lower())
            except ValueError:
                valid_roles = [role.value for role in UserRole]
                raise ValueError(f"Invalid role. Must be one of: {', '.join(valid_roles)}")
        return value


# Pydantic models to define the request and token schema
class TokenSchema(BaseModel):
    user_id: str
    email: str
    access_token: str
    refresh_token: str
    access_token_expire: datetime
    refresh_token_expire: datetime
    is_blacklisted: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)


# Function to store tokens in MongoDB
def store_token(user_id: str, email: str, access_token: str, refresh_token: str, access_token_expire: datetime, refresh_token_expire: datetime):
    token_data = TokenSchema(
        user_id=user_id,
        email=email,
        access_token=access_token,
        refresh_token=refresh_token,
        access_token_expire=access_token_expire,
        refresh_token_expire=refresh_token_expire,
        is_blacklisted=False,  # Tokens will not be blacklisted by default,
        created_at=datetime.utcnow()
    )
    token_collection.insert_one(token_data.model_dump())


# Fetch user from db based on username
async def get_user_by_email(data: str) -> UserCreate:
    user = await user_collection.find_one({f"email": data})
    if not user:
        return False
    # return UserCreate(**user)
    return user["_id"]

async def get_user_details(
        condition: Dict[str, Any],
        fields: Optional[List[str]] = None
):
    projection = None
    if fields:
        projection = {field: 1 for field in fields}
        # If user didn't explicitly ask for _id, exclude it
        if "_id" not in fields:
            projection["_id"] = 0


    return await user_collection.find_one(
        condition,
        projection
    )

async def get_users_list(
    condition: Dict[str, Any],
    fields: Optional[List[str]] = None,
    skip: int = 0,
    limit: int = 10
):
    projection = None
    if fields:
        projection = {field: 1 for field in fields}
        if "_id" not in fields:
            projection["_id"] = 0

    cursor = (
        user_collection
        .find(condition, projection)
        .skip(skip)
        .limit(limit)
        .sort("created_at", -1)
    )

    users = await cursor.to_list(length=limit)
    total = await user_collection.count_documents(condition)

    return users, total

async def get_user_token_balance(user_id: str) -> int:
    user = await user_collection.find_one(
        {"_id": ObjectId(user_id)},
        {"tokens": 1}
    )
    return int(user.get("tokens", 0)) if user else 0

async def debit_user_tokens(
    user_id: str,
    amount: int,
    reason: str
):
    balance_before = await get_user_token_balance(user_id)

    if balance_before < amount:
        return None, balance_before

    balance_after = balance_before - amount

    # Atomic update
    await user_collection.update_one(
        {
            "_id": ObjectId(user_id),
            "tokens": {"$gte": amount}
        },
        {
            "$inc": {"tokens": -amount},
            "$set": {"updated_at": datetime.utcnow()}
        }
    )

    # Token history entry
    await create_user_token_history(
        CreateTokenHistory(
            user_id=user_id,
            delta=-amount,
            type=TokenTransactionType.DEBIT,
            reason=reason,
            balance_before=str(balance_before),
            balance_after=str(balance_after)
        )
    )

    return balance_after, balance_before
