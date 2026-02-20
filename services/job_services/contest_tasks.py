import asyncio
from datetime import datetime, timedelta, timezone
from config.db_config import contest_collection, contest_history_collection, contest_winner_collection
from dateutil.relativedelta import relativedelta
from core.utils.core_enums import ContestFrequency
from config.models.contest_model import auto_declare_winners
from core.utils.leaderboard.leaderboard_helper import LeaderboardRedisHelper

_loop = None
leaderboard_helper = LeaderboardRedisHelper()

def get_loop():
    global _loop

    if _loop is None or _loop.is_closed():
        _loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_loop)

    return _loop

def increment_version(version: str) -> str:
    major, minor, patch = map(int, version.split("."))
    patch += 1
    return f"{major}.{minor}.{patch}"

def resolve_next_cycle_from_end(last_end_date: datetime, frequency: str):

    #use enums
    if frequency == ContestFrequency.weekly:
        return last_end_date + timedelta(days=7)

    elif frequency == ContestFrequency.bi_weekly:
        return last_end_date + timedelta(days=14)

    elif frequency == ContestFrequency.monthly:
        return last_end_date + relativedelta(months=1)

    elif frequency == ContestFrequency.three_months:
        return last_end_date + relativedelta(months=3)

    return None  # non_recurring

async def get_latest_history(contest_id: str):
    return await contest_history_collection.find_one(
        {"contest_id": contest_id},
        sort=[("registration_start", -1)]
    )

async def create_next_history(contest, latest, start_date, new_version):

    if start_date.tzinfo is None:
        start_date = start_date.replace(tzinfo=timezone.utc)

    launch_hour, launch_minute = map(int, contest["launch_time"].split(":"))

    registration_end = (
        start_date + timedelta(days=3)
    ).replace(hour=launch_hour, minute=launch_minute, second=0, microsecond=0)

    voting_start = registration_end

    duration = latest["voting_end"] - latest["voting_start"]

    voting_end = (voting_start + duration).replace(
        hour=launch_hour,
        minute=launch_minute,
        second=0,
        microsecond=0
    )

    # deactivate previous version
    await contest_history_collection.update_one(
        {"_id": latest["_id"]},
        {
            "$set": {
                "status": "inactive",
                "is_active": False,
                "updated_at": datetime.now(timezone.utc)
            }
        }
    )

    # insert new version
    await contest_history_collection.insert_one({
        "contest_id": str(contest["_id"]),
        "contest_version": new_version,

        "status": "active",

        "registration_start": start_date,
        "registration_end": registration_end,
        "voting_start": voting_start,
        "voting_end": voting_end,

        "cycle_key": start_date.strftime("%Y-%m"),
        "cycle_type": contest["frequency"],

        "total_participants": 0,
        "total_votes": 0,

        "is_active": True,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    })

async def process_contest(contest: dict, now: datetime):
    frequency = contest.get("frequency")

    if frequency == "non_recurring":
        return

    latest = await get_latest_history(str(contest["_id"]))

    if not latest:
        return

    last_end = latest["voting_end"]

    # Mongo returns naive datetime → force UTC awareness
    if last_end.tzinfo is None:
        last_end = last_end.replace(tzinfo=timezone.utc)

    next_cycle_date = resolve_next_cycle_from_end(last_end, frequency)

    if not next_cycle_date:
        return

    # not yet time
    if now < next_cycle_date:
        return

    # prevent duplicates
    latest_check = await get_latest_history(str(contest["_id"]))

    if str(latest_check["_id"]) != str(latest["_id"]):
        return 

    new_version = increment_version(latest["contest_version"])

    await create_next_history(contest, latest, next_cycle_date, new_version)


async def generate_contest_cycles_job():
    now = datetime.now(timezone.utc)

    contests = await contest_collection.find({
        "is_active": True,
        "is_deleted": False,
        "frequency": {"$ne": "non_recurring"}
    }).to_list(None)

    for contest in contests:
        await process_contest(contest, now)

async def declare_contest_winners_job():
    """
    Cron job to declare winners for contests
    whose voting period has ended.
    """

    now = datetime.now(timezone.utc)

    # Find contest histories where voting ended
    ended_contests = await contest_history_collection.find({
        "voting_end": {"$lt": now},
        "is_active": True
    }).to_list(None)

    for history in ended_contests:

        contest_id = history["contest_id"]
        contest_history_id = str(history["_id"])

        # Check if winners already declared
        existing_winner = await contest_winner_collection.find_one({
            "contest_id": contest_id,
            "contest_history_id": contest_history_id
        })

        if existing_winner:
            continue

        # Call your existing function
        await auto_declare_winners(contest_id)

        await leaderboard_helper.reset_contest()

    return {
        "status": "success",
        "message": "contest winners declared successfully"
    }