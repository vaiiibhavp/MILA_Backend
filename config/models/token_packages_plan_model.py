from datetime import datetime, timezone
from typing import Any, Dict, Optional, List
from bson import ObjectId

from core.utils.pagination import StandardResultsSetPagination
from schemas.token_package_schema import TokenPackagePlanCreateModel, TokenPackagePlanUpdateRequestModel
from services.translation import translate_message
from core.utils.response_mixin import CustomResponseMixin
from config.db_config import token_packages_plan_collection
from core.utils.helper import convert_objectid_to_str, calculate_usdt_amount

response = CustomResponseMixin()

async def get_token_packages_plans(condition:dict, pagination:StandardResultsSetPagination | None = None):
    cursor = (
        token_packages_plan_collection.
        find(condition)
        .sort("created_at", -1)
    )
    # ✅ Apply pagination only if provided
    if pagination:
        cursor = (
            cursor
            .skip(pagination.skip)
            .limit(pagination.limit)
        )
        return await cursor.to_list(length=pagination.limit)

    # ✅ No pagination → return all
    return await cursor.to_list()

async def get_token_packages_plan(plan_id, lang:str) -> Any:
    """
        get token package plan by id
        """
    packages_plan_data = await token_packages_plan_collection.find_one({"_id": ObjectId(plan_id), "status": "active"})
    if not packages_plan_data:
        return response.error_message(
            translate_message("TOKEN_PACKAGE_PLAN_NOT_FOUND", lang=lang),
            data=[],
            status_code=404,
        )
    return packages_plan_data

async def store_token_packages_plan(doc:TokenPackagePlanCreateModel, admin_user:str) -> Any:
    doc = doc.model_dump()
    doc['created_by'] = ObjectId(admin_user)
    result = await token_packages_plan_collection.insert_one(doc)
    doc["_id"] = convert_objectid_to_str(result.inserted_id)
    return doc

async def get_token_packages_plan_details(
        condition: Dict[str, Any],
        fields: Optional[List[str]] = None
):
    projection = None
    if fields:
        projection = {field: 1 for field in fields}
        if "_id" not in fields:
            projection["_id"] = 0


    return await token_packages_plan_collection.find_one(
        condition,
        projection
    )

async def update_token_package_plan(
    plan_id: str,
    payload: TokenPackagePlanUpdateRequestModel,
    admin_user_id: str,
    lang: str
) -> Dict[str, Any]:
    """
    Fully update token package plan.
    """

    plan = await token_packages_plan_collection.find_one(
        {"_id": ObjectId(plan_id)}
    )

    if not plan:
        raise response.raise_exception(
            translate_message("TOKEN_PACKAGE_PLAN_NOT_FOUND", lang=lang),
            status_code=404
        )

    existing_plan = await token_packages_plan_collection.find_one({
        "title": payload.title.strip().title(),
        "_id": {"$ne": ObjectId(plan_id)}
    })

    if existing_plan:
        raise response.raise_exception(
            translate_message(
                "TOKEN_PACKAGE_PLAN_TITLE_ALREADY_EXISTS",
                lang=lang
            ),
            status_code=409
        )

    amount = calculate_usdt_amount(int(payload.tokens))
    update_doc = {
        "title": payload.title.strip().title(),
        "amount": str(amount),
        "tokens": str(payload.tokens),
        "status": payload.status,
        "updated_at": datetime.now(timezone.utc),
        "updated_by": ObjectId(admin_user_id)
    }

    await token_packages_plan_collection.update_one(
        {"_id": ObjectId(plan_id)},
        {"$set": update_doc}
    )

    updated = await token_packages_plan_collection.find_one(
        {"_id": ObjectId(plan_id)}
    )

    return {
        "_id": updated["_id"],
        "title": updated["title"],
        "amount": updated["amount"],
        "tokens": updated["tokens"],
        "status": updated["status"],
        "created_at": updated["created_at"],
        "updated_at": updated["updated_at"]
    }


async def soft_delete_token_package_plan(
    plan_id: str,
    admin_user_id: str,
    lang: str
):
    """
    Soft delete token package plan by marking it deleted.
    """

    plan = await token_packages_plan_collection.find_one({
        "_id": ObjectId(plan_id)
    })

    if not plan:
        raise response.raise_exception(
            translate_message("TOKEN_PACKAGE_PLAN_NOT_FOUND", lang=lang),
            status_code=404
        )

    if plan.get("deleted"):
        raise response.raise_exception(
            translate_message("TOKEN_PLAN_ALREADY_DELETED", lang=lang),
            status_code=400
        )

    await token_packages_plan_collection.update_one(
        {"_id": ObjectId(plan_id)},
        {
            "$set": {
                "deleted": True,
                "deleted_at": datetime.now(timezone.utc),
                "deleted_by": ObjectId(admin_user_id)
            }
        }
    )

    return {
        "id": str(plan["_id"]),
        "deleted": True
    }