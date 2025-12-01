# exceptions.py

from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from typing import Optional   

# class for CustomValidationError
class CustomValidationError(HTTPException):
    def __init__(self, message: str, data: Optional[dict] = None, status_code: int = 400):
        self.message = message if message else "Something went wrong"
        self.data = data if isinstance(data, dict) else {}
        self.success = False
        self.status_code = status_code

        super().__init__(
            status_code=status_code,
            detail={
                "message": self.message,
                "data": self.data,
                "success": self.success,
                "status_code": self.status_code
            }
        )

# Exception handler for CustomValidationError
async def custom_validation_error_handler(request: Request, exc: CustomValidationError):
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.detail,
    )
# Custom exception handler for validation errors
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    
    # Extract field names and error messages
    formatted_errors = {err["loc"][-1]: err["msg"] for err in errors}  

    return JSONResponse(
        content={
            "message": "Validation Error",
            "data": {"errors": formatted_errors},  # More readable error structure
            "success": False
        },
        status_code=422  # Use 422 for validation errors
    )
