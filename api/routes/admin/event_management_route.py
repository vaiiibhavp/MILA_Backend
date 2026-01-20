from fastapi import APIRouter, Depends , File , Query ,Body
from datetime import datetime
from core.utils.permissions import AdminPermission
from core.utils.core_enums import ContestVisibility ,ContestFrequency
from core.utils.pagination import StandardResultsSetPagination ,pagination_params
from schemas.event_management_schema import ContestCreateSchema ,ContestUpdateSchema
from api.controller.admin.event_management_controller import create_contest ,upload_contest_banner  ,fetch_contests ,get_contest_details_controller ,update_contest_controller,delete_contest_controller,get_contest_participants_controller
from fastapi import UploadFile


admin_router = APIRouter(prefix="/admin/contests", tags=["Admin Contests"])


@admin_router.post("/create")
async def create_new_contest(
    payload: ContestCreateSchema,
    lang: str = "en",
    admin: dict = Depends(AdminPermission(allowed_roles=["admin"]))
):
    return await create_contest(
        payload=payload,
        admin_id=str(admin["_id"]),
        lang=lang
    )

@admin_router.post("/upload-banner")
async def upload_contest_banner_route(
    image: UploadFile = File(...),
    admin: dict = Depends(AdminPermission(allowed_roles=["admin"]))
):
    return await upload_contest_banner(
        image=image,
        admin=admin
    )


@admin_router.get("/list")
async def get_contests(
    search: str | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    visibility: ContestVisibility | None = Query(None),
    frequency: ContestFrequency | None = Query(None),
    pagination: StandardResultsSetPagination = Depends(pagination_params),
    lang: str = "en",
    admin: dict = Depends(AdminPermission(allowed_roles=["admin"]))
):
    return await fetch_contests(
        search=search,
        date_from=date_from,
        date_to=date_to,
        visibility=visibility,
        frequency=frequency,
        pagination=pagination,
        lang=lang
    )


@admin_router.get("/deatils/{contest_id}")
async def get_contest_details(
    contest_id: str,
    lang: str = "en",
    admin: dict = Depends(AdminPermission(allowed_roles=["admin"]))
):
    return await get_contest_details_controller(
        contest_id=contest_id,
        lang=lang
    )


@admin_router.patch("/update/{contest_id}")
async def update_contest(
    contest_id: str,
    payload: ContestUpdateSchema = Body(...),
    lang: str = "en",
    admin: dict = Depends(AdminPermission(allowed_roles=["admin"]))
):
    return await update_contest_controller(
        contest_id=contest_id,
        payload=payload,
        admin_id=str(admin["_id"]),
        lang=lang
    )

@admin_router.delete("/delete/{contest_id}")
async def delete_contest(
    contest_id: str,
    lang: str = "en",
    admin: dict = Depends(AdminPermission(allowed_roles=["admin"]))
):
    return await delete_contest_controller(
        contest_id=contest_id,
        admin_id=str(admin["_id"]),
        lang=lang
    )


@admin_router.get("/participants/{contest_id}")
async def get_contest_participants(
    contest_id: str,
    search: str | None = Query(None),
    pagination: StandardResultsSetPagination = Depends(pagination_params),
    lang: str = "en",
    admin: dict = Depends(AdminPermission(allowed_roles=["admin"]))
):
    return await get_contest_participants_controller(
        contest_id=contest_id,
        search=search,
        pagination=pagination,
        lang=lang
    )

