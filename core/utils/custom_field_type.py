from typing_extensions import Annotated
from pydantic.functional_validators import BeforeValidator
from core.utils.validator import (
    validate_email_value,
    validate_username_value,
    validate_password_value,
    validate_otp_4,
    validate_role_value,
)

EmailField = Annotated[str, BeforeValidator(validate_email_value)]
UsernameField = Annotated[str, BeforeValidator(validate_username_value)]
PasswordField = Annotated[str, BeforeValidator(validate_password_value)]
Otp4Field = Annotated[str, BeforeValidator(validate_otp_4)]
RoleField = Annotated[str, BeforeValidator(validate_role_value)]
