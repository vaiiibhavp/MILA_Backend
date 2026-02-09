import re
from typing import Optional

from fastapi import Query

from core.utils.core_enums import TokenTransactionType


# ---------- EMAIL ----------
def validate_email_value(v: str) -> str:
    if not v or not v.strip():
        raise ValueError("Email is required.")

    v = v.strip()

    if " " in v:
        raise ValueError("Email cannot contain spaces.")

    if v.count("@") != 1:
        raise ValueError("Email must contain a single '@' symbol.")

    local_part, domain_part = v.split("@")

    if not re.fullmatch(r"[A-Za-z0-9._-]+", local_part):
        raise ValueError(
            "Email can contain only letters, numbers, '.', '_', '-' before '@'."
        )

    if not re.fullmatch(r"[A-Za-z0-9.-]+\.[A-Za-z]{2,}", domain_part):
        raise ValueError("Invalid email domain. Example: user@domain.com")

    return v.lower()


# ---------- USERNAME ----------
def validate_username_value(v: str) -> str:
    if not v or not v.strip():
        raise ValueError("Username is required.")

    v = v.strip()

    if len(v) < 3:
        raise ValueError("Username must be at least 3 characters long.")

    if not re.match(r"^[A-Za-z]", v):
        raise ValueError("Username must start with a letter (A–Z or a–z).")

    if not re.fullmatch(r"[A-Za-z0-9_]+", v):
        raise ValueError("Username can contain only letters, numbers, and underscores (_).")

    return v


# ---------- PASSWORD ----------
def validate_password_value(v: str) -> str:
    if not v or not v.strip():
        raise ValueError("Password is required.")

    if len(v) < 8:
        raise ValueError("Password must be at least 8 characters.")

    if " " in v:
        raise ValueError("Password cannot contain spaces.")

    if not re.search(r"[A-Z]", v):
        raise ValueError("Password must include an uppercase letter.")

    if not re.search(r"[a-z]", v):
        raise ValueError("Password must include a lowercase letter.")

    if not re.search(r"[0-9]", v):
        raise ValueError("Password must include a number.")

    if not re.fullmatch(r"[.A-Za-z0-9]+", v):
        raise ValueError("Password contains invalid characters.")

    return v


# ---------- OTP ----------
def validate_otp_4(v: str) -> str:
    # Required check
    if not v or not v.strip():
        raise ValueError("OTP is required.")

    v = v.strip()

    # Digits only
    if not v.isdigit():
        raise ValueError("OTP must contain only digits.")

    # Exact length
    if len(v) != 4:
        raise ValueError("OTP must be 4 digits.")

    return v


# ---------- ROLE ----------
def validate_role_value(v: str) -> str:
    if not v or not v.strip():
        raise ValueError("Role is required.")

    v = v.strip().lower()
    allowed = {"admin", "user"}

    if v not in allowed:
        raise ValueError(f"Invalid role. Must be one of: {', '.join(allowed)}")

    return v

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
        raise ValueError(
            f"Invalid transaction_type. Allowed values: {[e.value for e in TokenTransactionType]}"
        )
