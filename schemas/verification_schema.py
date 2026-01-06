from enum import Enum
from datetime import datetime
from typing import Optional, List
from bson import ObjectId
from pydantic import BaseModel, Field, validator
from config.models.user_models import PyObjectId

from core.utils.core_enums import VerificationStatusEnum


class VerificationModel(BaseModel):
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    user_id: str
    onboarding_id: PyObjectId

    submitted_photos: List[str]
    live_selfie: str

    verification_status: VerificationStatusEnum = VerificationStatusEnum.PENDING

    submitted_at: datetime = Field(default_factory=datetime.utcnow)
    verified_at: Optional[datetime] = None

    verified_by_admin_id: Optional[PyObjectId] = None
    rejection_reason: Optional[str] = None

    class Config:
        use_enum_values = True
        arbitrary_types_allowed = True
        json_encoders = {PyObjectId: str}

class FileWithUrl(BaseModel):
    file_id: str
    url: Optional[str]


class VerificationResponse(BaseModel):
    verification_id: str
    user_id: str
    username: str

    submitted_photos: List[FileWithUrl]
    live_selfie: FileWithUrl

    verification_status: str
    submitted_at: datetime
    verified_at: Optional[datetime]

class VerificationActionRequest(BaseModel):
    user_id: str = Field(...)

class VerificationActionRequest(BaseModel):
    user_id: str = Field(..., description="User ID for verification action")

    @validator("user_id")
    def validate_user_id(cls, v):
        # Empty / whitespace check
        if not v or not v.strip():
            raise ValueError("USER_ID_REQUIRED")

        # Mongo ObjectId validation
        if not ObjectId.is_valid(v):
            raise ValueError("INVALID_USER_ID")

        return v.strip()
