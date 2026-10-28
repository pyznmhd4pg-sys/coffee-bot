import asyncio
import os
import json
from datetime import datetime
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, WebAppInfo, MenuButtonWebApp

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Основное меню
MENU = {
    "coffee": {
        "name": "☕ Кофе",
        "items": {
            "americano": {"name": "Американо 350 мл", "price": 240},
            "americano_milk": {"name": "Американо с молоком 350 мл", "price": 260},
            "flat_white": {"name": "Флэт уайт 350 мл", "price": 260},
            "mochaccino": {"name": "Мокачино 350 мл", "price": 250},
            "raf": {"name": "Раф 350 мл", "price": 260},
            "cappuccino": {"name": "Капучино 350 мл", "price": 260},
            "latte": {"name": "Латте 350 мл", "price": 260},
            "hot_chocolate": {"name": "Горячий шоколад 350 мл", "price": 240},
        }
    },
    "food": {
        "name": "🥐 Еда",
        "items": {
            "croissant": {"name": "Круассан с ветчиной", "price": 200},
            "caesar": {"name": "Салат Цезарь", "price": 280},
            "macaron": {"name": "Макарун 1 шт", "price": 90},
            "cheesecake": {"name": "Чизкейк 1 шт", "price": 150},
        }
    }
}

SYRUPS = {"vanilla": "Ваниль", "caramel": "Соленая карамель", "condensed": "Сгущенка", "toffee": "Тоффи"}
SYRUP_PRICE = 20
CINNAMON_PRICE = 15

user_carts = {}       
user_temp_choices = {} 

