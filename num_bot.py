
# need to install "pip install pandas openpyxl aiogram aiofiles" in Windows/linux console


import asyncio
import json
import os
import logging
import aiofiles
import pandas as pd
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import FSInputFile, InlineKeyboardButton, CallbackQuery, BotCommand, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Логирование
logging.basicConfig(level=logging.INFO)

# --- КОНФИГУРАЦИЯ ---
TOKEN = '8712709130:AAEkxYNQUcvEKshgU2DpsI35-TBRIKo_kj8'
ADMIN_ID = 1305647823  # ВАШ ID (числом)
DB_FILE = 'bot_database.json'

bot = Bot(token=TOKEN)
dp = Dispatcher()

async def load_data():
    if not os.path.exists(DB_FILE):
        return {"next_new_num": 1, "users": {}, "history": [], "free_numbers": []}
    try:
        async with aiofiles.open(DB_FILE, mode='r', encoding='utf-8') as f:
            return json.loads(await f.read())
    except:
        return {"next_new_num": 1, "users": {}, "history": [], "free_numbers": []}

async def save_data(data):
    async with aiofiles.open(DB_FILE, mode='w', encoding='utf-8') as f:
        await f.write(json.dumps(data, ensure_ascii=False, indent=4))

@dp.message(Command("name"))
async def cmd_name(message: types.Message):
    # Берем текст ПОСЛЕ команды /name
    full_name = message.text.replace("/name", "").strip()
    
    if full_name:
        data = await load_data()
        user_id = str(message.from_user.id)
        # Сохраняем строго как строку!
        data["users"][user_id] = {
            "real_name": str(full_name), 
            "tg_nick": f"@{message.from_user.username}" if message.from_user.username else "нет"
        }
        await save_data(data)
        await message.answer(f"✅ Регистрация: {full_name}")
    else:
        await message.answer("Используйте: /name Имя Фамилия")

@dp.message(Command("admin_get"))
async def cmd_admin_get(message: types.Message):
    if message.from_user.id != ADMIN_ID: 
        return
    
    data = await load_data()
    users = data.get("users", {})
    
    if not users:
        return await message.answer("База пользователей пуста.")

    builder = InlineKeyboardBuilder()
    
    for uid, info in users.items():
        # --- ОТЛАДКА ---
        # Печатаем в консоль, чтобы увидеть, нет ли там лишних скобок или списков
        print(f"DEBUG: Processing user {uid}, data: {info}")
        
        # Принудительно чистим имя. Если это список ['Имя'], берем первый элемент.
        raw_name = info.get("real_name", "Без имени")
        if isinstance(raw_name, list):
            name_text = " ".join(map(str, raw_name))
        else:
            name_text = str(raw_name)
            
        # Убираем возможные лишние символы, которые ломают Telegram
        name_text = name_text.replace("[", "").replace("]", "").replace("'", "").strip()
        
        # ВАЖНО: callback_data не должна быть длиннее 64 символов
        cb_data = f"adm:{uid}"
        
        # Добавляем кнопку через Builder
        builder.button(text=f"👤 {name_text}", callback_data=cb_data)

    # Делаем так, чтобы кнопки шли в столбик (по 1 в ряд)
    builder.adjust(1)
    
    try:
        await message.answer(
            "🎯 Выберите пользователя:", 
            reply_markup=builder.as_markup()
        )
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        await message.answer(f"Ошибка при создании меню: {e}")
        
@dp.callback_query(F.data.startswith("adm:"))
async def process_adm_give(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    target_uid = callback.data.split(":")[-1]
    data = await load_data()
    
    if target_uid not in data["users"]:
        return await callback.answer("Ошибка: пользователь не найден.")

    # Логика выдачи номера
    if data.get("free_numbers"):
        data["free_numbers"].sort()
        num = data["free_numbers"].pop(0)
    else:
        num = data.get("next_new_num", 1)
        data["next_new_num"] = num + 1
    
    user = data["users"][target_uid]
    name_str = " ".join(user["real_name"]) if isinstance(user["real_name"], list) else str(user["real_name"])
    
    data["history"].append({
        "number": num, "user_id": target_uid, "real_name": name_str,
        "tg_nick": user.get("tg_nick", ""), "date": datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    })
    
    await save_data(data)
    await callback.message.edit_text(f"✅ Выдан номер {num} для {name_str}")
    try: await bot.send_message(target_uid, f"🎁 Админ выдал вам номер: {num}")
    except: pass
    await callback.answer()

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
