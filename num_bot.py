
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

bot = Bot(token=TOKEN)
dp = Dispatcher()

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

async def assign_num(uid, data):
    if data.get("free_numbers"):
        data["free_numbers"].sort()
        num = data["free_numbers"].pop(0)
    else:
        num = data.get("next_new_num", 1)
        data["next_new_num"] = num + 1
    
    user = data["users"][uid]
    # Принудительно делаем имя строкой для истории
    name_str = " ".join(user["real_name"]) if isinstance(user["real_name"], list) else str(user["real_name"])
    
    data["history"].append({
        "number": num, "user_id": uid, "real_name": name_str,
        "tg_nick": user["tg_nick"], "date": datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    })
    return num

@dp.message(Command("name"))
async def cmd_name(message: types.Message):
    args = message.text.split(maxsplit=1)
    if len(args) > 1:
        data = await load_data()
        # СОХРАНЯЕМ КАК СТРОКУ, А НЕ СПИСОК
        full_name = args[1] 
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
        return await message.answer("База пуста.")

    rows = []
    for uid, info in data["users"].items():
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: преобразуем имя в строку перед созданием кнопки
        raw_name = info.get("real_name", "Без имени")
        clean_name = " ".join(raw_name) if isinstance(raw_name, list) else str(raw_name)
        nick = info.get("tg_nick", "")
        
        button = InlineKeyboardButton(
            text=f"👤 {clean_name} ({nick})", 
            callback_query_data=f"adm:{uid}" # укоротили callback_data
        )
        rows.append([button])
    
    await message.answer("🎯 Кому выдать номер?", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

@dp.callback_query(F.data.startswith("adm:"))
async def process_adm_give(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    target_uid = callback.data.split(":")[1]
    data = await load_data()
    
    if target_uid not in data["users"]:
        return await callback.answer("Ошибка: пользователь удален.")

    num = await assign_num(target_uid, data)
    await save_data(data)
    
    # Снова чистим имя для сообщения
    raw_name = data["users"][target_uid]["real_name"]
    clean_name = " ".join(raw_name) if isinstance(raw_name, list) else str(raw_name)
    
    await callback.message.edit_text(f"✅ Номер {num} выдан для {clean_name}")
    try: await bot.send_message(target_uid, f"🎁 Админ выделил вам номер: {num}")
    except: pass
    await callback.answer()

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
    await bot.set_my_commands([
        BotCommand(command="name", description="Регистрация"),
        BotCommand(command="get_num", description="Получить номер"),
        BotCommand(command="admin_get", description="Выдать другому (Админ)")
    ])
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