def get_main_menu():
    buttons = [
        [InlineKeyboardButton(text="☕ Кофе", callback_data="cat:coffee")],
        [InlineKeyboardButton(text="🥐 Еда", callback_data="cat:food")],
        [InlineKeyboardButton(text="🛒 Корзина", callback_data="cart")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

@dp.message(CommandStart())
async def start(message: types.Message):
    user_carts[message.from_user.id] = {}
    user_temp_choices[message.from_user.id] = {}
    
    # Если пишет админ, показываем ему кнопку для открытия Mini App
    if message.from_user.id == ADMIN_ID:
        # Устанавливаем кнопку меню (слева от поля ввода)
        await bot.set_chat_menu_button(
            chat_id=message.from_user.id,
            menu_button=MenuButtonWebApp(text="📊 Админка", web_app=WebAppInfo(url="https://ваш_туннель.ngrok.io"))
        )
        
    try:
        await message.delete()
    except Exception:
        pass 
        
    await message.answer("Добро пожаловать в нашу кофейню! Что желаете заказать?", reply_markup=get_main_menu())

@dp.callback_query(F.data.startswith("cat:"))
async def show_category(callback: CallbackQuery):
    cat_key = callback.data.split(":")[1]
    cat = MENU[cat_key]
    buttons = []
    for item_key, item in cat["items"].items():
        buttons.append([InlineKeyboardButton(text=f"{item['name']} — {item['price']}₽", callback_data=f"item:{cat_key}:{item_key}")])
    buttons.append([InlineKeyboardButton(text="🛒 Корзина", callback_data="cart")])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")])
    await callback.message.edit_text(f"{cat['name']}\nВыберите позицию:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await callback.answer()

@dp.callback_query(F.data.startswith("item:"))
async def show_item_details(callback: CallbackQuery):
    _, cat_key, item_key = callback.data.split(":")
    item = MENU[cat_key]["items"][item_key]
    
    if cat_key != "coffee":
        await add_item_to_cart(callback, cat_key, item_key, {})
        return

    user_id = callback.from_user.id
    if user_id not in user_temp_choices or user_temp_choices[user_id].get("item") != item_key:
         user_temp_choices[user_id] = {"item": item_key, "syrup": None, "cinnamon": False}
    
    await render_coffee_card(callback, cat_key, item_key)

async def render_coffee_card(callback: CallbackQuery, cat_key: str, item_key: str):
    user_id = callback.from_user.id
    item = MENU[cat_key]["items"][item_key]
    choices = user_temp_choices.get(user_id, {"item": item_key, "syrup": None, "cinnamon": False})
    
    text = f"☕ **{item['name']}** ({item['price']}₽)\n\n"
    text += "Что-нибудь добавим?\n"
    
    total_price = item["price"]
    
    if choices.get("syrup"):
        text += f"   └ + Сироп {SYRUPS[choices['syrup']]} (20₽)\n"
        total_price += SYRUP_PRICE
    if choices.get("cinnamon"):
        text += f"   └ + Корица (15₽)\n"
        total_price += CINNAMON_PRICE
        
    text += f"\n**Итого: {total_price}₽**"

    buttons = []
    
    if choices.get("syrup") or choices.get("cinnamon"):
        buttons.append([InlineKeyboardButton(text="🛒 Добавить в корзину", callback_data=f"confirm_add:{cat_key}:{item_key}")])
    else:
        buttons.append([InlineKeyboardButton(text="Нет, спасибо (сразу в корзину)", callback_data=f"confirm_add:{cat_key}:{item_key}")])
    
    syrup_btn_text = "✅ Сироп выбран" if choices.get("syrup") else "➕ Добавить сироп (20₽)"
    buttons.append([InlineKeyboardButton(text=syrup_btn_text, callback_data=f"syrup_menu:{cat_key}:{item_key}")])
    
    cinnamon_btn_text = "✅ Корица добавлена" if choices.get("cinnamon") else "➕ Добавить корицу (15₽)"
    buttons.append([InlineKeyboardButton(text=cinnamon_btn_text, callback_data=f"toggle_cinnamon:{cat_key}:{item_key}")])
    
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data=f"cat:{cat_key}")])

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data.startswith("syrup_menu:"))
async def show_syrup_menu(callback: CallbackQuery):
    _, cat_key, item_key = callback.data.split(":")
    buttons = []
    for s_key, s_name in SYRUPS.items():
        buttons.append([InlineKeyboardButton(text=s_name, callback_data=f"set_syrup:{cat_key}:{item_key}:{s_key}")])
    buttons.append([InlineKeyboardButton(text="🔙 Назад к кофе", callback_data=f"item:{cat_key}:{item_key}")])
    
    await callback.message.edit_text("Выберите сироп (20₽):", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await callback.answer()

@dp.callback_query(F.data.startswith("set_syrup:"))
async def set_syrup(callback: CallbackQuery):
    _, cat_key, item_key, syrup_key = callback.data.split(":")
    user_id = callback.from_user.id
    if user_id not in user_temp_choices:
        user_temp_choices[user_id] = {"item": item_key, "syrup": None, "cinnamon": False}
    
    if user_temp_choices[user_id].get("syrup") == syrup_key:
        user_temp_choices[user_id]["syrup"] = None
    else:
        user_temp_choices[user_id]["syrup"] = syrup_key
        
    await render_coffee_card(callback, cat_key, item_key)

@dp.callback_query(F.data.startswith("toggle_cinnamon:"))
async def toggle_cinnamon(callback: CallbackQuery):
    _, cat_key, item_key = callback.data.split(":")
    user_id = callback.from_user.id
    if user_id not in user_temp_choices:
         user_temp_choices[user_id] = {"item": item_key, "syrup": None, "cinnamon": False}
         
    user_temp_choices[user_id]["cinnamon"] = not user_temp_choices[user_id].get("cinnamon", False)
    await render_coffee_card(callback, cat_key, item_key)

@dp.callback_query(F.data.startswith("confirm_add:"))
async def confirm_add(callback: CallbackQuery):
    _, cat_key, item_key = callback.data.split(":")
    user_id = callback.from_user.id
    choices = user_temp_choices.get(user_id, {"syrup": None, "cinnamon": False})
    
    await add_item_to_cart(callback, cat_key, item_key, choices)
    user_temp_choices[user_id] = {} 

async def add_item_to_cart(callback: CallbackQuery, cat_key: str, item_key: str, choices: dict):
    item = MENU[cat_key]["items"][item_key]
    user_id = callback.from_user.id
    
    if user_id not in user_carts:
        user_carts[user_id] = {}
        
    cart_key = item_key
    if choices.get("syrup"): cart_key += f"_syrup_{choices['syrup']}"
    if choices.get("cinnamon"): cart_key += "_cinnamon"
    
    if cart_key not in user_carts[user_id]:
        user_carts[user_id][cart_key] = {"qty": 0, "item_key": item_key, "cat_key": cat_key, "choices": choices}
    user_carts[user_id][cart_key]["qty"] += 1
    
    cat = MENU[cat_key]
    text = f"{cat['name']}\nВыберите позицию:\n\n✅ *«{item['name']}» добавлен в корзину!*"
    
    buttons = []
    for i_key, i_item in cat["items"].items():
        buttons.append([InlineKeyboardButton(text=f"{i_item['name']} — {i_item['price']}₽", callback_data=f"item:{cat_key}:{i_key}")])
    buttons.append([InlineKeyboardButton(text="🛒 Корзина", callback_data="cart")])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")])
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "cart")
async def show_cart(callback: CallbackQuery):
    user_id = callback.from_user.id
    cart = user_carts.get(user_id, {})
    
    if not cart:
        await callback.answer("Ваша корзина пуста", show_alert=True)
        return

    text = "🛒 **Ваша корзина:**\n\n"
    total = 0
    buttons = []
    
    for cart_key, data in cart.items():
        item = MENU[data["cat_key"]]["items"][data["item_key"]]
        qty = data["qty"]
        choices = data["choices"]
        
        single_price = item["price"]
        if choices.get("syrup"): single_price += SYRUP_PRICE
        if choices.get("cinnamon"): single_price += CINNAMON_PRICE
        
        sum_price = single_price * qty
        total += sum_price
        
        text += f"• {item['name']} x{qty} = {sum_price}₽\n"
        if choices.get("syrup"):
            text += f"   └ Сироп {SYRUPS[choices['syrup']]}\n"
        if choices.get("cinnamon"):
            text += f"   └ Корица\n"
            
        buttons.append([InlineKeyboardButton(text=f"➖ Убрать 1 шт. {item['name']}", callback_data=f"del:{cart_key}")])

    text += f"\n**Итого: {total}₽**"
    
    buttons.append([InlineKeyboardButton(text="✅ Оформить заказ", callback_data="checkout")])
    buttons.append([InlineKeyboardButton(text="⬅️ В меню", callback_data="main_menu")])
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data.startswith("del:"))
async def delete_from_cart(callback: CallbackQuery):
    cart_key = callback.data.split(":")[1]
    user_id = callback.from_user.id
    
    if user_id in user_carts and cart_key in user_carts[user_id]:
        user_carts[user_id][cart_key]["qty"] -= 1
        if user_carts[user_id][cart_key]["qty"] <= 0:
            del user_carts[user_id][cart_key]
    
    await show_cart(callback)

