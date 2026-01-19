from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from core.utils.core_enums import WithdrawalStatus


class AdminWithdrawalUpdateModel(BaseModel):
    status: WithdrawalStatus
    paid_amount: float = Field(..., ge=0)
    platform_fee: float = Field(default=0, ge=0)
    tron_fee: float = Field(default=0, ge=0)
    payment_details: List[dict] = Field(default_factory=list)

class AdminWithdrawalResponseModel(BaseModel):
    id: str = Field(alias="_id")
    user_id: str
    request_amount: float
    paid_amount: float
    remaining_amount: float
    status: str
    wallet_address: str
    platform_fee: float
    tron_fee: float
    tokens: int
    created_at: str
    updated_at: str

    model_config = {"populate_by_name": True}

