from config.basic_config import settings
# from db_config import db
from config.db_config import db
from core.security import hash_password
from datetime import datetime

admin_collection = db["Admin"]

async def seed_admin():
    existing_admin = await admin_collection.find_one(
        {"email": settings.ADMIN_EMAIL}
    )

    if existing_admin:
        print(" Admin already exists")
        return

    admin_doc = {
        "name": settings.ADMIN_NAME,
        "email": settings.ADMIN_EMAIL,
        "password": hash_password(settings.ADMIN_PASSWORD),
        "role":"admin",
        "created_at": datetime.utcnow(),
    }

    await admin_collection.insert_one(admin_doc)
    print(" Admin seeded successfully")
