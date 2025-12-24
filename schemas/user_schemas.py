from pydantic import BaseModel,Field,field_validator,validator,model_validator
from tasks import send_email_task
from typing import Optional
import re
from datetime import datetime
from enum import Enum
from core.utils.custom_field_type import *

#UserLogin Schema 
class UserLogin(BaseModel):
    email: EmailField
    password: PasswordField
    role: RoleField
    is_test: Optional[bool] = False  # Defaults to False if not provided

#RefreshTokenRequest Schema 
class RefreshTokenRequest(BaseModel):
    refresh_token: str


#LogoutRequest Schema 
class LogoutRequest(BaseModel):
    refresh_token: str


# Request Reset Password Schema
class RequestResetPassword(BaseModel):
    email: EmailField

# Password Reset Request Schema
class ForgotPasswordOtpVerify(BaseModel):
    reset_otp: Otp4Field
    email: EmailField

class Signup(BaseModel):
    username: UsernameField
    email: EmailField
    password: PasswordField
    confirm_password: str

    @model_validator(mode="after")
    def check_passwords(self):
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match.")
        return self

class VerifyOTP(BaseModel):
    email: EmailField
    otp: Otp4Field

class ResendOTP(BaseModel):
    email: EmailField

class LoginRequest(BaseModel):
    email: EmailField
    password: PasswordField
    remember_me: bool = False
    
class VerifyLoginOtpRequest(BaseModel):
    email: EmailField
    otp: Otp4Field
    
class ResendOtpRequest(BaseModel):
    email: EmailField

class ForgotPasswordRequest(BaseModel):
    email: EmailField

class VerifyResetOtpRequest(BaseModel):
    email: EmailField
    otp: Otp4Field

class ResetPasswordRequest(BaseModel):
    email: EmailField
    new_password: PasswordField
    confirm_password: str

    @model_validator(mode="after")
    def check_passwords(self):
        if self.new_password != self.confirm_password:
            raise ValueError("Passwords do not match.")
        return self
    
class GoogleLoginRequest(BaseModel):
    email: EmailField
    name: Optional[str] = None
    google_id: str

class AppleLoginRequest(BaseModel):
    email: EmailField
    name: Optional[str] = None
    apple_id: str