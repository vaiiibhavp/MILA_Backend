from datetime import datetime, timezone
from bson import ObjectId
from pydantic import BaseModel,Field, field_validator
from typing import Optional, List
from core.utils.core_enums import TransactionStatus

class TransactionRequestModel(BaseModel):
    txn_id: str
    plan_id: str

    @field_validator("txn_id", "plan_id")
    def not_empty(cls, value):
        if not value or not value.strip():
            raise ValueError("Field cannot be empty")
        return value

    @field_validator("plan_id")
    def validate_plan_id(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("plan_id must be a valid ObjectId")
        return v

class PaymentDetailsModel(BaseModel):
    txn_id: str = Field(alias="txid")
    status: str
    txn_from: str = Field(alias="from")
    contract_address: str
    is_trc20: bool
    txn_to: str = Field(alias="to")
    amount_units: float = 0.0
    amount: float = 0.0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Config:
        populate_by_name = True

class TransactionCreateModel(BaseModel):
    user_id: str
    plan_id: str
    plan_amount: float = 0.0
    paid_amount: float = 0.0
    remaining_amount: float = 0.0
    status: TransactionStatus
    payment_details: PaymentDetailsModel
    start_date: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    tokens:Optional[int] = 0
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
