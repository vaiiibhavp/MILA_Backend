#onboarding_model.py

from pydantic import BaseModel, field_validator
from pydantic import Field
from typing import Optional, List
from datetime import date, datetime
from enum import Enum
from config.models.user_models import PyObjectId

class GenderEnum(str, Enum):
    male = "male"
    female = "female"
    non_binary = "non_binary"
    transgender = "transgender"


class SexualOrientationEnum(str, Enum):
    straight = "straight"
    gay = "gay"
    bisexual = "bisexual"
    asexual = "asexual"
    demisexual = "demisexual"
    pansexual = "pansexual"


class MaritalStatusEnum(str, Enum):
    single = "single"
    married = "married"
    divorced = "divorced"
    in_relationship = "in_relationship"
    open = "open"

class InterestedInEnum(str , Enum):
    male = "male"
    female = "female"
    gay = "gay"

class PublicGalleryItem(BaseModel):
    image_url: str
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)


class PrivateGalleryItem(BaseModel):
    image_url: str
    price: int
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)

class OnboardingModel(BaseModel):
    id: Optional[PyObjectId] = Field(default=None)
    user_id: str

    birthdate: Optional[datetime] = None
    gender: Optional[str] = None
    sexual_orientation: Optional[str] = None
    marital_status: Optional[str] = None

    country: Optional[str] = None
    bio: Optional[str] = None

    passions: List[str] = []
    interested_in: Optional[List[InterestedInEnum]] = None
    sexual_preferences: List[str] = []

    public_gallery : Optional[List[PrivateGalleryItem]] = None
    private_gallery : Optional[List[PrivateGalleryItem]] = None

    preferred_country: Optional[List[str]] = None
    images: List[str] = []
    selfie_image: Optional[str] = None

    onboarding_completed: bool = False

    created_at: datetime = datetime.utcnow()
    updated_at: datetime = datetime.utcnow()

    class Config:
        use_enum_values = True
        arbitrary_types_allowed = True


class OnboardingStepUpdate(BaseModel):

    # Step 1 fields
    birthdate: Optional[datetime] = None
    gender: Optional[GenderEnum] = None
    sexual_orientation: Optional[SexualOrientationEnum] = None
    marital_status: Optional[MaritalStatusEnum] = None
    country: Optional[str] = None
    bio: Optional[str] = None
    passions: Optional[List[str]] = None
    interested_in: Optional[List[InterestedInEnum]] = None
    sexual_preferences: Optional[List[str]] = None
    public_gallery : Optional[List[PublicGalleryItem]] = None
    private_gallery : Optional[List[PrivateGalleryItem]] = None
    preferred_country: Optional[List[str]] = None
    images: Optional[List[str]] = None
    selfie_image: Optional[str] = None
    onboarding_completed: Optional[bool] = None

    @field_validator("birthdate", mode="before")
    @classmethod
    def validate_birthdate(cls, value):
        if value is None:
            return None

        if isinstance(value, datetime):
            parsed = value
        elif isinstance(value, date):
            parsed = datetime.combine(value, datetime.min.time())
        elif isinstance(value, str):
            for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d"):
                try:
                    parsed = datetime.strptime(value, fmt)
                    break
                except ValueError:
                    pass
            else:
                raise ValueError("birthdate must be in DD-MM-YYYY or DD/MM/YYYY format")
        else:
            raise ValueError("Invalid birthdate value")
        today = datetime.utcnow().date()
        if parsed.date() == today:
            raise ValueError("birthdate cannot be today's date")

        return parsed

    @field_validator(
        "country",
        "bio",
        "selfie_image",
        "interested_in",
        mode="before"
    )
    @classmethod
    def validate_non_empty_strings(cls, value, info):
        if value is None:
            return None

        if isinstance(value, str) and not value.strip():
            raise ValueError(f"{info.field_name} cannot be empty")

        return value.strip() if isinstance(value, str) else value

    @field_validator(
        "passions",
        "sexual_preferences",
        "images",
        "public_gallery",
        "private_gallery",
        "preferred_country",
        mode="before"
    )
    @classmethod
    def validate_list_fields(cls, value, info):
        if value is None:
            return None

        if not isinstance(value, list):
            raise ValueError(f"{info.field_name} must be a list")

        if len(value) == 0:
            raise ValueError(f"{info.field_name} cannot be an empty list")

        for v in value:
            if not isinstance(v, str) or not v.strip():
                raise ValueError(f"{info.field_name} contains empty or invalid values")

        return value


    @field_validator("onboarding_completed", mode="before")
    @classmethod
    def validate_onboarding_completed(cls, value):
        if value is None:
            return None
        if not isinstance(value, bool):
            raise ValueError("onboarding_completed must be boolean")
        return value


    class Config:
        use_enum_values = True
