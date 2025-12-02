from pydantic import BaseModel,Field, EmailStr,field_validator,validator,model_validator
from tasks import send_email_task
from typing import Optional
import re
from datetime import datetime
from enum import Enum

#UserLogin Schema 
class UserLogin(BaseModel):
    email: str = Field(..., description="User email address")
    password: str = Field(..., description="User password")
    role: str = Field(..., description="User role for validation")
    is_test: Optional[bool] = False  # Defaults to False if not provided
    
    @field_validator("email")
    def validate_email(cls, v):
        """Ensure email is not empty and properly formatted."""
        if not v or not v.strip():
            raise ValueError("Email is required")
        return v.strip()
    
    @field_validator("password")
    def validate_password(cls, v):
        """Ensure password is not empty."""
        if not v or not v.strip():
            raise ValueError("Password is required")
        return v.strip()
    
    @field_validator("role")
    def validate_role(cls, v):
        """Ensure role is valid and not empty."""
        if not v or not v.strip():
            raise ValueError("Role is required")
        valid_roles = ["admin", "user"]
        if v.strip().lower() not in valid_roles:
            raise ValueError(f"Invalid role. Must be one of: {', '.join(valid_roles)}")
        return v.strip().lower()

#RefreshTokenRequest Schema 
class RefreshTokenRequest(BaseModel):
    refresh_token: str


#LogoutRequest Schema 
class LogoutRequest(BaseModel):
    refresh_token: str


# Request Reset Password Schema
class RequestResetPassword(BaseModel):
    email: str

    @field_validator("email")
    def validate_email(cls, v):
        if " " in v:
            raise ValueError("Email cannot contain spaces.")
        if "@" not in v:
            raise ValueError("Email must contain '@' symbol.")
        try:
            local_part, domain = v.split("@")
        except ValueError:
            raise ValueError("Email must contain only one '@' symbol.")
        if not re.fullmatch(r"[A-Za-z0-9._-]+", local_part):
            raise ValueError(
                "Only letters, numbers, '.', '_', '-' are allowed before '@'."
            )
        if not re.fullmatch(r"[A-Za-z0-9.]+", domain):
            raise ValueError(
                "Domain part can only contain letters, numbers, and dots ('.')."
            )
        if "." not in domain:
            raise ValueError("Domain must contain a dot (example: domain.com).")
        if not re.fullmatch(r"[A-Za-z0-9]+\.[A-Za-z]{2,}", domain):
            raise ValueError("Invalid domain format. Example: user@domain.com")
        return v


# Password Reset Request Schema
class ForgotPasswordOtpVerify(BaseModel):
    reset_otp: str
    email: str

    @field_validator("reset_otp")
    def validate_reset_otp(cls, v):
        if not v or not v.strip():
            raise ValueError("Reset OTP cannot be empty.")
        if not v.isdigit():
            raise ValueError("Reset OTP must contain only digits.")
        if len(v) != 6:
            raise ValueError("Reset OTP must be exactly 6 digits.")
        return v


    @field_validator("email")
    def validate_email(cls, v):
        if " " in v:
            raise ValueError("Email cannot contain spaces.")
        if "@" not in v:
            raise ValueError("Email must contain '@' symbol.")
        try:
            local_part, domain = v.split("@")
        except ValueError:
            raise ValueError("Email must contain only one '@' symbol.")
        if not re.fullmatch(r"[A-Za-z0-9._-]+", local_part):
            raise ValueError(
                "Only letters, numbers, '.', '_', '-' are allowed before '@'."
            )
        if not re.fullmatch(r"[A-Za-z0-9.]+", domain):
            raise ValueError(
                "Domain part can only contain letters, numbers, and dots ('.')."
            )
        if "." not in domain:
            raise ValueError("Domain must contain a dot (example: domain.com).")
        if not re.fullmatch(r"[A-Za-z0-9]+\.[A-Za-z]{2,}", domain):
            raise ValueError("Invalid domain format. Example: user@domain.com")
        return v
    

class Signup(BaseModel):
    username: str
    email: EmailStr
    password: str
    confirm_password: str

    @field_validator("username")
    def validate_username(cls, v):
        v = v.strip()
        if len(v) < 3:
            raise ValueError("Username must be at least 3 characters long.")
        if not re.match(r"^[A-Za-z]", v):
            raise ValueError("Username must start with a letter (A–Z or a–z).")
        if not re.fullmatch(r"[A-Za-z0-9_]+", v):
            raise ValueError("Username can contain only letters, numbers, and underscores (_).")
        return v

    @field_validator("password")
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters.")
        if " " in v:
            raise ValueError("Password cannot contain spaces.")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must include an uppercase letter.")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must include a lowercase letter.")
        if not re.search(r"[0-9]", v):
            raise ValueError("Password must include a number.")
        if not re.search(r"[!@#$%^&*]", v):
            raise ValueError("Password must include a special character.")
        if not re.fullmatch(r"[A-Za-z0-9!@#$%^&*]+", v):
            raise ValueError("Password contains invalid characters.")
        return v

    @model_validator(mode="after")
    def check_passwords(self):
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match.")
        return self

class VerifyOTP(BaseModel):
    email: EmailStr
    otp: str

    @field_validator("otp")
    def validate_otp(cls, v):
        if not re.match(r"^\d{4}$", v):
            raise ValueError("OTP must be 4 digits.")
        return v

class ResendOTP(BaseModel):
    email: EmailStr

class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    remember_me: bool = False

    @field_validator("password")
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters.")
        if " " in v:
            raise ValueError("Password cannot contain spaces.")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must include an uppercase letter.")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must include a lowercase letter.")
        if not re.search(r"[0-9]", v):
            raise ValueError("Password must include a number.")
        if not re.search(r"[!@#$%^&*]", v):
            raise ValueError("Password must include a special character.")
        if not re.fullmatch(r"[A-Za-z0-9!@#$%^&*]+", v):
            raise ValueError("Password contains invalid characters.")
        return v
    
class VerifyLoginOtpRequest(BaseModel):
    email: EmailStr
    otp: str

    @field_validator("otp")
    def validate_otp(cls, v):
        if not re.match(r"^\d{4}$", v):
            raise ValueError("OTP must be 4 digits.")
        return v
    
class ResendOtpRequest(BaseModel):
    email: EmailStr

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class VerifyResetOtpRequest(BaseModel):
    email: EmailStr
    otp: str

class ResetPasswordRequest(BaseModel):
    email: EmailStr
    new_password: str
    confirm_password: str

    @field_validator("new_password")
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters.")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must include an uppercase letter.")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must include a lowercase letter.")
        if not re.search(r"[0-9]", v):
            raise ValueError("Password must include a number.")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", v):
            raise ValueError("Password must include a special character.")
        return v

    @model_validator(mode="after")
    def check_passwords(self):
        if self.new_password != self.confirm_password:
            raise ValueError("Passwords do not match.")
        return self