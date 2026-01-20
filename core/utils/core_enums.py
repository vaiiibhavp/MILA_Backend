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
    WITHDRAW= "WITHDRAW"

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

class NotificationRecipientType(str, Enum):
    USER = "user"
    ADMIN = "admin"

class NotificationType(str, Enum):
    REGISTRATION = "registration"
    PROFILE_VERIFICATION = "profile_verification"
    MATCH = "match"
    MESSAGE = "message"
    PROFILE_VIEW = "profile_view"
    SUBSCRIPTION = "subscription"
    SUBSCRIPTION_EXPIRY = "subscription_expiry"
    REPORT = "report"
    BLOCK = "block"
    TOKEN_WITHDRAW_STATUS = "token_withdrawn_status_updated"

class VerificationStatusEnum(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUSPENDED = "suspended"
    DELETED = "deleted"
    BLOCKED = "blocked"


class ContestStatus(str, Enum):
    registration_open = "registration_open"
    registration_closed = "registration_closed"
    voting_started = "voting_started"
    voting_closed = "voting_closed"
    winner_announced = "winner_announced"

class ContestFrequency(str, Enum):
    weekly = "weekly"
    bi_weekly = "bi_weekly"
    monthly = "monthly"
    three_months = "three_months"
    
class ContestVisibility(str, Enum):
    upcoming = "upcoming"
    in_progress = "in_progress"
    completed = "completed"

class ContestType(str, Enum):
    active = "active"
    past = "past"

class TokenPlanStatus(str, Enum):
    active = "active",
    inactive = "inactive",

class WithdrawalStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    completed = "completed"