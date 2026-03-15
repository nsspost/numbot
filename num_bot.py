
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
from aiogram.types import (FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton, 
                           CallbackQuery, BotCommand, BotCommandScopeDefault, BotCommandScopeChat)

# Логирование
logging.basicConfig(level=logging.INFO)

# --- КОНФИГУРАЦИЯ ---
TOKEN = '8712709130:AAEkxYNQUcvEKshgU2DpsI35-TBRIKo_kj8'
ADMIN_ID = 1305647823  # ВАШ ID (числом)
DB_FILE = 'bot_database.json'

bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- БАЗА ДАННЫХ ---
async def load_data():
    if not os.path.exists(DB_FILE):
        return {"next_new_num": 1, "users": {}, "history": [], "free_numbers": []}
    try:
        async with aiofiles.open(DB_FILE, mode='r', encoding='utf-8') as f:
            data = json.loads(await f.read())
            return data
    except:
        return {"next_new_num": 1, "users": {}, "history": [], "free_numbers": []}

async def save_data(data):
    async with aiofiles.open(DB_FILE, mode='w', encoding='utf-8') as f:
        await f.write(json.dumps(data, ensure_ascii=False, indent=4))

# --- ЛОГИКА НОМЕРОВ ---
async def assign_num(uid, data):
    if data.get("free_numbers"):
        data["free_numbers"].sort()
        num = data["free_numbers"].pop(0)
    else:
        num = data.get("next_new_num", 1)
        data["next_new_num"] = num + 1
    
    user = data["users"][uid]
    data["history"].append({
        "number": num, 
        "user_id": uid, 
        "real_name": str(user["real_name"]), # Гарантируем строку
        "tg_nick": user["tg_nick"], 
        "date": datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    })
    return num

# --- ОБРАБОТЧИКИ ---

@dp.message(Command("name"))
async def cmd_name(message: types.Message):
    args = message.text.split(maxsplit=1)
    if len(args) > 1:
        data = await load_data()
        # ПРЕВРАЩАЕМ СПИСОК В СТРОКУ (ВАЖНО!)
        full_name = str(args[1])
        data["users"][str(message.from_user.id)] = {
            "real_name": full_name, 
            "tg_nick": f"@{message.from_user.username}" if message.from_user.username else "нет"
        }
        await save_data(data)
        await message.answer(f"✅ Регистрация: {full_name}")
    else:
        await message.answer("Используйте: /name Имя Фамилия")

@dp.message(Command("admin_get"))
async def cmd_admin_get(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    data = await load_data()
    
    if not data.get("users"):
        return await message.answer("База пуста. Никто не нажал /name")

    rows = []
    for uid, info in data["users"].items():
        # Принудительно приводим имя к строке, если там вдруг список
        name = info['real_name']
        if isinstance(name, list):
            name = " ".join(name)
            
        btn_text = f"👤 {name}"
        rows.append([InlineKeyboardButton(text=btn_text, callback_query_data=f"adm_give:{uid}")])
    
    markup = InlineKeyboardMarkup(inline_keyboard=rows)
    await message.answer("🎯 Выберите, кому выдать номер:", reply_markup=markup)

@dp.callback_query(F.data.startswith("adm_give:"))
async def process_adm_give(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    uid = callback.data.split(":")[1]
    data = await load_data()
    
    if uid not in data["users"]:
        return await callback.answer("Пользователь не найден")

    num = await assign_num(uid, data)
    await save_data(data)
    
    await callback.message.edit_text(f"✅ Выдан номер {num} для {data['users'][uid]['real_name']}")
    await callback.answer()
    try: await bot.send_message(uid, f"🎁 Админ выдал вам номер: {num}")
    except: pass

@dp.message(Command("get_num"))
async def cmd_get_num(message: types.Message):
    uid = str(message.from_user.id)
    data = await load_data()
    if uid not in data["users"]: return await message.answer("Сначала /name")
    num = await assign_num(uid, data)
    await save_data(data)
    await message.answer(f"🎉 Ваш номер: {num}")

@dp.message(Command("report"))
async def cmd_report(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    data = await load_data()
    if not data.get("history"): return await message.answer("Пусто.")
    pd.DataFrame(data["history"]).to_excel("report.xlsx", index=False)
    await message.answer_document(FSInputFile("report.xlsx"))

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
