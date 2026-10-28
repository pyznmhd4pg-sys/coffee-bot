import json
import os
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import List, Optional
import uvicorn

app = FastAPI()

BASE_DIR = Path(__file__).resolve().parent
WEBAPP_DIR = BASE_DIR / "webapp"
MENU_FILE = BASE_DIR / "menu.json"
ORDERS_FILE = BASE_DIR / "orders.json"
CLIENTS_FILE = BASE_DIR / "clients.json"

app.mount("/webapp", StaticFiles(directory=WEBAPP_DIR), name="webapp")

# ... (модели данных остаются прежними) ...
class ClientCreate(BaseModel):
    user_id: int
    username: Optional[str] = None
    name: str
    phone: str

# ... (функции load_menu, save_menu, load_orders, save_orders остаются прежними) ...

def load_clients():
    if not os.path.exists(CLIENTS_FILE): return {}
    with open(CLIENTS_FILE, "r", encoding="utf-8") as f:
        try: return json.load(f)
        except: return {}

def save_clients(clients):
    with open(CLIENTS_FILE, "w", encoding="utf-8") as f:
        json.dump(clients, f, ensure_ascii=False, indent=2)

# ... (API меню и заказов остаются) ...

@app.get("/api/clients/{user_id}")
async def get_client(user_id: int):
    clients = load_clients()
    if str(user_id) in clients:
        return clients[str(user_id)]
    raise HTTPException(status_code=404, detail="Client not found")

@app.post("/api/clients")
async def create_client(client: ClientCreate):
    clients = load_clients()
    clients[str(client.user_id)] = {
        "user_id": client.user_id,
        "username": client.username,
        "name": client.name,
        "phone": client.phone,
        "orders_count": clients.get(str(client.user_id), {}).get("orders_count", 0)
    }
    save_clients(clients)
    return {"status": "ok"}

@app.get("/api/clients")
async def get_all_clients():
    # Считаем количество заказов для каждого клиента
    clients = load_clients()
    orders = load_orders()
    
    for c_id, c_data in clients.items():
        c_orders = [o for o in orders if str(o.get("user_id")) == c_id]
        c_data["orders_count"] = len(c_orders)
        
    return {"clients": list(clients.values())}
