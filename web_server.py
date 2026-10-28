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

class CategoryCreate(BaseModel):
    name: str

class ItemCreate(BaseModel):
    name: str
    price: int

class PriceUpdate(BaseModel):
    price: int

class OrderItem(BaseModel):
    name: str
    qty: int
    price: int
    syrup: Optional[str] = None
    cinnamon: bool = False

class OrderCreate(BaseModel):
    user_id: int
    username: Optional[str] = None
    date: str
    items: List[OrderItem]
    total: int
    status: str = "new"

class ClientCreate(BaseModel):
    user_id: int
    username: Optional[str] = None
    name: str
    phone: str

DEFAULT_MENU = {
    "coffee": {"name": "☕ Кофе", "items": {"americano": {"name": "Американо 350 мл", "price": 240}, "latte": {"name": "Латте 350 мл", "price": 260}}},
    "food": {"name": "🥐 Еда", "items": {"croissant": {"name": "Круассан с ветчиной", "price": 200}, "cheesecake": {"name": "Чизкейк 1 шт", "price": 150}}}
}

def load_menu():
    if not os.path.exists(MENU_FILE):
        with open(MENU_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_MENU, f, ensure_ascii=False, indent=2)
        return DEFAULT_MENU
    with open(MENU_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_menu(menu):
    with open(MENU_FILE, "w", encoding="utf-8") as f:
        json.dump(menu, f, ensure_ascii=False, indent=2)

def load_orders():
    if not os.path.exists(ORDERS_FILE): return []
    with open(ORDERS_FILE, "r", encoding="utf-8") as f:
        try: return json.load(f)
        except: return []

def save_orders(orders):
    with open(ORDERS_FILE, "w", encoding="utf-8") as f:
        json.dump(orders, f, ensure_ascii=False, indent=2)

def load_clients():
    if not os.path.exists(CLIENTS_FILE): return {}
    with open(CLIENTS_FILE, "r", encoding="utf-8") as f:
        try: return json.load(f)
        except: return {}

def save_clients(clients):
    with open(CLIENTS_FILE, "w", encoding="utf-8") as f:
        json.dump(clients, f, ensure_ascii=False, indent=2)

@app.get("/", response_class=HTMLResponse)
async def read_index():
    return HTMLResponse(content=(WEBAPP_DIR / "index.html").read_text(encoding="utf-8"))

@app.get("/api/menu")
async def get_menu():
    return load_menu()

@app.post("/api/category")
async def add_category(cat: CategoryCreate):
    menu = load_menu()
    cat_id = f"cat_{int(os.urandom(2).hex(), 16)}"
    menu[cat_id] = {"name": cat.name, "items": {}}
    save_menu(menu)
    return {"status": "ok", "id": cat_id}

@app.delete("/api/category/{cat_id}")
async def delete_category(cat_id: str):
    menu = load_menu()
    if cat_id in menu:
        del menu[cat_id]
        save_menu(menu)
    return {"status": "ok"}

@app.post("/api/category/{cat_id}/item")
async def add_item(cat_id: str, item: ItemCreate):
    menu = load_menu()
    if cat_id not in menu: raise HTTPException(status_code=404)
    item_id = f"item_{int(os.urandom(2).hex(), 16)}"
    menu[cat_id]["items"][item_id] = {"name": item.name, "price": item.price}
    save_menu(menu)
    return {"status": "ok", "id": item_id}

@app.delete("/api/category/{cat_id}/item/{item_id}")
async def delete_item(cat_id: str, item_id: str):
    menu = load_menu()
    if cat_id in menu and item_id in menu[cat_id]["items"]:
        del menu[cat_id]["items"][item_id]
        save_menu(menu)
    return {"status": "ok"}

@app.put("/api/category/{cat_id}/item/{item_id}/price")
async def update_price(cat_id: str, item_id: str, data: PriceUpdate):
    menu = load_menu()
    if cat_id in menu and item_id in menu[cat_id]["items"]:
        menu[cat_id]["items"][item_id]["price"] = data.price
        save_menu(menu)
    return {"status": "ok"}

@app.get("/api/orders")
async def get_orders():
    orders = load_orders()
    # Добавляем индекс к каждому заказу для фронтенда
    for i, order in enumerate(orders):
        order["index"] = i
    return {"orders": orders}

@app.post("/api/orders")
async def create_order(order: OrderCreate):
    orders = load_orders()
    orders.append(order.model_dump())
    save_orders(orders)
    return {"status": "ok"}

@app.post("/api/orders/{order_index}/action")
async def process_order(order_index: int, action: str): # Упростил для примера
    orders = load_orders()
    if order_index >= len(orders): raise HTTPException(status_code=404)
    orders[order_index]["status"] = "done"
    save_orders(orders)
    return {"status": "ok"}

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
    clients = load_clients()
    orders = load_orders()
    for c_id, c_data in clients.items():
        c_orders = [o for o in orders if str(o.get("user_id")) == c_id]
        c_data["orders_count"] = len(c_orders)
    return {"clients": list(clients.values())}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
