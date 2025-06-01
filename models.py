from typing import Optional
from pydantic import BaseModel

class User(BaseModel):
    id: int
    username: str
    email: Optional[str] = None
    is_active: bool = True

    class Config:
        orm_mode = True

class Session(BaseModel):
    id: int
    user_id: int
    session_token: str
    expires_at: str

class Link(BaseModel):
    id: int
    short_id: str
    original_url: str
    created_at: str
    click_count: int
    user_id: Optional[int] = None
