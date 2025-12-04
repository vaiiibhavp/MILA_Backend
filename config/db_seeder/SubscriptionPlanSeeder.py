from config.db_config import db
from datetime import datetime

subscription_plan_collection = db["subscription_plan"]

async def seed_subscription_plan():
    # sample plans to seed
    sample_plans = [
        {"title": "Monthly Plan", "amount": "9.90", "validity_value": "1", "validity_unit": "month"},
        {"title": "Semi-Annual Plan", "amount": "8.90", "validity_value": "6", "validity_unit": "month"},
        {"title": "Annual Plan", "amount": "7.90", "validity_value": "12", "validity_unit": "month"},
    ]

    for plan in sample_plans:

        existing_plan = await subscription_plan_collection.find_one(
            {"title": plan['title']},
        )

        if existing_plan:
            print(" Plan already exists")
            continue

        plan_doc = {
            "title": plan['title'],
            "amount": plan['amount'],
            "validity_value": plan['validity_value'],
            "validity_unit": plan['validity_unit'],
            "status":"active",
            "created_at": datetime.utcnow(),
        }

        await subscription_plan_collection.insert_one(plan_doc)
    print(" Plan seeded successfully")