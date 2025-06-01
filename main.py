from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from urllib.parse import urlparse
import secrets
import os
import sqlite3
from datetime import datetime
from typing import Optional

# Импорты из наших модулей
from auth import router as auth_router
from dependencies import get_current_user
from database import db_connection, init_db
from models import User

app = FastAPI()

# Настройка путей
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
DB_PATH = os.path.join(BASE_DIR, "links.db")

# Подключаем статические файлы
app.mount("/static", StaticFiles(directory=os.path.join(FRONTEND_DIR, "static")), name="static")

# Инициализация шаблонов
templates = Jinja2Templates(directory=os.path.join(FRONTEND_DIR, "templates"))

# Подключаем роутер аутентификации
app.include_router(auth_router)

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

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    user = get_current_user(request)
    return templates.TemplateResponse(
        "index.html", 
        {
            "request": request,
            "user": user.dict() if user else None
        }
    )

@app.get("/about", response_class=HTMLResponse)
async def about_page(request: Request):
    user = get_current_user(request)
    return templates.TemplateResponse(
        "about.html", 
        {
            "request": request,
            "user": user.dict() if user else None
        }
    )

@app.get("/all", response_class=HTMLResponse)
async def show_all(request: Request):
    user = get_current_user(request)
    
    with db_connection() as conn:
        if user:
            links = conn.execute("""
                SELECT short_id, original_url, click_count, created_at
                FROM links 
                WHERE user_id = ?
                ORDER BY created_at DESC
            """, (user.id,)).fetchall()
        else:
            links = []
    
    return templates.TemplateResponse(
        "all_links.html",
        {
            "request": request,
            "links": [dict(link) for link in links],
            "total_links": len(links),
            "user": user.dict() if user else None
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
                    (short_id, original_url, user.id)
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

@app.get("/api/links", response_model=list[dict])
async def get_user_links(user: Optional[User] = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    with db_connection() as conn:
        links = conn.execute("""
            SELECT short_id, original_url, click_count, created_at
            FROM links 
            WHERE user_id = ?
            ORDER BY created_at DESC
        """, (user.id,)).fetchall()
    
    return [dict(link) for link in links]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
