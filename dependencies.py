from fastapi import Request, HTTPException, Depends
from typing import Optional
from models import User
from database import db_connection
from dependencies import get_current_user

def get_current_user(request: Request) -> Optional[User]:
    session_token = request.cookies.get("session_token")
    if not session_token:
        return None
    
    with db_connection() as conn:
        session = conn.execute(
            "SELECT * FROM sessions WHERE session_token = ? AND expires_at > datetime('now')",
            (session_token,)
        ).fetchone()
        
        if not session:
            return None
        
        user = conn.execute(
            "SELECT id, username, email, is_active FROM users WHERE id = ?",
            (session["user_id"],)
        ).fetchone()
        
        return User(**user) if user else None

def get_required_user(user: Optional[User] = Depends(get_current_user)) -> User:
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user
