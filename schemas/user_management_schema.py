from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class AdminUserListResponse(BaseModel):
    user_id: str
    username: str
    email: str
    membership_type: str
    is_verified: bool
    login_status: str
    gender: Optional[str]
    sexual_orientation: Optional[str]
    marital_status: Optional[str]
    country: Optional[str]
    created_at: datetime


class AdminUserDetailsResponse(BaseModel):
    user_id: str
    username: str
    email: str
    membership_type: str
    is_verified: bool
    login_status: str
    suspended_until: Optional[datetime]
    created_at: datetime

    gender: Optional[str]
    sexual_orientation: Optional[str]
    marital_status: Optional[str]
    country: Optional[str]
    bio: Optional[str]
    passions: Optional[List[str]]
    photos: Optional[List[dict]]


class SuspendUserRequest(BaseModel):
    days: int
