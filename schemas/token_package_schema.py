import re
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field, field_serializer, field_validator
from core.utils.core_enums import TokenPlanStatus


class TokenPackageCreateRequestModel(BaseModel):
    title: str = Field(description="Token package title")
    tokens: int = Field(gt=0, description="Number of tokens")

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str):
        if not v or not v.strip():
            raise ValueError("Title cannot be empty")

        v = v.strip()

        # ✅ Must contain at least one alphabet
        if not re.search(r"[A-Za-z]", v):
            raise ValueError(
                "Title must contain at least one alphabet character"
            )

        return v

    @field_validator("tokens", mode="before")
    @classmethod
    def validate_tokens(cls, v):
        # If value comes as string
        if isinstance(v, str):
            if not v.isdigit():
                raise ValueError("Tokens must be a valid number")

            if len(v) > 1 and v.startswith("0"):
                raise ValueError("Tokens value must not start with zero")

            v = int(v)

        if v <= 0:
            raise ValueError("Tokens must be greater than zero")

        return v

class TokenPackagePlanCreateModel(BaseModel):
    title: str
    amount: str
    tokens: str
    status: str = Field(default=TokenPlanStatus.active.value)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: None = None
    updated_by: None = None

class TokenPackagePlanResponseModel(BaseModel):
    id: str = Field(alias="_id")
    title: str
    amount: str
    tokens: str
    status: str
    created_at: str
    updated_at: str | None = None

    @field_validator("amount", "tokens", mode="before")
    @classmethod
    def convert_to_str(cls, v):
        return str(v) if v is not None else v

    model_config = {
        "populate_by_name": True
    }

class TokenPackagePlanUpdateRequestModel(BaseModel):
    """
    PUT a request model for updating token package plan.
    All fields are required for update.
    """
    title: str = Field(None, description="Token package title")
    tokens: int = Field(None, gt=0, description="Number of tokens")
    status: TokenPlanStatus = Field(None, description="Plan status (active/inactive)")

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str):
        if not v or not v.strip():
            raise ValueError("Title cannot be empty")
        v = v.strip()

        # ✅ Must contain at least one alphabet
        if not re.search(r"[A-Za-z]", v):
            raise ValueError(
                "Title must contain at least one alphabet character"
            )
        return v

    @field_validator("tokens", mode="before")
    @classmethod
    def validate_tokens(cls, v):
        # If value comes as string
        if isinstance(v, str):
            if not v.isdigit():
                raise ValueError("Tokens must be a valid number")

            if len(v) > 1 and v.startswith("0"):
                raise ValueError("Tokens value must not start with zero")

            v = int(v)

        if v <= 0:
            raise ValueError("Tokens must be greater than zero")

        return v

class TokenPackagePlanListResponseModel(BaseModel):
    id: str = Field(alias="_id")
    title: str
    amount: str
    tokens: str
    status: str
    created_at: str
    updated_at: str

    model_config = {
        "populate_by_name": True
    }