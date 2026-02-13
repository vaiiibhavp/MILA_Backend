from datetime import datetime,timedelta
from bson import ObjectId
import re
from bson.errors import InvalidId
from config.db_config import contest_collection, file_collection , contest_participant_collection,contest_history_collection
from core.utils.helper import serialize_datetime_fields
from api.controller.files_controller import save_file
from api.controller.files_controller import generate_file_url
from config.models.user_models import Files
from config.basic_config import settings
from services.translation import translate_message
from core.utils.helper import calculate_visibility , parse_date_format
from core.utils.core_enums import ContestVisibility

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

        # ---------------- BANNER IMAGE ID FORMAT VALIDATION ----------------
        try:
            banner_object_id = ObjectId(payload.banner_image_id)
        except (InvalidId, TypeError):
            return {
                "error": True,
                "message": translate_message("INVALID_BANNER_IMAGE_ID", lang),
                "status_code": 400
            }

        # ---------------- BANNER IMAGE EXISTENCE VALIDATION ----------------
        banner_file = await file_collection.find_one({
            "_id": banner_object_id
        })

        if not banner_file:
            return {
                "error": True,
                "message": translate_message("BANNER_IMAGE_NOT_FOUND", lang),
                "status_code": 400
            }


        # ---------------- TITLE MIN CHARACTER VALIDATION ----------------
        title_length = len(payload.title.strip())

        if title_length < 5:
            return {
                "error": True,
                "message": translate_message("CONTEST_TITLE_MIN_CHARS", lang),
                "status_code": 400
            }


        # ---------------- TITLE READABILITY ----------------
        if not re.search(r"[a-zA-Z]", payload.title):
            return {
                "error": True,
                "message": translate_message("INVALID_CONTEST_TITLE", lang),
                "status_code": 400
            }

        # ---------------- BADGE VALIDATION ----------------
        if not payload.badge or not payload.badge.strip():
            return {
                "error": True,
                "message": translate_message("EMPTY_BADGE_NOT_ALLOWED", lang),
                "status_code": 400
            }

        badge = payload.badge.strip()

        if len(badge) < 3:
            return {
                "error": True,
                "message": translate_message("BADGE_MIN_CHARS", lang),
                "status_code": 400
            }

        if not re.search(r"[a-zA-Z]", badge):
            return {
                "error": True,
                "message": translate_message("INVALID_BADGE", lang),
                "status_code": 400
            }

        # ---------------- DESCRIPTION VALIDATION ----------------
        if not payload.description or not payload.description.strip():
            return {
                "error": True,
                "message": translate_message("EMPTY_CONTEST_DESCRIPTION", lang),
                "status_code": 400
            }

        # ---------------- RULES VALIDATION ----------------
        if not payload.rules or any(not r or not r.strip() for r in payload.rules):
            return {
                "error": True,
                "message": translate_message("EMPTY_RULES_NOT_ALLOWED", lang),
                "status_code": 400
            }

        # ---------------- LAUNCH TIME VALIDATION ----------------
        try:
            hour, minute = map(int, payload.launch_time.split(":"))
        except Exception:
            return {
                "error": True,
                "message": translate_message("INVALID_LAUNCH_TIME_FORMAT", lang),
                "status_code": 400
            }

        if not (0 <= hour <= 23):
            return {
                "error": True,
                "message": translate_message("INVALID_LAUNCH_TIME_HOUR", lang),
                "status_code": 400
            }

        if not (0 <= minute <= 59):
            return {
                "error": True,
                "message": translate_message("INVALID_LAUNCH_TIME_MINUTE", lang),
                "status_code": 400
            }

        today = datetime.utcnow()

        start_date_dt = parse_date_format(payload.start_date)
        end_date_dt = parse_date_format(payload.end_date)

        # ---------- FORMAT VALIDATION ----------
        if not start_date_dt:
            return {"error": True, "message": translate_message("INVALID_START_DATE_FORMAT", lang), "status_code": 400}

        if not end_date_dt:
            return {"error": True, "message": translate_message("INVALID_END_DATE_FORMAT", lang), "status_code": 400}

        # ---------- PAST DATE VALIDATION ----------
        if start_date_dt < today:
            return {"error": True, "message": translate_message("FUTURE_START_DATE_REQUIRED", lang), "status_code": 400}

        if end_date_dt < today:
            return {"error": True, "message": translate_message("FUTURE_END_DATE_REQUIRED", lang), "status_code": 400}


        # Contest must have a valid duration
        if start_date_dt >= end_date_dt:
            return {
                "error": True,
                "message": translate_message("INVALID_CONTEST_DATES", lang),
                "status_code": 400
            }

        # ---------------- MINIMUM 4 DAYS VALIDATION ----------------
        contest_duration_days = (end_date_dt - start_date_dt).days

        if contest_duration_days < 4:
            return {
                "error": True,
                "message": translate_message("CONTEST_MINIMUM_4_DAYS_REQUIRED", lang),
                "status_code": 400
            }

        if payload.judging_criteria is not None:
            if not payload.judging_criteria or any(not c.strip() for c in payload.judging_criteria):
                return {
                    "error": True,
                    "message": translate_message("INVALID_JUDGING_CRITERIA", lang),
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

        # ---------------- DATE RANGE OVERLAP ----------------
        overlapping_contest = await contest_collection.find_one({
            "is_deleted": {"$ne": True},
            "$expr": {
                "$and": [
                    {"$lte": [payload.start_date, "$end_date"]},
                    {"$gte": [payload.end_date, "$start_date"]}
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


        min_participant = payload.min_participant
        max_participant = payload.max_participant

        if min_participant <= 0:
            return {
                "error": True,
                "message": translate_message("INVALID_MIN_PARTICIPANT", lang),
                "status_code": 400
            }

        if max_participant <= 0:
            return {
                "error": True,
                "message": translate_message("INVALID_MAX_PARTICIPANT", lang),
                "status_code": 400
            }

        if min_participant > max_participant:
            return {
                "error": True,
                "message": translate_message("MIN_PARTICIPANT_GREATER_THAN_MAX", lang),
                "status_code": 400
            }

        # ---------------- DERIVED CONTEST TIMELINES ----------------
        launch_hour, launch_minute = map(int, payload.launch_time.split(":"))

        # Registration ends at (start_date + 3 days) AT launch time
        registration_until_dt = (
            start_date_dt + timedelta(days=3)
        ).replace(
            hour=launch_hour,
            minute=launch_minute,
            second=0,
            microsecond=0
        )

        # Voting starts exactly when registration ends
        voting_date_dt = registration_until_dt

        # Voting ends on contest end date at launch time
        voting_until_dt = end_date_dt.replace(
            hour=launch_hour,
            minute=launch_minute,
            second=0,
            microsecond=0
        )
    
        # ---------------- CREATE CONTEST ----------------
        now = datetime.utcnow()

        contest_doc = {
            "title": payload.title.strip(),
            "badge": badge,
            "banner_image_id": payload.banner_image_id.strip(),
            "description": payload.description.strip(),
            "rules": [r.strip() for r in payload.rules],

            "start_date": payload.start_date,
            "end_date": payload.end_date,
            "launch_time": payload.launch_time.strip(),

            "registration_until": registration_until_dt,
            "voting_start": voting_date_dt,
            "voting_end": voting_until_dt,

            "frequency": payload.frequency.value if payload.frequency else None,

            "prize_distribution": {
                "first_place": prizes.first_place,
                "second_place": prizes.second_place,
                "third_place": prizes.third_place
            },

            "max_votes_per_user":payload.max_votes_per_user,
            "cost_per_vote": payload.cost_per_vote,
            "min_participant": payload.min_participant,
            "max_participant": payload.max_participant,

            "photos_per_participant": payload.photos_per_participant,

            "created_by": admin_id,

            "total_participants": 0,
            "total_votes": 0,

            "start_date": start_date_dt,
            "end_date": end_date_dt,
            "judging_criteria": payload.judging_criteria or [],

            "is_active": True,
            "is_deleted": False,

            "created_at": now,
            "updated_at": now
        }

        result = await contest_collection.insert_one(contest_doc)

        # ---------------- CREATE CONTEST HISTORY ----------------
        contest_history_doc = {
            "contest_id": str(result.inserted_id),

            "status": "active",  # <-- plain string, no enum
            "contest_version": "1.0.0",
            "registration_start": contest_doc["start_date"],
            "registration_end": contest_doc["registration_until"],

            "voting_start": contest_doc["voting_start"],
            "voting_end": contest_doc["voting_end"],

            "cycle_key": contest_doc["start_date"].strftime("%Y-%m"),
            "cycle_type": contest_doc["frequency"],

            "total_participants": 0,
            "total_votes": 0,

            "is_active": True,

            "created_at": now,
            "updated_at": now
        }

        await contest_history_collection.insert_one(contest_history_doc)

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
            # ---------------- IMAGE REQUIRED VALIDATION ----------------
            if not image or not getattr(image, "filename", None):
                return {
                    "error": True,
                    "message": translate_message("IMAGE_FIELD_REQUIRED", lang),
                    "status_code": 400
                }

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
                "message": translate_message("FILE_UPLOADED_SUCCESS", lang).format(
                    file_type=translate_message("CONTEST_BANNER", lang)
                ),
                "data": serialize_datetime_fields({
                    "file_id": str(inserted.inserted_id),
                    "storage_key": storage_key,
                    "url": public_url
                })
            }

        except Exception:
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

        # ---------------- PROJECTION ----------------
        pipeline.append({
            "$project": {
                "_id": 0,
                "contest_id": {"$toString": "$_id"},
                "title": 1,
                "badge":1,
                "start_date": 1,
                "end_date": 1,
                "launch_time": 1,
                "frequency": 1,
                "total_participants": 1,
                "total_votes": 1,
                "min_participant":1,
                "registration_until":1,
                "voting_start":1,
                "voting_end":1
            }
        })

        contests = await contest_collection.aggregate(pipeline).to_list(None)

        # ---------------- ADD DYNAMIC VISIBILITY ----------------
        for contest in contests:
            # existing visibility logic
            contest["visibility"] = calculate_visibility(
                contest["start_date"],
                contest["end_date"]
            )


        # ---------------- TOTAL COUNT ----------------
        total_count = len(contests)

        # ---------------- PAGINATION (IN-MEMORY, SAFE) ----------------
        page = pagination.page if pagination and pagination.page else 1
        page_size = (
            pagination.page_size
            if pagination and pagination.page_size
            else pagination.limit
            if pagination and pagination.limit
            else total_count
        )

        start = (page - 1) * page_size
        end = start + page_size
        contests = contests[start:end]

        # ---------------- SERIALIZE ----------------
        contests = [serialize_datetime_fields(c) for c in contests]

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
            "badge":contest.get("badge"),
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
            "registration_until":contest.get("registration_until"),
            "voting_start":contest.get("voting_start"),
            "voting_end":contest.get("voting_end"),

            # Rewards
            "prize_distribution": contest.get("prize_distribution"),

            # Settings
            "max_participants": contest.get("max_participant"),
            "cost_per_vote": contest.get("cost_per_vote"),
            "max_votes_per_user":contest.get("max_votes_per_user"),
            "min_participant":contest.get("min_participant")
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
        if payload.title is not None:
            title = payload.title.strip()

            if len(title) < 5:
                return {
                    "error": True,
                    "message": translate_message("CONTEST_TITLE_MIN_CHARS", lang),
                    "status_code": 400
                }

            if not re.search(r"[a-zA-Z]", title):
                return {
                    "error": True,
                    "message": translate_message("INVALID_CONTEST_TITLE", lang),
                    "status_code": 400
                }

            existing = await contest_collection.find_one({
                "_id": {"$ne": ObjectId(contest_id)},
                "title": title,
                "is_deleted": {"$ne": True}
            })

            if existing:
                return {
                    "error": True,
                    "message": translate_message("CONTEST_TITLE_ALREADY_EXISTS", lang),
                    "status_code": 400
                }

            update_data["title"] = title

        # ---------------- BANNER IMAGE ID VALIDATION ----------------
        if payload.banner_image_id is not None:
            try:
                banner_object_id = ObjectId(payload.banner_image_id)
            except (InvalidId, TypeError):
                return {
                    "error": True,
                    "message": translate_message("INVALID_BANNER_IMAGE_ID", lang),
                    "status_code": 400
                }

            banner_file = await file_collection.find_one({
                "_id": banner_object_id
            })

            if not banner_file:
                return {
                    "error": True,
                    "message": translate_message("BANNER_IMAGE_NOT_FOUND", lang),
                    "status_code": 400
                }

            update_data["banner_image_id"] = payload.banner_image_id.strip()

        # ---------------- BADGE VALIDATION ----------------
        if not payload.badge or not payload.badge.strip():
            return {
                "error": True,
                "message": translate_message("EMPTY_BADGE_NOT_ALLOWED", lang),
                "status_code": 400
            }

        badge = payload.badge.strip()

        if len(badge) < 3:
            return {
                "error": True,
                "message": translate_message("BADGE_MIN_CHARS", lang),
                "status_code": 400
            }

        if not re.search(r"[a-zA-Z]", badge):
            return {
                "error": True,
                "message": translate_message("INVALID_BADGE", lang),
                "status_code": 400
            }

        # ---------------- DESCRIPTION VALIDATION ----------------
        if not payload.description or not payload.description.strip():
            return {
                "error": True,
                "message": translate_message("EMPTY_CONTEST_DESCRIPTION", lang),
                "status_code": 400
            }
        
        # ---------------- BASIC STRING & NUMBER FIELDS ----------------
        basic_fields = [
            "description",
            "launch_time",
            "cost_per_vote",
            "max_votes_per_user",
            "min_participant",
            "max_participant",
            "photos_per_participant"
        ]

        for field in basic_fields:
            value = getattr(payload, field)
            if value is not None:
                update_data[field] = value

        # ---------------- RULES VALIDATION ----------------
        if payload.rules is not None:
            if not payload.rules or any(not r or not r.strip() for r in payload.rules):
                return {
                    "error": True,
                    "message": translate_message("EMPTY_RULES_NOT_ALLOWED", lang),
                    "status_code": 400
                }
            update_data["rules"] = [r.strip() for r in payload.rules]

        # ---------------- LAUNCH TIME VALIDATION ----------------
        if payload.launch_time is not None:
            try:
                hour, minute = map(int, payload.launch_time.split(":"))
            except Exception:
                return {
                    "error": True,
                    "message": translate_message("INVALID_LAUNCH_TIME_FORMAT", lang),
                    "status_code": 400
                }

            if not (0 <= hour <= 23):
                return {
                    "error": True,
                    "message": translate_message("INVALID_LAUNCH_TIME_HOUR", lang),
                    "status_code": 400
                }

            if not (0 <= minute <= 59):
                return {
                    "error": True,
                    "message": translate_message("INVALID_LAUNCH_TIME_MINUTE", lang),
                    "status_code": 400
                }

            update_data["launch_time"] = payload.launch_time.strip()

        # ---------------- FINAL LAUNCH TIME ----------------
        final_launch_time = (
            payload.launch_time.strip()
            if payload.launch_time is not None
            else contest["launch_time"]
        )

        launch_hour, launch_minute = map(int, final_launch_time.split(":"))

        # ---------------- FREQUENCY ----------------
        if payload.frequency is not None:
            update_data["frequency"] = payload.frequency.value

        # ---------------- DATE VALIDATION ----------------
        today = datetime.utcnow()

        # Existing dates from DB (already datetime)
        existing_start_date = contest["start_date"]
        existing_end_date = contest["end_date"]

        # Parse incoming values if present
        new_start_date = parse_date_format(payload.start_date) if payload.start_date else None
        new_end_date = parse_date_format(payload.end_date) if payload.end_date else None

        # If user provided invalid format
        if payload.start_date and not new_start_date:
            return {
                "error": True,
                "message": translate_message("INVALID_START_DATE_FORMAT", lang),
                "status_code": 400
            }

        if payload.end_date and not new_end_date:
            return {
                "error": True,
                "message": translate_message("INVALID_END_DATE_FORMAT", lang),
                "status_code": 400
            }

        # Final dates to compare
        final_start_date = new_start_date or existing_start_date
        final_end_date = new_end_date or existing_end_date

        # Past-date validation
        if final_start_date < today:
            return {
                "error": True,
                "message": translate_message("FEATURE_START_DATE_REQUIRED", lang),
                "status_code": 400
            }

        if final_end_date < today:
            return {
                "error": True,
                "message": translate_message("FEATURE_END_DATE_REQUIRED", lang),
                "status_code": 400
            }

        if payload.judging_criteria is not None:
            if not payload.judging_criteria or any(not c.strip() for c in payload.judging_criteria):
                return {
                    "error": True,
                    "message": translate_message("INVALID_JUDGING_CRITERIA", lang),
                    "status_code": 400
                }
            update_data["judging_criteria"] = payload.judging_criteria

        # Ordering validation
        if final_start_date >= final_end_date:
            return {
                "error": True,
                "message": translate_message("INVALID_CONTEST_DATES", lang),
                "status_code": 400
            }
    
        if new_start_date:
            update_data["start_date"] = new_start_date

        if new_end_date:
            update_data["end_date"] = new_end_date

        # ---------------- RECALCULATE DERIVED DATES ----------------
        if payload.start_date or payload.end_date or payload.launch_time:
            registration_until_dt = (
                final_start_date + timedelta(days=3)
            ).replace(
                hour=launch_hour,
                minute=launch_minute,
                second=0,
                microsecond=0
            )

            voting_date_dt = registration_until_dt

            voting_until_dt = final_end_date.replace(
                hour=launch_hour,
                minute=launch_minute,
                second=0,
                microsecond=0
            )

            if registration_until_dt >= voting_until_dt:
                return {
                    "error": True,
                    "message": translate_message(
                        "REGISTRATION_ENDS_AFTER_CONTEST_END",
                        lang
                    ),
                    "status_code": 400
                }

            update_data.update({
                "registration_until": registration_until_dt,
                "voting_start": voting_date_dt,
                "voting_until": voting_until_dt
            })

        existing_min = contest.get("min_participant")
        existing_max = contest.get("max_participant")

        new_min = payload.min_participant if payload.min_participant is not None else existing_min
        new_max = payload.max_participant if payload.max_participant is not None else existing_max

        if new_min is not None and new_min <= 0:
            return {
                "error": True,
                "message": translate_message("INVALID_MIN_PARTICIPANT", lang),
                "status_code": 400
            }

        if new_max is not None and new_max <= 0:
            return {
                "error": True,
                "message": translate_message("INVALID_MAX_PARTICIPANT", lang),
                "status_code": 400
            }

        if new_min is not None and new_max is not None and new_min > new_max:
            return {
                "error": True,
                "message": translate_message("MIN_PARTICIPANT_GREATER_THAN_MAX", lang),
                "status_code": 400
            }

        if payload.min_participant is not None:
            update_data["min_participant"] = payload.min_participant

        if payload.max_participant is not None:
            update_data["max_participant"] = payload.max_participant

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
            }
        }

    @staticmethod
    async def delete_contest(
        contest_id: str,
        admin_id: str,
        lang: str = "en"
    ):
        # ---------------- VALIDATE CONTEST ID ----------------
        try:
            contest_object_id = ObjectId(contest_id)
        except (InvalidId, TypeError):
            return {
                "error": True,
                "message": translate_message("INVALID_CONTEST_ID", lang),
                "status_code": 400
            }

        # ---------------- CHECK CONTEST EXISTS ----------------
        contest = await contest_collection.find_one({
            "_id": contest_object_id
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
        if now >= contest.get("start_date"):
            return {
                "error": True,
                "message": translate_message("CONTEST_ALREADY_STARTED_CANNOT_DELETE", lang),
                "status_code": 400
            }

        # ---------------- SOFT DELETE ----------------
        await contest_collection.update_one(
            {"_id": contest_object_id},
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
        pipeline.append({"$match": {"contest_id": contest_id}})

        # ---------------- USER LOOKUP ----------------
        pipeline.extend([
            {"$addFields": {"userObjId": {"$toObjectId": "$user_id"}}},
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

        # ---------------- SEARCH ----------------
        if search:
            pipeline.append({
                "$match": {
                    "user.username": {"$regex": search, "$options": "i"}
                }
            })

        # ==================================================
        # COUNT PIPELINE (BEFORE PAGINATION)
        # ==================================================
        count_pipeline = pipeline.copy()
        count_pipeline.append({"$count": "total"})

        count_result = await contest_participant_collection.aggregate(
            count_pipeline
        ).to_list(1)

        total_records = count_result[0]["total"] if count_result else 0

        # ---------------- SORT ----------------
        pipeline.append({"$sort": {"total_votes": -1}})

        # ---------------- PAGINATION ----------------
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

        return {
            "data": participants,
            "total": total_records
        }
