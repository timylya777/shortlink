from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

import secrets
import os

app = FastAPI()

# Настройка путей
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

# Подключаем статические файлы
app.mount("/static", StaticFiles(directory=os.path.join(FRONTEND_DIR, "static")), name="static")

# Инициализация шаблонов
templates = Jinja2Templates(directory=os.path.join(FRONTEND_DIR, "templates"))

# Хранилище ссылок
url_storage = {}

# Главная страница
@app.get("/")
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})
# Добавьте новые маршруты
@app.get("/about")
async def about_page(request: Request):
    return templates.TemplateResponse("about.html", {"request": request})
# Страница со всеми ссылками
@app.get("/all")
async def show_all(request: Request):
    return templates.TemplateResponse(
        "all_links.html",
        {"request": request, "links": url_storage}
    )

# Остальные endpoint'ы...
@app.post("/shorten")
async def shorten_url(request: Request):
    data = await request.json()
    original_url = data.get("original_url")
    
    if not original_url:
        return {"error": "URL is required"}
    
    short_id = secrets.token_urlsafe(5)
    url_storage[short_id] = original_url
    
    return {
        "short_url": f"http://shortlink-s4v6.onrender.com/{short_id}",
        "original_url": original_url
    }

@app.get("/{short_id}")
async def redirect(short_id: str):
    if short_id not in url_storage:
        raise HTTPException(
            status_code=404,
            detail="Short link not found",
            headers={"X-Error": "Link not found"}
        )
    
    target_url = url_storage[short_id]
    return RedirectResponse(
        url=target_url,
        status_code=307  # Temporary Redirect (сохраняет метод запроса)
    )
