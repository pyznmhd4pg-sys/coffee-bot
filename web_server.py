import json
import os
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import uvicorn

app = FastAPI()

# Определяем абсолютный путь к папке webapp, чтобы сервер на Render не терял её
BASE_DIR = Path(__file__).resolve().parent
WEBAPP_DIR = BASE_DIR / "webapp"

# Указываем FastAPI, где искать статические файлы (HTML, CSS)
app.mount("/webapp", StaticFiles(directory=WEBAPP_DIR), name="webapp")

@app.get("/", response_class=HTMLResponse)
async def read_index():
    # Читаем и отдаем главную страницу Mini App
    index_file = WEBAPP_DIR / "index.html"
    return HTMLResponse(content=index_file.read_text(encoding="utf-8"))

@app.get("/api/orders")
async def get_orders(request: Request):
    # В реальном проекте здесь была бы проверка initData от Telegram.
    # Для демо мы просто отдаем все заказы, которые есть в файле.
    
    if not os.path.exists("orders.json"):
        return {"orders": []}
        
    with open("orders.json", "r", encoding="utf-8") as f:
        try:
            orders = json.load(f)
        except json.JSONDecodeError:
            orders = []
            
    return {"orders": orders}

if __name__ == "__main__":
    # Запускаем сервер локально на порту 8000 (для тестов на компьютере)
    uvicorn.run(app, host="127.0.0.1", port=8000)