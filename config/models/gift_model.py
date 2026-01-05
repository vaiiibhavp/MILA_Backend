# gift_model.py

from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from config.models.user_models import PyObjectId
from core.utils.core_enums import *

class Gift(BaseModel):
    name: str
    file_id: PyObjectId
    token: int

    status: GiftStatusEnum = GiftStatusEnum.active

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @field_validator("code", "name", mode="before")
    @classmethod
    def validate_non_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("Field cannot be empty")
        return v.strip()

    @field_validator("price")
    @classmethod
    def validate_price(cls, v):
        if v <= 0:
            raise ValueError("Gift price must be greater than zero")
        return v

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        use_enum_values = True