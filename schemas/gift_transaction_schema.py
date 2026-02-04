from pydantic import BaseModel, Field
from typing import Optional, Dict
from datetime import datetime

class GiftTransactionCreate(BaseModel):
    sender_id: str
    receiver_id: str
    gift_id: str
    gift_name: str
    gift_token_value: int

    sender_balance_before: int
    sender_balance_after: int
    receiver_balance_before: int
    receiver_balance_after: int

    status: str = Field(default="completed")
    created_at: datetime = Field(default_factory=datetime.utcnow)
