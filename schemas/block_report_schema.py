from pydantic import BaseModel, Field

class BlockUserRequest(BaseModel):
    blocked_user_id: str = Field(...)

class ReportUserRequest(BaseModel):
    reported_user_id: str = Field(...)
    reason: str = Field(..., min_length=5)
