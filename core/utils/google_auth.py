import jwt
from fastapi import HTTPException
from core.utils.response_mixin import CustomResponseMixin

response = CustomResponseMixin()

def decode_google_id_token(id_token: str):
    """
    Decode Google ID token WITHOUT verifying signature (frontend handles verification).
    """
    try:
        data = jwt.decode(id_token, options={"verify_signature": False})

        email = data.get("email")
        if not email:
            return response.error_message("Google token does not contain email", status_code=400)

        return {
            "email": email,
            "name": data.get("name"),
            "picture": data.get("picture"),
            "google_id": data.get("sub"),
            "email_verified": data.get("email_verified", False)
        }

    except Exception as e:
        raise response.raise_exception("Invalid Google token", 
                                       data={str(e)},
                                       status_code=400
        )
