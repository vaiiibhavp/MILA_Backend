# from pymongo.mongo_client import MongoClient
from motor.motor_asyncio import AsyncIOMotorClient  #for the cron job to query in scheuler
from config.basic_config import settings
from urllib.parse import quote_plus
from pymongo import ASCENDING, DESCENDING
import asyncio

#uri = "mongodb://localhost:27017/"

# Construct MongoDB URI using settings variables
if settings.MONGO_USER and settings.MONGO_PASSWORD:
    username = quote_plus(settings.MONGO_USER)
    password = quote_plus(settings.MONGO_PASSWORD)
    uri = f"mongodb://{username}:{password}@{settings.MONGO_HOST}:{settings.MONGO_PORT}/{settings.MONGO_DATABASE}"
    print('db compass url dev-----------------------',uri)

else:
    uri = f"mongodb://{settings.MONGO_HOST}:{settings.MONGO_PORT}"
    print('db compass url local-----------------------',uri)

# Singleton MongoDB client with optimized connection pooling
class MongoDBClient:
    _instance = None
    _client = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MongoDBClient, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._client is None:
            self._client = AsyncIOMotorClient(
                uri,
                maxPoolSize=100,  # Increased from 50 for better performance
                minPoolSize=20,   # Increased from 10 for better performance
                maxIdleTimeMS=30000,  # Close connections after 30 seconds of inactivity
                serverSelectionTimeoutMS=5000,  # Timeout for server selection
                connectTimeoutMS=10000,  # Connection timeout
                # socketTimeoutMS=30000,  # Socket timeout
                 socketTimeoutMS=300000,  # Socket timeout
                retryWrites=True,  # Enable retry for write operations
                retryReads=True,  # Enable retry for read operations
                compressors="zlib",  # Enable compression
                waitQueueTimeoutMS=5000,  # Wait queue timeout
                maxConnecting=10  # Maximum concurrent connection attempts
            )
            print("✅ MongoDB client initialized with optimized connection pooling")
    
    @property
    def client(self):
        return self._client
    
    async def close(self):
        """Close MongoDB connections properly"""
        if self._client:
            self._client.close()
            print("✅ MongoDB connections closed")
    
    async def ping(self):
        """Test database connectivity"""
        try:
            await self._client.admin.command('ping')
            print("✅ MongoDB connection test successful")
            return True
        except Exception as e:
            print(f"❌ MongoDB connection test failed: {e}")
            return False

# Create singleton instance
mongodb_client = MongoDBClient()
client = mongodb_client.client
db = client[settings.MONGO_DATABASE]

# Collection definitions
user_collection = db["users"]
token_collection = db["tokens"]
file_collection = db["files"]
admin_collection = db["Admin"]
subscription_plan_collection = db["subscription_plan"]
onboarding_collection = db["user_onboarding"]
transaction_collection = db["transaction"]
system_config_collection = db["system_config"]
user_token_history_collection = db["user_token_history"]
token_packages_plan_collection = db["token_packages_plan"]
countries_collection = db["countries"]
interest_categories_collection = db["interest_categories"]
user_like_history = db["user_like_history"]
favorite_collection = db["favorite_collection"]
user_match_history = db["users_matched_history"]
user_passed_hostory = db["user_passed_history"]
gift_collection = db["gifts"]
profile_view_history = db["profile_view_history"]
blocked_users_collection = db["blocked_users_history"]
reported_users_collection = db["reported_users_history"]
withdraw_token_transaction_collection = db["withdraw_token_transaction"]
notification_collection = db["notifications"]
fcm_device_tokens_collection = db["fcm_device_tokens"]
private_gallery_purchases_collection = db["private_gallery_purchases"]
verification_collection = db["verification_history"]
user_suspension_collection = db["user_suspension"]
admin_blocked_users_collection = db["admin_blocked_users_history"]
deleted_account_collection = db["deleted_accounts"]
contest_collection = db["contests"]
contest_participant_collection = db["contests_participants"]
contest_history_collection = db["contest_history"]
contest_vote_collection = db["contest_vote"]
daily_action_history = db["daily_action_history"]
gift_transaction_collection = db["gift_transaction"]
chat_audio_collection = db["chat_audio_files"]

async def create_indexes():
    """
    Placeholder for database indexes.
    Currently no indexes are created.
    """
    try:
        print("🔧 Creating database indexes...")

        # Favorites
        await favorite_collection.create_index(
            [("user_id", 1), ("favorite_user_ids", 1)],
            name="idx_favorite_user"
        )

        # Likes (core matching logic)
        await user_like_history.create_index(
            [("user_id", 1), ("liked_by_user_ids", 1)],
            name="idx_user_likes"
        )

        # Matches (prevent duplicate matches)
        existing_indexes = await user_match_history.index_information()
        if "idx_unique_user_match" in existing_indexes:
            await user_match_history.drop_index("idx_unique_user_match")

        await user_match_history.create_index(
            [("pair_key", 1)],
            unique=True,
            name="idx_unique_pair_key"
        )

        # Passed users
        await user_passed_hostory.create_index(
            [("user_id", 1), ("passed_user_ids", 1)],
            name="idx_user_passed"
        )

        # Onboarding (token & profile fetch)
        await onboarding_collection.create_index(
            [("user_id", 1)],
            name="idx_onboarding_user"
        )

        print("✅ Database indexes created successfully")
        await user_token_history_collection.create_index(
            [("user_id", ASCENDING), ("created_at", DESCENDING)],
            name="user_id_created_at_idx"
        )
        return True

    except Exception as e:
        print(f"❌ Error creating indexes: {e}")
        return False

        
async def initialize_database():
    """Initialize database connection and test connectivity"""
    try:
        # Test the connection during startup
        is_connected = await mongodb_client.ping()
        if is_connected:
            print("✅ MongoDB connection established successfully!")
            return True
        else:
            print("❌ Failed to establish MongoDB connection")
            return False
    except Exception as e:
        print(f"❌ Database initialization error: {e}")
        return False

async def close_database():
    """Close database connections properly"""
    try:
        await mongodb_client.close()
        print("✅ Database connections closed successfully")
    except Exception as e:
        print(f"❌ Error closing database connections: {e}")

        