from fastapi.responses import JSONResponse
from .exceptions import CustomValidationError
from typing import Optional

#class for CustomResponseMixin
class CustomResponseMixin:
    def success_message(self, message: str, data: Optional[dict] = None, status_code: int = 200):
        return JSONResponse(
            content={
                "message": message,
                "data": data if isinstance(data, dict) else {},
                "success": True,
                "status_code": status_code,
            },
            status_code=status_code,
        )
    
    def error_message(self, message: str, data: Optional[dict] = None, status_code: int = 400):
        return JSONResponse(
            content={
                "message": message,
                "data": data if isinstance(data, dict) else {},
                "success": False,
                "status_code": status_code,
            },
            status_code=status_code,
        )

    def raise_exception(self, message: str, data: Optional[dict] = None, status_code: int = 400):
        if data is None:
            data = {}
        elif not isinstance(data, dict):
            data = {"error": str(data)}

        raise CustomValidationError(
            message=message,
            data=data,
            status_code=status_code
        )
