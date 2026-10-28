import asyncio
import os
import json
import requests
from datetime import datetime
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.types import (
    InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, 
    WebAppInfo, MenuButtonWebApp, ReplyKeyboardMarkup, KeyboardButton, 
    ReplyKeyboardRemove
)

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

API_URL = "https://coffee-bot-46zl.onrender.com"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

SYRUPS = {"vanilla": "Ваниль", "caramel": "Соленая карамель", "condensed": "Сгущенка", "toffee": "Тоффи"}
SYRUP_PRICE = 20
CINNAMON_PRICE = 15

user_carts = {}       
user_temp_choices = {} 
registration_states = {}

def get_menu_from_server():
    try:
        response = requests.get(f"{API_URL}/api/menu", timeout=10)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"Ошибка загрузки меню: {e}")
    return {}

def get_main_menu():
    buttons = [
        [InlineKeyboardButton(text="☕ Кофе", callback_data="cat:coffee")],
        [InlineKeyboardButton(text="🥐 Еда", callback_data="cat:food")],
        [InlineKeyboardButton(text="🛒 Корзина", callback_data="cart")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

@dp.message(CommandStart())
async def start(message: types.Message):
    user_id = message.from_user.id
    user_carts[user_id] = {}
    user_temp_choices[user_id] = {}
    
    if user_id == ADMIN_ID:
        await bot.set_chat_menu_button(
            chat_id=user_id,
            menu_button=MenuButtonWebApp(text="📊 Админка", web_app=WebAppInfo(url=API_URL))
        )
        
    try:
        await message.delete()
    except Exception:
        pass 
        
    try:
        res = requests.get(f"{API_URL}/api/clients/{user_id}", timeout=5)
        if res.status_code == 200:
            await message.answer("Добро пожаловать обратно в нашу кофейню! Что желаете заказать?", reply_markup=get_main_menu())
            return
    except Exception:
        pass
        
    registration_states[user_id] = {"step": "name"}
    
    # Кнопка с именем пользователя из ТГ
    name_btn = KeyboardButton(text=message.from_user.first_name)
    kb = ReplyKeyboardMarkup(keyboard=[[name_btn]], resize_keyboard=True, one_time_keyboard=True)
    
    await message.answer(
        "Для оформления заказа нужно зарегистрироваться.\n\nКак к вам обращаться? Напишите ваше имя или нажмите кнопку ниже.",
        reply_markup=kb
    )

@dp.message(lambda message: message.from_user.id in registration_states)
async def process_registration(message: types.Message):
    user_id = message.from_user.id
    state = registration_states[user_id]["step"]
    
    if state == "name":
        name = message.text
        if not name:
            await message.answer("Пожалуйста, напишите ваше имя текстом.")
            return
            
        registration_states[user_id]["name"] = name
        registration_states[user_id]["step"] = "phone"
        
        kb = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="📱 Поделиться номером", request_contact=True)]],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        await message.answer(
            f"Приятно познакомиться, {name}!\n\nТеперь поделитесь номером телефона, чтобы мы могли связаться с вами.",
            reply_markup=kb
        )
        
    elif state == "phone":
        if message.contact:
            phone = message.contact.phone_number
        else:
            await message.answer("Пожалуйста, нажмите на кнопку «📱 Поделиться номером» ниже.")
            return
            
        name = registration_states[user_id]["name"]
        try:
            requests.post(f"{API_URL}/api/clients", json={
                "user_id": user_id,
                "username": message.from_user.username,
                "name": name,
                "phone": phone
            }, timeout=5)
        except Exception as e:
            print(f"Ошибка сохранения клиента: {e}")
            
        del registration_states[user_id]
        
        await message.answer(
            "✅ Отлично! Регистрация завершена.",
            reply_markup=ReplyKeyboardRemove()
        )
        await message.answer("Что желаете заказать?", reply_markup=get_main_menu())

@dp.callback_query(F.data.startswith("cat:"))
async def show_category(callback: CallbackQuery):
    cat_key = callback.data.split(":")[1]
    menu = get_menu_from_server()
    
    if cat_key not in menu:
        await callback.answer("Категория не найдена (сервер просыпается)", show_alert=True)
        return
        
    cat = menu[cat_key]
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
    menu = get_menu_from_server()
    if cat_key not in menu or item_key not in menu[cat_key]["items"]:
        await callback.answer("Товар не найден", show_alert=True)
        return

    item = menu[cat_key]["items"][item_key]
    
    if cat_key != "coffee":
        await add_item_to_cart(callback, cat_key, item_key, {}, item)
        return

    user_id = callback.from_user.id
    if user_id not in user_temp_choices or user_temp_choices[user_id].get("item") != item_key:
         user_temp_choices[user_id] = {"item": item_key, "syrup": None, "cinnamon": False}
    
    await render_coffee_card(callback, cat_key, item_key, item)

