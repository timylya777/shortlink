from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from urllib.parse import urlparse
import secrets
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime

app = FastAPI()

# Настройка путей
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
DB_PATH = os.path.join(BASE_DIR, "links.db")

# Подключаем статические файлы
app.mount("/static", StaticFiles(directory=os.path.join(FRONTEND_DIR, "static")), name="static")

# Инициализация шаблонов
templates = Jinja2Templates(directory=os.path.join(FRONTEND_DIR, "templates"))

# Инициализация БД
def init_db():
    with db_connection() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            short_id TEXT UNIQUE NOT NULL,
            original_url TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            click_count INTEGER DEFAULT 0
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

@app.get("/")
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/about")
async def about_page(request: Request):
    return templates.TemplateResponse("about.html", {"request": request})

@app.get("/all")
async def show_all(request: Request):
    with db_connection() as conn:
        links = conn.execute("""
            SELECT short_id, original_url, click_count 
            FROM links 
            ORDER BY created_at DESC
        """).fetchall()
    
    return templates.TemplateResponse(
        "all_links.html",
        {
            "request": request, 
            "links": [dict(link) for link in links],
            "total_links": len(links)
        }
    )

@app.post("/shorten")
async def shorten_url(request: Request):
    data = await request.json()
    original_url = normalize_url(data.get("original_url"))
    
    if not original_url:
        return {"error": "Invalid URL"}
    
    short_id = secrets.token_urlsafe(5)
    
    with db_connection() as conn:
        try:
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
        
        # Увеличиваем счетчик кликов
        conn.execute(
            "UPDATE links SET click_count = click_count + 1 WHERE short_id = ?",
            (short_id,)
        )
        conn.commit()
        
        return RedirectResponse(
            url=link["original_url"],
            status_code=307
        )