@dp.callback_query(F.data == "checkout")
async def checkout(callback: CallbackQuery):
    user_id = callback.from_user.id
    cart = user_carts.get(user_id, {})
    
    if not cart:
        await callback.answer("Корзина пуста", show_alert=True)
        return

    order_text = f"🔔 **Новый заказ!**\nКлиент: @{callback.from_user.username or user_id}\n\n"
    total = 0
    
    # Список для сохранения в JSON
    order_items_for_json = []
    
    for cart_key, data in cart.items():
        item = MENU[data["cat_key"]]["items"][data["item_key"]]
        qty = data["qty"]
        choices = data["choices"]
        
        single_price = item["price"]
        if choices.get("syrup"): single_price += SYRUP_PRICE
        if choices.get("cinnamon"): single_price += CINNAMON_PRICE
        
        sum_price = single_price * qty
        total += sum_price
        
        order_text += f"• {item['name']} x{qty} = {sum_price}₽\n"
        if choices.get("syrup"): order_text += f"   └ Сироп {SYRUPS[choices['syrup']]}\n"
        if choices.get("cinnamon"): order_text += f"   └ Корица\n"

        # Сохраняем инфу для Mini App
        syrup_name = SYRUPS.get(choices.get("syrup")) if choices.get("syrup") else None
        order_items_for_json.append({
            "name": item["name"],
            "qty": qty,
            "price": sum_price,
            "syrup": syrup_name,
            "cinnamon": choices.get("cinnamon")
        })

    order_text += f"\n**Итого к оплате: {total}₽**"

    # Отправляем в ТГ
    await bot.send_message(chat_id=ADMIN_ID, text=order_text, parse_mode="Markdown")
    
    # Сохраняем в файл orders.json для Mini App
    orders = []
    if os.path.exists("orders.json"):
        with open("orders.json", "r", encoding="utf-8") as f:
            try:
                orders = json.load(f)
            except json.JSONDecodeError:
                orders = []
                
    orders.append({
        "user_id": user_id,
        "username": callback.from_user.username,
        "date": datetime.now().strftime("%d.%m %H:%M"),
        "items": order_items_for_json,
        "total": total
    })
    
    with open("orders.json", "w", encoding="utf-8") as f:
        json.dump(orders, f, ensure_ascii=False, indent=2)
    
    user_carts[user_id] = {}
    
    await callback.message.edit_text("✅ Заказ успешно оформлен!\nС вами свяжутся для подтверждения.", reply_markup=get_main_menu())
    await callback.answer()

@dp.callback_query(F.data == "main_menu")
async def back_to_main(callback: CallbackQuery):
    await callback.message.edit_text("Добро пожаловать в нашу кофейню! Что желаете заказать?", reply_markup=get_main_menu())
    await callback.answer()

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())