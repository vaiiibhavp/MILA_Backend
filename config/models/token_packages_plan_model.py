from config.db_config import token_packages_plan_collection

async def get_token_packages_plans():
    return await token_packages_plan_collection.find({'status':'active'}).to_list()