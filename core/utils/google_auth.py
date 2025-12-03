import httpx
from fastapi import HTTPException
from config.basic_config import settings

GOOGLE_TOKEN_INFO_URL = settings.GOOGLE_TOKEN_INFO_URL

async def verify_google_id_token(id_token: str):
    """
    Verifies the Google ID token and returns raw Google user info.
    """
    async with httpx.AsyncClient() as client:
        google_response = await client.get(GOOGLE_TOKEN_INFO_URL + id_token)

    if google_response.status_code != 200:
        raise HTTPException(status_code=400, detail="Invalid Google ID token")

    data = google_response.json()

    if "email" not in data:
        raise HTTPException(status_code=400, detail="Google token missing email")

    return {  
        "email": data["email"],
        "name": data.get("name", ""),
        "picture": data.get("picture"),
        "email_verified": data.get("email_verified") == "true"
    }
