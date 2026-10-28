import json
import os
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import uvicorn

app = FastAPI()

# Указываем, что папка webapp содержит статические файлы (HTML, CSS)
app.mount("/webapp", StaticFiles(directory="webapp"), name="webapp")

@app.get("/", response_class=HTMLResponse)
async def read_index():
    # Отдаем главную страницу Mini App
    with open("webapp/index.html", "r", encoding="utf-8") as f:
        return f.read()

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
    # Запускаем сервер на порту 8000
    uvicorn.run(app, host="127.0.0.1", port=8000)