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
registration_states = {} # Для хранения этапа регистрации

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
        
    # Проверяем, зарегистрирован ли пользователь
    try:
        res = requests.get(f"{API_URL}/api/clients/{user_id}", timeout=5)
        if res.status_code == 200:
            # Пользователь уже есть
            await message.answer("Добро пожаловать обратно в нашу кофейню! Что желаете заказать?", reply_markup=get_main_menu())
            return
    except Exception:
        pass
        
    # Если нет — начинаем регистрацию
    registration_states[user_id] = {"step": "name"}
    
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Отправить имя из Telegram", request_contact=False)]], # Хак для получения имени
        resize_keyboard=True,
        one_time_keyboard=True
    )
    # В Telegram нет кнопки "Отправить имя", поэтому просто просим ввести текстом
    # Но чтобы было красиво, мы дадим кнопку с именем пользователя, при нажатии на которую он отправит это имя
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
        
        # Убираем клавиатуру с именем и просим телефон
        kb = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="📱 Поделиться номером", request_contact=True)]],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        await message.answer(
            f"Приятно познакомиться, {name}!\n\nТеперь поделитесь номером телефона, чтобы мы могли связаться с вами по заказу.",
            reply_markup=kb
        )
        
    elif state == "phone":
        if message.contact:
            phone = message.contact.phone_number
        else:
            # Если он не нажал кнопку, а написал текст, просим еще раз
            await message.answer("Пожалуйста, нажмите на кнопку «📱 Поделиться номером» ниже.")
            return
            
        # Сохраняем на сервер
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
            "✅ Отлично! Регистрация завершена. Теперь вы можете сделать заказ.",
            reply_markup=ReplyKeyboardRemove()
        )
        await message.answer("Что желаете заказать?", reply_markup=get_main_menu())

@dp.callback_query(F.data.startswith("cat:"))
async def show_category(callback: CallbackQuery):
    cat_key = callback.data.split(":")[1]
    menu = get_menu_from_server()
    
    if cat_key not in menu:
        await callback.answer("Категория не найдена или сервер просыпается", show_alert=True)
        return
        
    cat = menu[cat_key]
    buttons = []
    for item_key, item in cat["items"].items():
        buttons.append([InlineKeyboardButton(text=f"{item['name']} — {item['price']}₽", callback_data=f"item:{cat_key}:{item_key}")])
    
    buttons.append([InlineKeyboardButton(text="🛒 Корзина", callback_data="cart")])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")])
    
    await callback.message.edit_text(f"{cat['name']}\nВыберите позицию:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await callback.answer()

# ... (остальные функции бота: show_item_details, render_coffee_card, show_syrup_menu, set_syrup, toggle_cinnamon, confirm_add, add_item_to_cart, show_cart, delete_from_cart - ОСТАЮТСЯ БЕЗ ИЗМЕНЕНИЙ, кроме checkout)

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
    
    # Отправляем заказ на сервер
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

# ... (main_menu и main остаются без изменений)
