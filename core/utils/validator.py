import re
from typing import Optional

from fastapi import Query
from core.utils.core_enums import TokenTransactionType


# ---------- EMAIL ----------
def validate_email_value(v: str) -> str:
    if not v or not v.strip():
        raise ValueError("EMAIL_REQUIRED")

    v = v.strip()

    if " " in v:
        raise ValueError("EMAIL_NO_SPACES")

    if v.count("@") != 1:
        raise ValueError("EMAIL_SINGLE_AT")

    local_part, domain_part = v.split("@")

    if not re.fullmatch(r"[A-Za-z0-9._-]+", local_part):
        raise ValueError("EMAIL_INVALID_LOCAL")

    if not re.fullmatch(r"[A-Za-z0-9.-]+\.[A-Za-z]{2,}", domain_part):
        raise ValueError("EMAIL_INVALID_DOMAIN")

    return v.lower()


# ---------- USERNAME ----------
def validate_username_value(v: str) -> str:
    if not v or not v.strip():
        raise ValueError("USERNAME_REQUIRED")

    v = v.strip()

    if len(v) < 3:
        raise ValueError("USERNAME_MIN_LENGTH")

    if not re.match(r"^[A-Za-z]", v):
        raise ValueError("USERNAME_START_LETTER")

    if not re.fullmatch(r"[A-Za-z0-9_]+", v):
        raise ValueError("USERNAME_INVALID_CHARS")

    return v


# ---------- PASSWORD ----------
def validate_password_value(v: str) -> str:
    if not v or not v.strip():
        raise ValueError("PASSWORD_REQUIRED")

    if len(v) < 8:
        raise ValueError("PASSWORD_MIN_LENGTH")

    if " " in v:
        raise ValueError("PASSWORD_NO_SPACES")

    if not re.search(r"[A-Z]", v):
        raise ValueError("PASSWORD_UPPERCASE")

    if not re.search(r"[a-z]", v):
        raise ValueError("PASSWORD_LOWERCASE")

    if not re.search(r"[0-9]", v):
        raise ValueError("PASSWORD_NUMBER")

    if not re.fullmatch(r"[.A-Za-z0-9]+", v):
        raise ValueError("PASSWORD_INVALID_CHARS")

    return v


# ---------- OTP ----------
def validate_otp_4(v: str) -> str:
    if not v or not v.strip():
        raise ValueError("OTP_REQUIRED")

    v = v.strip()

    if not v.isdigit():
        raise ValueError("OTP_DIGITS_ONLY")

    if len(v) != 4:
        raise ValueError("OTP_4_DIGITS")

    return v


# ---------- ROLE ----------
def validate_role_value(v: str) -> str:
    if not v or not v.strip():
        raise ValueError("ROLE_REQUIRED")

    v = v.strip().lower()
    allowed = {"admin", "user"}

    if v not in allowed:
        raise ValueError("ROLE_INVALID")

    return v


# ---------- TRANSACTION TYPE ----------
def normalize_transaction_type(
    transaction_type: Optional[str] = Query(
        None,
        description="Filter token history by transaction type : [CREDIT, DEBIT, WITHDRAW]",
        examples=["CREDIT", "DEBIT", "WITHDRAW"]
    )
) -> Optional[TokenTransactionType]:

    if transaction_type is None:
        return None

    try:
        return TokenTransactionType(transaction_type.upper())
    except ValueError:
        raise ValueError("INVALID_TRANSACTION_TYPE")