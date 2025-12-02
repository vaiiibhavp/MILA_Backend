import os
import random
from jose import JWTError, jwt  # Change from regular jwt to jose.jwt
from redis import Redis
from dotenv import load_dotenv
from datetime import datetime, timedelta
from passlib.context import CryptContext
from typing import Optional
from config.basic_config import settings
from tasks import send_email_task
from .response_mixin import CustomResponseMixin
from schemas.tokens_schema import TokenData
from core.utils.redis_helper import store_in_redis, get_from_redis, delete_from_redis
from config.models.user_models import store_token
from config.basic_config import settings

load_dotenv()
response = CustomResponseMixin()

#Secret key for JWT access token and referesh token encoding and decoding
SECRET_ACCESS_KEY = settings.SECRET_ACCESS_KEY
SECRET_REFRESH_KEY = settings.SECRET_REFRESH_KEY
ALGORITHM = settings.ALGORITHM
# ACCESS_TOKEN_EXPIRE_MINUTES = 120 # 2hr time
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES
REFRESH_TOKEN_EXPIRE_MINUTES = settings.REFRESH_TOKEN_EXPIRE_MINUTES

if not (SECRET_ACCESS_KEY or SECRET_REFRESH_KEY):
    raise response.error_message("Cannot load JWT Secret key or Refresh key")

# Password hash context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# Function Password hashing
def get_hashed_password(password: str) -> str:
    return pwd_context.hash(password)


# Function to Verify password
def verify_password(plain_pwd, hashed_pwd) -> bool:
    return pwd_context.verify(plain_pwd, hashed_pwd)


# Function to Genrating access token
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> None:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_ACCESS_KEY, algorithm=ALGORITHM)
    return encoded_jwt


# Function to create_refresh_token
def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=REFRESH_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_REFRESH_KEY, algorithm=ALGORITHM)
    return encoded_jwt


# Function to verify a token and extract user info
def verify_token(token: str) -> TokenData:
    try:
        payload = jwt.decode(token, SECRET_ACCESS_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        user_id: str = payload.get("user_id")
        if username is None or user_id is None:
            return response.error_message("Invalid credentials", status_code=403)
        else:
            return response.success_message("Successfully loged In")
        return TokenData(username=username, user_id=user_id)
    except JWTError as e:
        return response.error_message("Invalid credentials", data=str(e), status_code=403)


# Function to generate_verification_code
def generate_verification_code(length: int =4) -> str:
    """
    Generate random 6 digit number
    """
    return ''.join(random.choices('0123456789', k=length))


# Function to send_email
async def send_email(to_email: str, subject: str, body: str, is_html: bool = False):
    send_email_task.delay(to_email, subject, body, is_html)


# Function to verify_refresh_token
def verify_refresh_token(refresh_token: str):
    payload = jwt.decode(refresh_token, SECRET_REFRESH_KEY, algorithms=[ALGORITHM])
    return payload  # This should include the token data

def generate_login_tokens(user):
    user_id = str(user["_id"])
    email = user["email"]

    user_data = {
        "sub": email,
        "user_id": user_id,
        "role": user.get("role", "user")
    }

    # Create tokens
    access_token = create_access_token(user_data)
    refresh_token = create_refresh_token(user_data)

    # Decode expiry times
    access_payload = jwt.decode(access_token, SECRET_ACCESS_KEY, algorithms=[ALGORITHM])
    refresh_payload = jwt.decode(refresh_token, SECRET_REFRESH_KEY, algorithms=[ALGORITHM])

    access_expire = datetime.fromtimestamp(access_payload["exp"])
    refresh_expire = datetime.fromtimestamp(refresh_payload["exp"])

    # Store tokens in DB
    store_token(
        user_id=user_id,
        email=email,
        access_token=access_token,
        refresh_token=refresh_token,
        access_token_expire=access_expire,
        refresh_token_expire=refresh_expire
    )

    return access_token, refresh_token

