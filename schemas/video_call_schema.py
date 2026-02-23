from pydantic import BaseModel

class StartVideoCallRequest(BaseModel):
    caller_id:str
    receiver_user_id: str

class EndVideoCallRequest(BaseModel):
    call_id: str
    total_call_seconds: int

class VideoCallTickRequest(BaseModel):
    call_id: str
    elapsed_seconds: int   # total time since call started (from FE)
