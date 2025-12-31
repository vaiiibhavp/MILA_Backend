# schemas/profile_edit_schema.py

from pydantic import BaseModel
from typing import Optional, List

class EditProfileRequest(BaseModel):
    bio: Optional[str] = None
    country: Optional[str] = None
    gender: Optional[str] = None
    sexual_orientation: Optional[str] = None
    marital_status: Optional[str] = None

    passions: Optional[List[str]] = None
    interested_in: Optional[List[str]] = None
    preferred_country: Optional[List[str]] = None
    sexual_preferences: Optional[List[str]] = None

    wallet_address: Optional[str] = None
    two_factor_enabled: Optional[bool] = None
