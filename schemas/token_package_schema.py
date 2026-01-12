from datetime import datetime, timezone

from bson import ObjectId
from pydantic import BaseModel, Field
from core.utils.core_enums import TokenPlanStatus


class TokenPackageCreateRequestModel(BaseModel):
    title: str = Field(description="Token package title")
    amount: float = Field(gt=0, description="Amount in USD")
    tokens: int = Field(gt=0, description="Number of tokens")

class TokenPackagePlanCreateModel(BaseModel):
    title: str
    amount: float
    tokens: int
    status: str = Field(default=TokenPlanStatus.active.value)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: ObjectId = Field(default_factory=ObjectId)
    updated_at: datetime = None
    updated_by: ObjectId = None

class TokenPackagePlanResponseModel(BaseModel):
    id: str = Field(alias="_id")
    title: str
    amount: str
    tokens: str
    status: str
    createdAt: datetime
    updatedAt: datetime
    model_config = {
        "populate_by_name": True
    }