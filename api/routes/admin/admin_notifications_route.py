from fastapi import APIRouter , Query ,Depends
from core.utils.permissions import AdminPermission
from api.controller.admin.admin_notifications_controller import (
    get_admin_notifications_controller,
    mark_admin_notification_read,
    mark_all_admin_notifications_read
)

router = APIRouter()



@router.get("/admin/notifications")
async def get_admin_notifications(
    current_admin: dict = Depends(AdminPermission(["admin"])),
    lang: str = Query("en")
):
    return await get_admin_notifications_controller(current_admin, lang)


@router.patch("/admin/read/{notification_id}")
async def read_single_admin_notification(
    notification_id: str,
    current_admin: dict = Depends(AdminPermission(["admin"])),
    lang: str = Query("en")
):
    return await mark_admin_notification_read(
        notification_id=notification_id,
        current_admin=current_admin,
        lang=lang
    )


@router.patch("/admin/read-all")
async def read_all_admin_notifications(
    current_admin: dict = Depends(AdminPermission(["admin"])),
    lang: str = Query("en")
):
    return await mark_all_admin_notifications_read(
        current_admin=current_admin,
        lang=lang
    )