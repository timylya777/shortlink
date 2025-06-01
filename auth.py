from fastapi import APIRouter, HTTPException, status, Response, Request, Depends
from fastapi.security import HTTPBasic
from datetime import datetime, timedelta
import secrets
from passlib.context import CryptContext
from typing import Optional

from database import db_connection
from models import User, Session
from schemas import UserCreate, UserLogin
from dependencies import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBasic()

def verify_password(plain_password: str, hashed_password: str):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str):
    return pwd_context.hash(password)

def create_session_token() -> str:
    return secrets.token_urlsafe(32)

@router.post("/register")
async def register_user(user_data: UserCreate):
    hashed_password = get_password_hash(user_data.password)
    
    with db_connection() as conn:
        try:
            cursor = conn.execute(
                "INSERT INTO users (username, email, hashed_password) VALUES (?, ?, ?) RETURNING id",
                (user_data.username, user_data.email, hashed_password)
            )
            user_id = cursor.fetchone()["id"]
            conn.commit()
        except sqlite3.IntegrityError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username or email already exists"
            )
    
    return {"id": user_id, "username": user_data.username}

@router.post("/login")
async def login_user(response: Response, user_data: UserLogin):
    with db_connection() as conn:
        user = conn.execute(
            "SELECT * FROM users WHERE username = ?",
            (user_data.username,)
        ).fetchone()
        
        if not user or not verify_password(user_data.password, user["hashed_password"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password"
            )
        
        # Создаем новую сессию
        session_token = create_session_token()
        expires_at = datetime.now() + timedelta(days=7)
        
        conn.execute(
            "INSERT INTO sessions (user_id, session_token, expires_at) VALUES (?, ?, ?)",
            (user["id"], session_token, expires_at)
        )
        conn.commit()
        
        # Устанавливаем cookie
        response.set_cookie(
            key="session_token",
            value=session_token,
            httponly=True,
            max_age=60*60*24*7,  # 7 дней
            secure=False,  # В production должно быть True
            samesite="lax"
        )
        
        return {"username": user["username"]}

@router.post("/logout")
async def logout_user(response: Response, request: Request):
    session_token = request.cookies.get("session_token")
    if session_token:
        with db_connection() as conn:
            conn.execute(
                "DELETE FROM sessions WHERE session_token = ?",
                (session_token,)
            )
            conn.commit()
    
    response.delete_cookie("session_token")
    return {"message": "Logged out successfully"}

@router.get("/me")
async def get_current_user_info(user: User = Depends(get_current_user)):
    return {"user": user}