async def render_coffee_card(callback: CallbackQuery, cat_key: str, item_key: str, item: dict):
    user_id = callback.from_user.id
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
        
    menu = get_menu_from_server()
    if cat_key in menu and item_key in menu[cat_key]["items"]:
        await render_coffee_card(callback, cat_key, item_key, menu[cat_key]["items"][item_key])
    else:
        await callback.answer("Ошибка загрузки", show_alert=True)

@dp.callback_query(F.data.startswith("toggle_cinnamon:"))
async def toggle_cinnamon(callback: CallbackQuery):
    _, cat_key, item_key = callback.data.split(":")
    user_id = callback.from_user.id
    if user_id not in user_temp_choices:
         user_temp_choices[user_id] = {"item": item_key, "syrup": None, "cinnamon": False}
         
    user_temp_choices[user_id]["cinnamon"] = not user_temp_choices[user_id].get("cinnamon", False)
    
    menu = get_menu_from_server()
    if cat_key in menu and item_key in menu[cat_key]["items"]:
        await render_coffee_card(callback, cat_key, item_key, menu[cat_key]["items"][item_key])
    else:
        await callback.answer("Ошибка загрузки", show_alert=True)

@dp.callback_query(F.data.startswith("confirm_add:"))
async def confirm_add(callback: CallbackQuery):
    _, cat_key, item_key = callback.data.split(":")
    user_id = callback.from_user.id
    choices = user_temp_choices.get(user_id, {"syrup": None, "cinnamon": False})
    
    menu = get_menu_from_server()
    if cat_key in menu and item_key in menu[cat_key]["items"]:
        await add_item_to_cart(callback, cat_key, item_key, choices, menu[cat_key]["items"][item_key])
        user_temp_choices[user_id] = {} 
    else:
        await callback.answer("Товар не найден", show_alert=True)

async def add_item_to_cart(callback: CallbackQuery, cat_key: str, item_key: str, choices: dict, item: dict):
    user_id = callback.from_user.id
    
    if user_id not in user_carts:
        user_carts[user_id] = {}
        
    cart_key = item_key
    if choices.get("syrup"): cart_key += f"_syrup_{choices['syrup']}"
    if choices.get("cinnamon"): cart_key += "_cinnamon"
    
    if cart_key not in user_carts[user_id]:
        user_carts[user_id][cart_key] = {"qty": 0, "item_key": item_key, "cat_key": cat_key, "choices": choices, "name": item['name'], "base_price": item['price']}
    user_carts[user_id][cart_key]["qty"] += 1
    
    menu = get_menu_from_server()
    cat_name = menu.get(cat_key, {}).get("name", "Меню")
    
    text = f"{cat_name}\nВыберите позицию:\n\n✅ *«{item['name']}» добавлен в корзину!*"
    
    buttons = []
    if cat_key in menu:
        for i_key, i_item in menu[cat_key]["items"].items():
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
        item_name = data.get("name", "Товар")
        base_price = data.get("base_price", 0)
        qty = data["qty"]
        choices = data["choices"]
        
        single_price = base_price
        if choices.get("syrup"): single_price += SYRUP_PRICE
        if choices.get("cinnamon"): single_price += CINNAMON_PRICE
        
        sum_price = single_price * qty
        total += sum_price
        
        text += f"• {item_name} x{qty} = {sum_price}₽\n"
        if choices.get("syrup"):
            text += f"   └ Сироп {SYRUPS[choices['syrup']]}\n"
        if choices.get("cinnamon"):
            text += f"   └ Корица\n"
            
        buttons.append([InlineKeyboardButton(text=f"➖ Убрать 1 шт. {item_name}", callback_data=f"del:{cart_key}")])

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
    order_items_for_json = []
    
    for cart_key, data in cart.items():
        item_name = data.get("name", "Товар")
        base_price = data.get("base_price", 0)
        qty = data["qty"]
        choices = data["choices"]
        
        single_price = base_price
        if choices.get("syrup"): single_price += SYRUP_PRICE
        if choices.get("cinnamon"): single_price += CINNAMON_PRICE
        
        sum_price = single_price * qty
        total += sum_price
        
        order_text += f"• {item_name} x{qty} = {sum_price}₽\n"
        if choices.get("syrup"): order_text += f"   └ Сироп {SYRUPS[choices['syrup']]}\n"
        if choices.get("cinnamon"): order_text += f"   └ Корица\n"

        syrup_name = SYRUPS.get(choices.get("syrup")) if choices.get("syrup") else None
        order_items_for_json.append({
            "name": item_name,
            "qty": qty,
            "price": sum_price,
            "syrup": syrup_name,
            "cinnamon": choices.get("cinnamon")
        })

    order_text += f"\n**Итого к оплате: {total}₽**"

    await bot.send_message(chat_id=ADMIN_ID, text=order_text, parse_mode="Markdown")
    
    try:
        requests.post(f"{API_URL}/api/orders", json={
            "user_id": user_id,
            "username": callback.from_user.username,
            "date": datetime.now().strftime("%d.%m %H:%M"),
            "items": order_items_for_json,
            "total": total,
            "status": "new"
        }, timeout=5)
    except Exception as e:
        print(f"Не удалось сохранить заказ на сервере: {e}")
    
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
