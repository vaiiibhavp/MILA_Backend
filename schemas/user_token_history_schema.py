from datetime import datetime, timezone

from bson import ObjectId

from core.utils.core_enums import TokenTransactionType
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional

class CreateTokenHistory(BaseModel):
    user_id: str
    delta: int
    type: TokenTransactionType
    reason: str
    balance_before: str
    balance_after: str
    txn_id: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class TokenHistory(BaseModel):
    txn_id: Optional[str] = None
    user_id: str
    gift_username: Optional[str] = None
    plan_amount: Optional[float] = 0
    paid_amount: Optional[float] = 0
    remaining_amount: Optional[float] = 0
    delta: int
    type: str
    reason: str
    status: Optional[str] = None
    balance_before: str
    balance_after: str
    created_at: datetime

class TokenPlans(BaseModel):
    id: str = Field(alias="_id")
    title: str
    amount: str
    tokens: str
    status: str
    model_config = {
        "populate_by_name": True
    }

class TokenHistoryResponse(BaseModel):
    history: List[TokenHistory]
    available_tokens: str
    token_plans:List[TokenPlans]

class TokenTransactionRequestModel(BaseModel):
    tron_txn_id: str = Field(
        description="Tron USDT transaction value. "
    )
    package_id: str = Field(
        description="Token Purchased Package ID. "
    )

    @field_validator("package_id", "tron_txn_id")
    def not_empty(cls, value):
        if not value or not value.strip():
            raise ValueError("Field cannot be empty")
        return value

    @field_validator("package_id")
    def validate_package_id(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("package_id must be a valid ObjectId")
        return v

class CompleteTokenTransactionRequestModel(BaseModel):
    tron_txn_id: str = Field(
        description="Tron USDT transaction value. "
    )
    trans_id: str = Field(
        description="Transaction history _id field value. "
    )

    @field_validator("trans_id", "tron_txn_id")
    def not_empty(cls, value):
        if not value or not value.strip():
            raise ValueError("Field cannot be empty")
        return value

    @field_validator("trans_id")
    def validate_trans_id(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("trans_id must be a valid ObjectId")
        return v


class WithdrawnTokenRequestModel(BaseModel):
    amount: float = Field(
        description="Withdrawal amount in USD. Must be greater than 0."
    )
    wallet_address: str = Field(
        description="User Tron wallet address. "
    )

    @field_validator("amount")
    def validate_amount(cls, value: float):
        if value <= 0:
            raise ValueError("Amount must be greater than 0")
        return value

    @field_validator("wallet_address")
    def validate_wallet_address(cls, value: str):
        if not value or not value.strip():
            raise ValueError("Wallet address cannot be empty")
        return value.strip()


