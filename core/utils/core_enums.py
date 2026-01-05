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
    PENDING = "pending"

class TokenTransactionReason(str, Enum):
    SUBSCRIPTION = "Purchased_Subscription_Plan"
    ACCOUNT_VERIFIED = "Account_Verified"
    TOKEN_PURCHASE = "Token_Purchase"

class LoginStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"

class TransactionType(str, Enum):
    SUBSCRIPTION_TRANSACTION = "subscription_transaction"
    TOKEN_TRANSACTION = "token_transaction"

class GiftStatusEnum(str, Enum):
    active = "active"
    inactive = "inactive"

class GiftTypeEnum(str, Enum):
    emoji = "emoji"
    image = "image"

class LanguageEnum(str, Enum):
    EN = "en"
    FR = "fr"