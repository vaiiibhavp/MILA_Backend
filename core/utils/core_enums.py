from enum import Enum

class MembershipType(str,Enum):
    PREMIUM = "premium"
    FREE = "free"

class MembershipStatus(str,Enum):
    ACTIVE = "active"
    EXPIRED = "expired"

class TokenTransactionType(str, Enum):
    CREDIT = "CREDIT"
    DEBIT = "DEBIT"

class TransactionStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial payment"

class TokenTransactionReason(str, Enum):
    SUBSCRIPTION = "Purchased Subscription Plan"
    ACCOUNT_VERIFIED = "Account Verified"