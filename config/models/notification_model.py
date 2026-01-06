from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional
from core.utils.core_enums import NotificationType, NotificationRecipientType
from typing import Optional
from enum import Enum
from bson import ObjectId

class NotificationReference(BaseModel):
    entity: Optional[str] = None
    entity_id: Optional[str] = None

class Notification(BaseModel):

    recipient_id: str
    recipient_type: NotificationRecipientType

    type: NotificationType

    title: str
    message: str

    reference: Optional[NotificationReference] = None
    sender_user_id: Optional[str] = None

    is_read: bool = False
    read_at: Optional[datetime] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True
        populate_by_name = True

class DeviceType(str, Enum):
    IOS = "ios"
    ANDROID = "android"
    WEB = "web"
    DESKTOP = "desktop"

class DeviceStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    EXPIRED = "expired"

class FCMDeviceToken(BaseModel):
    user_id: str
    device_token: str
    device_type: Optional[DeviceType] = None
    device_name: Optional[str] = None  # e.g., "iPhone 12", "Samsung Galaxy"
    status: DeviceStatus = DeviceStatus.ACTIVE
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        allow_population_by_field_name = True
        json_encoders = {ObjectId: str}