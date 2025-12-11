from config.db_config import user_token_history_collection
from schemas.user_token_history_schema import CreateTokenHistory

async def create_user_token_history(data:CreateTokenHistory):
    await user_token_history_collection.insert_one(data.model_dump())
