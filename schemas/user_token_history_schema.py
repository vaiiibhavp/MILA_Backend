from datetime import datetime, timezone
from core.utils.core_enums import TokenTransactionType
from pydantic import BaseModel,Field
from typing import Optional

class CreateTokenHistory(BaseModel):
    user_id: str
    delta: int
    type: TokenTransactionType
    reason: str
    balance_before: str
    balance_after: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

