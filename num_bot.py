
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
from aiogram.types import FSInputFile, InlineKeyboardButton, CallbackQuery, BotCommand
from aiogram.utils.keyboard import InlineKeyboardBuilder # Специальный строитель

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
    # Гарантируем, что имя - строка
    raw_name = user.get("real_name", "Без имени")
    name_str = " ".join(raw_name) if isinstance(raw_name, list) else str(raw_name)
    
    data["history"].append({
        "number": num, "user_id": uid, "real_name": name_str,
        "tg_nick": user.get("tg_nick", ""), "date": datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    })
    return num

# --- ОБРАБОТЧИКИ ---

@dp.message(Command("name"))
async def cmd_name(message: types.Message):
    args = message.text.split(maxsplit=1)
    if len(args) > 1:
        data = await load_data()
        # СРАЗУ СОХРАНЯЕМ КАК ЧИСТУЮ СТРОКУ
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
    
    users = data.get("users", {})
    if not users:
        return await message.answer("База пользователей пуста.")

    # Используем Builder - это исключает ошибку типов кнопок
    builder = InlineKeyboardBuilder()
    
    for uid, info in users.items():
        raw_name = info.get("real_name", "Без имени")
        # Если в базе лежит список (старые данные), склеиваем в строку
        clean_name = " ".join(raw_name) if isinstance(raw_name, list) else str(raw_name)
        nick = info.get("tg_nick", "")
        
        # Добавляем кнопку в билдер
        builder.row(InlineKeyboardButton(
            text=f"👤 {clean_name} ({nick})", 
            callback_query_data=f"adm:{uid}")
        )
    
    await message.answer(
        "🎯 Выберите, кому выдать номер:", 
        reply_markup=builder.as_markup()
    )

@dp.callback_query(F.data.startswith("adm:"))
async def process_adm_give(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    target_uid = callback.data.split(":")[1]
    data = await load_data()
    
    if target_uid not in data["users"]:
        return await callback.answer("Ошибка: пользователь не найден.")

    num = await assign_num(target_uid, data)
    await save_data(data)
    
    raw_name = data["users"][target_uid]["real_name"]
    clean_name = " ".join(raw_name) if isinstance(raw_name, list) else str(raw_name)
    
    await callback.message.edit_text(f"✅ Номер {num} выдан для {clean_name}")
    try: await bot.send_message(target_uid, f"🎁 Админ выдал вам номер: {num}")
    except: pass
    await callback.answer()

@dp.message(Command("report"))
async def cmd_report(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    data = await load_data()
    if not data.get("history"): return await message.answer("Пусто.")
    pd.DataFrame(data["history"]).to_excel("report.xlsx", index=False)
    await message.answer_document(FSInputFile("report.xlsx"))

async def main():
    # Удаляем старые команды и ставим новые подсказки
    await bot.set_my_commands([
        BotCommand(command="name", description="Регистрация"),
        BotCommand(command="get_num", description="Получить номер"),
        BotCommand(command="admin_get", description="Выдать другому (Админ)")
    ])
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
