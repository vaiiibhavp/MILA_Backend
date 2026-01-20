from datetime import datetime
from bson import ObjectId
from config.db_config import contest_collection, file_collection , contest_participant_collection
from core.utils.helper import serialize_datetime_fields
from api.controller.files_controller import save_file
from api.controller.files_controller import generate_file_url
from config.models.user_models import Files
from config.basic_config import settings
from services.translation import translate_message
from core.utils.helper import calculate_visibility



class ContestModel:

    # ============================================================
    # CREATE CONTEST
    # ============================================================
    @staticmethod
    async def create_contest(
        payload,
        admin_id: str,
        lang: str = "en"
    ):
        # ---------------- EMPTY STRING PROTECTION ----------------
        text_fields = {
            "title": payload.title,
            "banner_image_id": payload.banner_image_id,
            "description": payload.description,
            "launch_time": payload.launch_time,
        }

        for field, value in text_fields.items():
            if not value or not value.strip():
                return {
                    "error": True,
                    "message": translate_message("EMPTY_FIELDS_NOT_ALLOWED", lang),
                    "status_code": 400
                }

        if not payload.rules or any(not r or not r.strip() for r in payload.rules):
            return {
                "error": True,
                "message": translate_message("EMPTY_RULES_NOT_ALLOWED", lang),
                "status_code": 400
            }

        # ---------------- DATE VALIDATION ----------------
        if payload.start_date >= payload.end_date:
            return {
                "error": True,
                "message": translate_message("INVALID_CONTEST_DATES", lang),
                "status_code": 400
            }

        # ---------------- DUPLICATE TITLE CHECK ----------------
        existing = await contest_collection.find_one({
            "title": payload.title.strip(),
            "is_deleted": {"$ne": True}
        })

        if existing:
            return {
                "error": True,
                "message": translate_message("CONTEST_TITLE_ALREADY_EXISTS", lang),
                "status_code": 400
            }

        # ---------------- BLOCK ONLY IF DATE RANGE OVERLAPS ----------------
        new_start = payload.start_date
        new_end = payload.end_date

        overlapping_contest = await contest_collection.find_one({
            "is_deleted": {"$ne": True},
            "$expr": {
                "$and": [
                    {"$lte": [new_start, "$end_date"]},
                    {"$gte": [new_end, "$start_date"]}
                ]
            }
        })

        if overlapping_contest:
            return {
                "error": True,
                "message": translate_message("CONTEST_DATE_RANGE_OVERLAPS", lang),
                "status_code": 400
            }

        # ---------------- PRIZE VALIDATION ----------------
        prizes = payload.prize_distribution

        if not (prizes.first_place > prizes.second_place > prizes.third_place):
            return {
                "error": True,
                "message": translate_message("INVALID_PRIZE_DISTRIBUTION", lang),
                "status_code": 400
            }

        # ---------------- CREATE CONTEST ----------------
        now = datetime.utcnow()

        contest_doc = {
            "title": payload.title.strip(),
            "banner_image_id": payload.banner_image_id.strip(),
            "description": payload.description.strip(),
            "rules": [r.strip() for r in payload.rules],

            "start_date": payload.start_date,
            "end_date": payload.end_date,
            "launch_time": payload.launch_time.strip(),

            "frequency": payload.frequency.value,

            "prize_distribution": {
                "first_place": prizes.first_place,
                "second_place": prizes.second_place,
                "third_place": prizes.third_place
            },

            "cost_per_vote": payload.cost_per_vote,
            "max_votes_per_user": payload.max_votes_per_user,

            "participant_limit": payload.participant_limit,
            "photos_per_participant": payload.photos_per_participant,

            "created_by": admin_id,

            "total_participants": 0,
            "total_votes": 0,

            "is_active": True,
            "is_deleted": False,

            "created_at": now,
            "updated_at": now
        }

        result = await contest_collection.insert_one(contest_doc)

        return {
            "error": False,
            "data": serialize_datetime_fields({
                "contest_id": str(result.inserted_id),
                "title": contest_doc["title"],
                "start_date": contest_doc["start_date"],
                "end_date": contest_doc["end_date"]
            })
        }
    # ============================================================
    # UPLOAD CONTEST BANNER
    # ============================================================
    @staticmethod
    async def upload_contest_banner(
        image,
        admin_id: str,
        lang: str = "en"
    ):
        try:
            # ---------------- FILE TYPE VALIDATION ----------------
            allowed_extensions = {"jpg", "jpeg", "png", "webp"}
            ext = image.filename.split(".")[-1].lower()

            if ext not in allowed_extensions:
                return {
                    "error": True,
                    "message": translate_message("INVALID_IMAGE_FORMAT", lang),
                    "status_code": 400
                }

            # ---------------- FILE SIZE VALIDATION ----------------
            content = await image.read()
            image_size_mb = len(content) / (1024 * 1024)

            if image_size_mb > settings.MAX_IMAGE_SIZE_BYTES:
                return {
                    "error": True,
                    "message": translate_message("IMAGE_SIZE_EXCEEDED", lang),
                    "status_code": 400
                }

            # Reset file pointer after read
            image.file.seek(0)

            # ---------------- SAVE FILE (LOCAL / S3) ----------------
            public_url, storage_key, backend = await save_file(
                file_obj=image,
                file_name=image.filename,
                user_id=admin_id,
                file_type="contest_banner"
            )

            # ---------------- STORE FILE META IN DB ----------------
            file_doc = Files(
                storage_key=storage_key,
                storage_backend=backend,
                file_type="contest_banner",
                uploaded_by=admin_id,
                uploaded_at=datetime.utcnow(),
            )

            inserted = await file_collection.insert_one(
                file_doc.model_dump(by_alias=True)
            )

            return {
                "error": False,
                "data": serialize_datetime_fields({
                    "file_id": str(inserted.inserted_id),
                    "storage_key": storage_key,
                    "url": public_url
                })
            }

        except Exception as e:
            return {
                "error": True,
                "message": translate_message("ERROR_WHILE_UPLOADING_FILE", lang),
                "status_code": 500
            }

    @staticmethod
    async def fetch_contests(
        search: str | None,
        date_from,
        date_to,
        visibility,
        frequency,
        pagination,
        lang: str = "en"
    ):
        pipeline = []

        # ---------------- BASE MATCH ----------------
        match_stage = {"is_deleted": {"$ne": True}}

        # ---------------- SEARCH ----------------
        if search:
            match_stage["title"] = {"$regex": search, "$options": "i"}

        # ---------------- DATE FILTER ----------------
        if date_from or date_to:
            match_stage["start_date"] = {}
            if date_from:
                match_stage["start_date"]["$gte"] = date_from
            if date_to:
                match_stage["start_date"]["$lte"] = date_to

        # ---------------- FREQUENCY FILTER ----------------
        if frequency:
            match_stage["frequency"] = frequency.value

        pipeline.append({"$match": match_stage})

        # ---------------- SORT BY LATEST ----------------
        pipeline.append({"$sort": {"created_at": -1}})

        # ---------------- PAGINATION (SAFE FIX) ----------------
        if pagination and pagination.skip is not None and pagination.limit is not None:
            pipeline.extend([
                {"$skip": int(pagination.skip)},
                {"$limit": int(pagination.limit)}
            ])

        # ---------------- PROJECTION (UI TABLE FIELDS) ----------------
        pipeline.append({
            "$project": {
                "_id": 0,
                "contest_id": {"$toString": "$_id"},
                "title": 1,
                "start_date": 1,
                "end_date": 1,
                "launch_time": 1,
                "frequency": 1,
                "total_participants": 1,
                "total_votes": 1
            }
        })

        contests = await contest_collection.aggregate(pipeline).to_list(None)

        # ---------------- ADD DYNAMIC VISIBILITY ----------------
        for contest in contests:
            contest["visibility"] = calculate_visibility(
                contest["start_date"],
                contest["end_date"]
            )

        # ---------------- STATUS FILTER (POST COMPUTE) ----------------
        if visibility:
            contests = [
                c for c in contests
                if c["visibility"] == visibility.value
            ]

        # ---------------- SERIALIZE ----------------
        contests = [serialize_datetime_fields(contest)for contest in contests]

        # ---------------- TOTAL COUNT (ACCURATE FIX) ----------------
        count_match = match_stage.copy()

        raw_contests = await contest_collection.find(count_match).to_list(None)

        for contest in raw_contests:
            contest["visibility"] = calculate_visibility(
                contest["start_date"],
                contest["end_date"]
            )

        if visibility:
            raw_contests = [
                c for c in raw_contests
                if c["visibility"] == visibility.value
            ]

        total_count = len(raw_contests)

        return {
            "data": contests,
            "total": total_count
        }
    
    @staticmethod
    async def get_contest_details(
        contest_id: str,
        lang: str = "en"
    ):
        # ---------------- CONTEST ----------------
        contest = await contest_collection.find_one({
            "_id": ObjectId(contest_id),
            "is_deleted": {"$ne": True}
        })

        if not contest:
            return {
                "error": True,
                "message": translate_message("CONTEST_NOT_FOUND", lang),
                "status_code": 404
            }

        # ---------------- BANNER IMAGE ----------------
        banner = None
        if contest.get("banner_image_id"):
            file_doc = await file_collection.find_one({
                "_id": ObjectId(contest["banner_image_id"])
            })

            if file_doc:
                banner_url = await generate_file_url(
                    file_doc["storage_key"],
                    file_doc.get("storage_backend")
                )

                banner = {
                    "id": str(file_doc["_id"]),
                    "url": banner_url
                }

        # ---------------- DYNAMIC VISIBILITY ----------------
        visibility = calculate_visibility(
            contest["start_date"],
            contest["end_date"]
        )

        # ---------------- RESPONSE STRUCTURE ----------------
        result = {
            "contest_id": str(contest["_id"]),
            "title": contest.get("title"),
            "visibility": visibility,

            "banner_image": banner,

            # Stats Cards
            "total_participants": contest.get("total_participants", 0),
            "total_votes": contest.get("total_votes", 0),
            "cost_per_vote": contest.get("cost_per_vote"),
            "photos_per_participant": contest.get("photos_per_participant"),

            # Description
            "description": contest.get("description"),
            "rules": contest.get("rules", []),

            # Contest Details
            "start_date": contest.get("start_date"),
            "end_date": contest.get("end_date"),
            "launch_time": contest.get("launch_time"),
            "frequency": contest.get("frequency"),

            # Rewards
            "prize_distribution": contest.get("prize_distribution"),

            # Settings
            "participant_limit": contest.get("participant_limit"),
            "max_votes_per_user": contest.get("max_votes_per_user")
        }

        return {
            "error": False,
            "data": serialize_datetime_fields(result)
        }


    @staticmethod
    async def update_contest(
        contest_id: str,
        payload,
        admin_id: str,
        lang: str = "en"
    ):
        # ---------------- CHECK CONTEST EXISTS ----------------
        contest = await contest_collection.find_one({
            "_id": ObjectId(contest_id),
            "is_deleted": {"$ne": True}
        })

        if not contest:
            return {
                "error": True,
                "message": translate_message("CONTEST_NOT_FOUND", lang),
                "status_code": 404
            }

        update_data = {}

        # ---------------- TITLE DUPLICATE CHECK ----------------
        if payload.title:
            existing = await contest_collection.find_one({
                "_id": {"$ne": ObjectId(contest_id)},
                "title": payload.title,
                "is_deleted": {"$ne": True}
            })

            if existing:
                return {
                    "error": True,
                    "message": translate_message("CONTEST_TITLE_ALREADY_EXISTS", lang),
                    "status_code": 400
                }

            update_data["title"] = payload.title

        # ---------------- BASIC FIELDS ----------------
        fields = [
            "banner_image_id",
            "description",
            "rules",
            "launch_time",
            "cost_per_vote",
            "max_votes_per_user",
            "participant_limit",
            "photos_per_participant"
        ]

        for field in fields:
            value = getattr(payload, field)
            if value is not None:
                update_data[field] = value

        # ---------------- FREQUENCY (ENUM SAFE) ----------------
        if payload.frequency:
            update_data["frequency"] = payload.frequency.value

        # ---------------- DATE VALIDATION ----------------
        start_date = payload.start_date or contest["start_date"]
        end_date = payload.end_date or contest["end_date"]

        if start_date >= end_date:
            return {
                "error": True,
                "message": translate_message("INVALID_CONTEST_DATES", lang),
                "status_code": 400
            }

        if payload.start_date:
            update_data["start_date"] = payload.start_date
        if payload.end_date:
            update_data["end_date"] = payload.end_date

        # ---------------- PRIZE VALIDATION ----------------
        if payload.prize_distribution:
            first = payload.prize_distribution.first_place or contest["prize_distribution"]["first_place"]
            second = payload.prize_distribution.second_place or contest["prize_distribution"]["second_place"]
            third = payload.prize_distribution.third_place or contest["prize_distribution"]["third_place"]

            if not (first > second > third):
                return {
                    "error": True,
                    "message": translate_message("INVALID_PRIZE_DISTRIBUTION", lang),
                    "status_code": 400
                }

            update_data["prize_distribution"] = {
                "first_place": first,
                "second_place": second,
                "third_place": third
            }

        # ---------------- NO FIELDS TO UPDATE ----------------
        if not update_data:
            return {
                "error": True,
                "message": translate_message("NO_FIELDS_TO_UPDATE", lang),
                "status_code": 400
            }

        update_data["updated_at"] = datetime.utcnow()

        # ---------------- UPDATE ----------------
        await contest_collection.update_one(
            {"_id": ObjectId(contest_id)},
            {"$set": update_data}
        )

        return {
            "error": False,
            "data": {
                "contest_id": contest_id,
                "updated_fields": list(update_data.keys())
            }
        }

    @staticmethod
    async def delete_contest(
        contest_id: str,
        admin_id: str,
        lang: str = "en"
    ):
        # ---------------- CHECK CONTEST EXISTS ----------------
        contest = await contest_collection.find_one({
            "_id": ObjectId(contest_id)
        })

        if not contest:
            return {
                "error": True,
                "message": translate_message("CONTEST_NOT_FOUND", lang),
                "status_code": 404
            }

        # ---------------- CHECK ALREADY DELETED ----------------
        if contest.get("is_deleted") is True:
            return {
                "error": True,
                "message": translate_message("CONTEST_ALREADY_DELETED", lang),
                "status_code": 400
            }

        now = datetime.utcnow()

        # ---------------- BLOCK DELETE IF CONTEST STARTED ----------------
        if now >= contest["start_date"]:
            return {
                "error": True,
                "message": translate_message("CONTEST_ALREADY_STARTED_CANNOT_DELETE", lang),
                "status_code": 400
            }

        # ---------------- SOFT DELETE ----------------
        await contest_collection.update_one(
            {"_id": ObjectId(contest_id)},
            {
                "$set": {
                    "is_deleted": True,
                    "updated_at": now,
                    "deleted_by": admin_id
                }
            }
        )

        return {
            "error": False,
            "data": {
                "contest_id": contest_id,
                "deleted_by": admin_id
            }
        }
    
    @staticmethod
    async def get_contest_participants(
        contest_id: str,
        search: str | None,
        pagination,
        lang: str = "en"
    ):
        pipeline = []

        # ---------------- MATCH CONTEST ----------------
        pipeline.append({
            "$match": {
                "contest_id": contest_id
            }
        })

        # ---------------- USER LOOKUP ----------------
        pipeline.extend([
            {
                "$addFields": {
                    "userObjId": {"$toObjectId": "$user_id"}
                }
            },
            {
                "$lookup": {
                    "from": "users",
                    "localField": "userObjId",
                    "foreignField": "_id",
                    "as": "user"
                }
            },
            {"$unwind": "$user"}
        ])

        # ---------------- SEARCH BY USERNAME ----------------
        if search:
            pipeline.append({
                "$match": {
                    "user.username": {"$regex": search, "$options": "i"}
                }
            })

        # ---------------- SORT BY VOTES DESC ----------------
        pipeline.append({"$sort": {"total_votes": -1}})

        # ---------------- PAGINATION (DOUBLE SAFE) ----------------
        if pagination and pagination.skip is not None and pagination.limit is not None:
            pipeline.extend([
                {"$skip": int(pagination.skip)},
                {"$limit": int(pagination.limit)}
            ])

        # ---------------- FINAL PROJECTION ----------------
        pipeline.append({
            "$project": {
                "_id": 0,
                "participant_id": {"$toString": "$_id"},
                "user_id": "$user_id",
                "username": "$user.username",
                "email": "$user.email",
                "total_votes": 1,
                "joined_date": "$created_at",
                "uploaded_file_ids": 1
            }
        })

        participants = await contest_participant_collection.aggregate(pipeline).to_list(None)

        # ---------------- RESOLVE IMAGE URLS ----------------
        for p in participants:
            file_ids = p.get("uploaded_file_ids", [])

            files = await file_collection.find(
                {"_id": {"$in": [ObjectId(fid) for fid in file_ids]}}
            ).to_list(None)

            photos = []
            for f in files:
                url = await generate_file_url(
                    f["storage_key"],
                    f.get("storage_backend")
                )
                photos.append({
                    "id": str(f["_id"]),
                    "url": url
                })

            p["photos"] = photos
            p.pop("uploaded_file_ids", None)

        participants = serialize_datetime_fields(participants)

        # ---------------- TOTAL COUNT (ACCURATE) ----------------
        count_pipeline = [
            {"$match": {"contest_id": contest_id}},
            {
                "$addFields": {
                    "userObjId": {"$toObjectId": "$user_id"}
                }
            },
            {
                "$lookup": {
                    "from": "users",
                    "localField": "userObjId",
                    "foreignField": "_id",
                    "as": "user"
                }
            },
            {"$unwind": "$user"}
        ]

        if search:
            count_pipeline.append({
                "$match": {
                    "user.username": {"$regex": search, "$options": "i"}
                }
            })

        total_records = len(
            await contest_participant_collection.aggregate(count_pipeline).to_list(None)
        )

        return {
            "data": participants,
            "total": total_records
        }
