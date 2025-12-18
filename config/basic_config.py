from pydantic_settings import BaseSettings
from fastapi import FastAPI
from typing import Optional
from fastapi.middleware.trustedhost import TrustedHostMiddleware
import os 
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv(override=True)  

#Define App
app = FastAPI()

# Get ALLOWED_HOSTS from the environment and split it into a list
allowed_hosts = os.getenv("ALLOWED_HOSTS")

print('allowed---hosts',allowed_hosts)

class Settings(BaseSettings):
    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str
 
    EMAIL_HOST: str
    EMAIL_PORT: int
    EMAIL_HOST_USER: str
    EMAIL_HOST_PASSWORD: str
    EMAIL_FROM: str
 
    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_DB: int
    VERIFICATION_TTL: int 
    RATE_LIMIT_MAX: int  
    RATE_LIMIT_PERIOD: int
    MONGO_HOST: str
    MONGO_PORT: int
    MONGO_DATABASE: str
    MONGO_USER: Optional[str] =None
    MONGO_PASSWORD: Optional[str] = None
    CELERY_PREFIX: str = "fastapi"  # Default to "fastapi" or use any other default logic

    ADMIN_NAME: str
    ADMIN_EMAIL: str
    ADMIN_PASSWORD: str
    RELOAD:bool

    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    RESET_TOKEN_EXPIRE_MINUTES: int = 10
    OTP_EXPIRE_MINUTES: int = 5
    PORT:int
    HOST:str
    SECRET_ACCESS_KEY: str
    SECRET_REFRESH_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    REFRESH_TOKEN_EXPIRE_MINUTES: int
    ALGORITHM: str
    ADMIN_WALLET_ADDRESS:str
    WALLET_NETWORK:str
    VERIFICATION_REWARD_TOKENS: int

    class ConfigDict:
        env_file = ".env"
        extra = "ignore"

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=allowed_hosts,
)
    
settings = Settings()
