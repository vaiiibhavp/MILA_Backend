from pydantic import BaseModel, Field
from core.utils.core_enums import *
from datetime import datetime
from typing import Optional, List

class ContestCardResponse(BaseModel):
    contest_id: str
    contest_history_id: str
    title: str
    banner_url: Optional[str] = None
    visibility: ContestVisibility
    total_participants: int
    total_votes: int
    prize_distribution: Optional[int] = None
    registration_until: Optional[datetime] = None
    voting_ends: Optional[datetime] = None
    registration_started: Optional[bool] = None
    voting_started: Optional[bool] = None
    
class PrizeItem(BaseModel):
    position: int        # 1, 2, 3
    reward: int          # tokens


class ParticipantPreview(BaseModel):
    user_id: str
    username: str
    profile_photo: Optional[dict]


class LeaderboardEntry(BaseModel):
    user_id: str
    username: str
    profile_photo: Optional[dict]
    votes: int
    rank: int
    badge: Optional[str]  # Top 1 / Top 2 / Top 3


class ContestDetailResponse(BaseModel):
    contest_id: str

    title: str
    tag: Optional[str]
    description: str
    rules_and_conditions: Optional[str]

    banner_url: str

    status: ContestStatus
    visibility: ContestVisibility

    registration_start: datetime
    registration_end: datetime
    voting_start: datetime
    voting_end: datetime

    prize_pool: List[PrizeItem]

    judging_criteria: List[str]

    total_participants: int
    total_votes: int

    participants_preview: List[ParticipantPreview]

    leaderboard: Optional[List[LeaderboardEntry]] = None
    winners: Optional[List[LeaderboardEntry]] = None

    can_participate: bool
    can_vote: bool
    action_button: str  # participate | vote_now | view_leaderboard | view_winners

class VoteRequestSchema(BaseModel):
    participant_user_id: Optional[str] = None
