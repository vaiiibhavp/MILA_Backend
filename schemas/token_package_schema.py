from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field, field_serializer, field_validator
from core.utils.core_enums import TokenPlanStatus


class TokenPackageCreateRequestModel(BaseModel):
    title: str = Field(description="Token package title")
    tokens: int = Field(gt=0, description="Number of tokens")

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
        return v.strip()