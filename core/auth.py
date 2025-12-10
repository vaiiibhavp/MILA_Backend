from fastapi import Depends, HTTPException, status
from jose import jwt, JWTError
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from bson import ObjectId
from config.basic_config import settings
from config.db_config import user_collection

bearer_scheme = HTTPBearer(auto_error=True)

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)
):
    """
    Authenticate and return the current user based on the JWT access token.

    Purpose:
    ----------
    This function serves as a FastAPI dependency that protects routes.
    It verifies the incoming Bearer token, decodes the JWT, validates
    the user, and returns the authenticated user's database document.

    This ensures only logged-in users can access protected endpoints.

    Workflow:
    ----------
    1. Extract Bearer Token:
       - Uses FastAPI's HTTPBearer dependency to fetch the Authorization header.
       - Extracts `credentials.credentials` which contains the raw JWT token.

    2. Decode and validate JWT:
       - Uses `jose.jwt.decode()` with:
            * SECRET_ACCESS_KEY
            * selected JWT algorithm (HS256)
            * expiration verification enabled
       - If token is expired or invalid → raises 401 Unauthorized.

    3. Extract user_id from token payload:
       - The JWT must include `"user_id"`.
       - If missing → token is invalid → 401 Unauthorized.

    4. Validate user in database:
       - Converts `user_id` into a Mongo `ObjectId`.
       - Fetches the user document from `user_collection`.
       - If not found or ObjectId is invalid → 401 Unauthorized.

    5. Return the authenticated user:
       - The returned user object is injected into route handlers
         via FastAPI dependency injection.

    """
    token = credentials.credentials

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_ACCESS_KEY,      
            algorithms=[settings.JWT_ALGORITHM],
            options={"verify_exp": True}
        )
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )

    user_id = payload.get("user_id")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: user_id missing"
        )

    try:
        user = await user_collection.find_one({"_id": ObjectId(user_id)})
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user id format"
        )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    return user
