from fastapi import FastAPI, Request, HTTPException, Depends, status, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from urllib.parse import urlparse
import secrets
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from passlib.context import CryptContext
from typing import Optional

app = FastAPI()

# Настройка путей
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
DB_PATH = os.path.join(BASE_DIR, "links.db")

# Настройки безопасности
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBasic()

# Подключаем статические файлы
app.mount("/static", StaticFiles(directory=os.path.join(FRONTEND_DIR, "static")), name="static")

# Инициализация шаблонов
templates = Jinja2Templates(directory=os.path.join(FRONTEND_DIR, "templates"))

# Инициализация БД
def init_db():
    with db_connection() as conn:
        # Таблица пользователей
        conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE,
            hashed_password TEXT NOT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # Таблица сессий
        conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            session_token TEXT NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """)
        
        # Обновленная таблица ссылок
        conn.execute("""
        CREATE TABLE IF NOT EXISTS links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            short_id TEXT UNIQUE NOT NULL,
            original_url TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            click_count INTEGER DEFAULT 0,
            user_id INTEGER,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """)
        conn.commit()

@contextmanager
def db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

# Инициализируем БД при старте
init_db()

# Вспомогательные функции
def verify_password(plain_password: str, hashed_password: str):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str):
    return pwd_context.hash(password)

def create_session_token() -> str:
    return secrets.token_urlsafe(32)

def get_current_user(request: Request) -> Optional[dict]:
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
            "SELECT * FROM users WHERE id = ?",
            (session["user_id"],)
        ).fetchone()
        
        return dict(user) if user else None

# Маршруты для аутентификации
@app.post("/register")
async def register_user(request: Request):
    data = await request.json()
    username = data.get("username")
    password = data.get("password")
    email = data.get("email")
    
    if not username or not password:
        return {"error": "Username and password are required"}
    
    hashed_password = get_password_hash(password)
    
    with db_connection() as conn:
        try:
            conn.execute(
                "INSERT INTO users (username, email, hashed_password) VALUES (?, ?, ?)",
                (username, email, hashed_password)
            )
            conn.commit()
        except sqlite3.IntegrityError as e:
            return {"error": "Username or email already exists"}
    
    return {"success": True}

@app.post("/login")
async def login_user(response: Response, request: Request):
    data = await request.json()
    username = data.get("username")
    password = data.get("password")
    
    with db_connection() as conn:
        user = conn.execute(
            "SELECT * FROM users WHERE username = ?",
            (username,)
        ).fetchone()
        
        if not user or not verify_password(password, user["hashed_password"]):
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
        
        return {"success": True}

@app.post("/logout")
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
    return {"success": True}

@app.get("/me")
async def get_current_user_info(user: dict = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return {"user": user}

# Обновленные маршруты для работы с ссылками
@app.get("/")
async def read_root(request: Request):
    user = get_current_user(request)
    return templates.TemplateResponse(
        "index.html", 
        {"request": request, "user": user}
    )

@app.get("/about")
async def about_page(request: Request):
    user = get_current_user(request)
    return templates.TemplateResponse(
        "about.html", 
        {"request": request, "user": user}
    )

@app.get("/all")
async def show_all(request: Request):
    user = get_current_user(request)
    
    with db_connection() as conn:
        if user:
            links = conn.execute("""
                SELECT short_id, original_url, click_count 
                FROM links 
                WHERE user_id = ?
                ORDER BY created_at DESC
            """, (user["id"],)).fetchall()
        else:
            links = []
    
    return templates.TemplateResponse(
        "all_links.html",
        {
            "request": request, 
            "links": [dict(link) for link in links],
            "total_links": len(links),
            "user": user
        }
    )

@app.post("/shorten")
async def shorten_url(request: Request):
    user = get_current_user(request)
    data = await request.json()
    original_url = normalize_url(data.get("original_url"))
    
    if not original_url:
        return {"error": "Invalid URL"}
    
    short_id = secrets.token_urlsafe(5)
    
    with db_connection() as conn:
        try:
            if user:
                conn.execute(
                    "INSERT INTO links (short_id, original_url, user_id) VALUES (?, ?, ?)",
                    (short_id, original_url, user["id"])
                )
            else:
                conn.execute(
                    "INSERT INTO links (short_id, original_url) VALUES (?, ?)",
                    (short_id, original_url)
                )
            conn.commit()
        except sqlite3.IntegrityError:
            return {"error": "Failed to generate unique short URL, please try again"}
    
    return {
        "short_url": f"{request.base_url}{short_id}",
        "original_url": original_url
    }

@app.get("/{short_id}")
async def redirect(short_id: str):
    with db_connection() as conn:
        link = conn.execute(
            "SELECT original_url FROM links WHERE short_id = ?", 
            (short_id,)
        ).fetchone()
        
        if not link:
            raise HTTPException(
                status_code=404,
                detail="Short link not found",
                headers={"X-Error": "Link not found"}
            )
        
        conn.execute(
            "UPDATE links SET click_count = click_count + 1 WHERE short_id = ?",
            (short_id,)
        )
        conn.commit()
        
        return RedirectResponse(
            url=link["original_url"],
            status_code=307
        )

def normalize_url(url: str):
    default_scheme = "https"
    if not url or not isinstance(url, str):
        return None
    
    url = url.strip()
    
    if '://' in url:
        parsed = urlparse(url)
        if all([parsed.scheme, parsed.netloc]):
            return url
        return None
    
    if '.' in url and not url.startswith(('http', 'ftp', 'content')):
        return f"{default_scheme}://{url}"
    
    if ':/' in url and not url.startswith(('http', 'ftp')):
        if not url.startswith(('content', 'file', 'ftp')):
            return None
        return url.replace(':/', '://', 1)
    
    return None
