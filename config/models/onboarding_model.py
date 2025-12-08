from pydantic import BaseModel, field_validator
from typing import Optional, List
from datetime import date, datetime
from enum import Enum

class GenderEnum(str, Enum):
    man = "man"
    woman = "woman"
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
    widowed = "widowed"

class InterestedInEnum(str , Enum):
    male = "male"
    female = "female"
    gay = "gay"


class OnboardingModel(BaseModel):
    user_id: str

    birthdate: Optional[datetime] = None
    gender: Optional[str] = None
    sexual_orientation: Optional[str] = None
    marital_status: Optional[str] = None

    city: Optional[str] = None
    bio: Optional[str] = None

    passions: List[str] = []
    interested_in: Optional[str] = None
    sexual_preferences: List[str] = []

    preferred_city: List[str] = None
    images: List[str] = []
    selfie_image: Optional[str] = None

    onboarding_completed: bool = False

    created_at: datetime = datetime.utcnow()
    updated_at: datetime = datetime.utcnow()


class OnboardingStepUpdate(BaseModel):
    birthdate: Optional[datetime] = None
    gender: Optional[GenderEnum] = None
    sexual_orientation: Optional[SexualOrientationEnum] = None
    marital_status: Optional[MaritalStatusEnum] = None
    city: Optional[str] = None
    bio: Optional[str] = None
    passions: Optional[List[str]] = None
    interested_in: Optional[InterestedInEnum] = None
    sexual_preferences: Optional[List[str]] = None
    preferred_city: Optional[List[str]] = None
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
            for fmt in ("%d-%m-%Y", "%d/%m/%Y"):
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
        "city",
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
        mode="before"
    )
    @classmethod
    def validate_lists(cls, value, info):
        if value is None:
            return None

        if not isinstance(value, list):
            raise ValueError(f"{info.field_name} must be a list")

        if len(value) == 0:
            raise ValueError(f"{info.field_name} cannot be empty")

        for item in value:
            if not isinstance(item, str) or not item.strip():
                raise ValueError(
                    f"{info.field_name} cannot contain empty values"
                )

        return value

    @field_validator("onboarding_completed", mode="before")
    @classmethod
    def validate_boolean(cls, value):
        if value is None:
            return value
        if not isinstance(value, bool):
            raise ValueError("onboarding_completed must be a boolean")
        return value

    class Config:
        use_enum_values = True