from fastapi import HTTPException, Security,Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt,JWTError
from config.db_config import user_collection , admin_collection
import os
from fastapi.responses import JSONResponse
from .response_mixin import CustomResponseMixin
from services.translation import translate_message

response = CustomResponseMixin()

SECRET_ACCESS_KEY = os.getenv("SECRET_ACCESS_KEY", " ")
ALGORITHM = "HS256"

#class for AdminPermission       
class AdminPermission:
    def __init__(self, allowed_roles):
        self.allowed_roles = allowed_roles
        self.http_bearer = HTTPBearer()

    async def __call__(self, credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer(auto_error=False))):
        
        if credentials is None:        
            return response.raise_exception(
                    message="No token provided. Authentication required.",
                    data={},
                    status_code=403
                )

        try:
            # Decode the JWT token
            payload = jwt.decode(credentials.credentials, SECRET_ACCESS_KEY, algorithms=[ALGORITHM])
            user = await admin_collection.find_one({"email": payload["sub"]})

            if not user:
                raise HTTPException(status_code=401, detail="Invalid user")

            # Debugging: Log the user role
            user_role = user.get("role")

            # Check if the user has the required role
            if user_role not in self.allowed_roles:
                return response.raise_exception(
                    message="You dont have enough permissions to perform this action",
                    data={},
                    status_code=403
                )

            return user

        except JWTError:
            return response.raise_exception(
                    message="Access Token Expired,please login",
                    data={},
                    status_code=401
                )


#class for UserPermission    
class UserPermission:
    def __init__(self, allowed_roles, require_verified: bool = False):
        self.allowed_roles = allowed_roles
        self.http_bearer = HTTPBearer()
        self.require_verified = require_verified

    async def __call__(self, credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer(auto_error=False))):
        
        if credentials is None:        
            return response.raise_exception(
                    message="No token provided. Authentication required.",
                    data=None,
                    status_code=403
                )

        try:
            # Decode the JWT token
            payload = jwt.decode(credentials.credentials, SECRET_ACCESS_KEY, algorithms=[ALGORITHM])
            user = await user_collection.find_one(
                {"email": payload["sub"]},
                {
                    "role": 1,
                    "is_deleted": 1,
                    "is_verified": 1,
                    "membership_type": 1
                }
            )
            if not user:
                raise HTTPException(status_code=401, detail="Invalid user")
            
            lang = payload.get("lang", "en")

            if user.get("is_deleted") is True:
                return response.raise_exception(
                    message=translate_message("ACCOUNT_IS_BEEN_DELETED", lang),
                    data=None,
                    status_code=401
                )
            # Debugging: Log the user role
            user_role = user.get("role")

            if not user_role:  # empty / None / "" / missing
                user_role = payload.get("role")

            # Check if the user has the required role
            if user_role not in self.allowed_roles:
                return response.raise_exception(
                    message="You dont have enough permissions to perform this action",
                    data=None,
                    status_code=403
                )

            if self.require_verified and not user.get("is_verified", False):
                return response.raise_exception(
                    message="Your account is not verified",
                    data=None,
                    status_code=403
                )
            return user

        except JWTError:
            return response.raise_exception(
                    message="Access Token Expired,please login",
                    data=None,
                    status_code=403
                )
 