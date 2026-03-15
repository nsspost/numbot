
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
            # Проверка ключей
            for k in ["next_new_num", "users", "history", "free_numbers"]:
                if k not in data: data[k] = [] if "history" in k or "free" in k else ({} if "users" in k else 1)
            return data
    except:
        return {"next_new_num": 1, "users": {}, "history": [], "free_numbers": []}

async def save_data(data):
    async with aiofiles.open(DB_FILE, mode='w', encoding='utf-8') as f:
        await f.write(json.dumps(data, ensure_ascii=False, indent=4))

# --- ЛОГИКА НОМЕРОВ ---
async def assign_num(uid, data):
    if data["free_numbers"]:
        data["free_numbers"].sort()
        num = data["free_numbers"].pop(0)
    else:
        num = data["next_new_num"]
        data["next_new_num"] += 1
    
    user = data["users"][uid]
    data["history"].append({
        "number": num, "user_id": uid, "real_name": user["real_name"],
        "tg_nick": user["tg_nick"], "date": datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    })
    data["history"].sort(key=lambda x: x["number"])
    return num

# --- ОБРАБОТЧИКИ ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("Зарегистрируйтесь: /name Имя Фамилия\nЗатем: /get_num")

@dp.message(Command("name"))
async def cmd_name(message: types.Message):
    args = message.text.split(maxsplit=1)
    if len(args) > 1:
        data = await load_data()
        data["users"][str(message.from_user.id)] = {
            "real_name": args[1], 
            "tg_nick": f"@{message.from_user.username}" if message.from_user.username else "нет"
        }
        await save_data(data)
        await message.answer(f"✅ Регистрация: {args[1]}")
    else:
        await message.answer("Используйте: /name Имя Фамилия")

@dp.message(Command("admin_get"))
async def cmd_admin_get(message: types.Message):
    if message.from_user.id != ADMIN_ID: 
        return
    
    data = await load_data()
    if not data.get("users"):
        return await message.answer("База пользователей пуста. Никто еще не нажал /name")

    # Создаем список кнопок правильно
    keyboard_rows = []
    for uid, info in data["users"].items():
        user_name = info.get("real_name", "Без имени")
        user_nick = info.get("tg_nick", "нет")
        
        # Создаем ОБЪЕКТ кнопки
        button = InlineKeyboardButton(
            text=f"👤 {user_name} ({user_nick})", 
            callback_query_data=f"adm_give:{uid}"
        )
        # Добавляем кнопку как отдельную строку (список из одного элемента)
        keyboard_rows.append([button])
    
    # Собираем клавиатуру из списка строк
    markup = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    
    await message.answer("🎯 Выберите, кому выдать номер:", reply_markup=markup)

@dp.callback_query(F.data.startswith("adm_give:"))
async def process_adm_give(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID: 
        return
        
    # Извлекаем ID пользователя из callback_data
    target_uid = callback.data.split(":")[1]
    data = await load_data()
    
    if target_uid not in data["users"]:
        return await callback.answer("Пользователь не найден")

    num = await assign_num(target_uid, data)
    await save_data(data)
    
    user_name = data["users"][target_uid]["real_name"]
    await callback.message.edit_text(f"✅ Выдан номер {num} для {user_name}")
    
    try:
        await bot.send_message(target_uid, f"🎁 Администратор выдал вам номер: {num}")
    except:
        pass
    
    await callback.answer() # Закрываем "часики" на кнопке

@dp.message(Command("get_num"))
async def cmd_get_num(message: types.Message):
    uid = str(message.from_user.id)
    data = await load_data()
    if uid not in data["users"]: return await message.answer("Сначала /name")
    num = await assign_num(uid, data)
    await save_data(data)
    await message.answer(f"🎉 Ваш номер: {num}")

@dp.message(Command("my_nums"))
async def cmd_my_nums(message: types.Message):
    data = await load_data()
    uid = str(message.from_user.id)
    nums = [str(r["number"]) for r in data["history"] if r["user_id"] == uid]
    await message.answer(f"Ваши номера: {', '.join(nums)}" if nums else "Номеров нет.")

@dp.message(Command("report"))
async def cmd_report(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    data = await load_data()
    if not data["history"]: return await message.answer("Пусто.")
    pd.DataFrame(data["history"]).to_excel("report.xlsx", index=False)
    await message.answer_document(FSInputFile("report.xlsx"))

@dp.message(Command("del_num"))
async def cmd_del_num(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    args = message.text.split()
    if len(args) < 2: return
    target = int(args[1])
    data = await load_data()
    
    orig_len = len(data["history"])
    data["history"] = [r for r in data["history"] if r["number"] != target]
    if len(data["history"]) < orig_len:
        data["free_numbers"].append(target)
        await save_data(data)
        await message.answer(f"🗑 Номер {target} удален.")
    else:
        await message.answer("Номер не найден.")

async def main():
    await bot.set_my_commands([
        BotCommand(command="start", description="Старт"),
        BotCommand(command="name", description="Регистрация"),
        BotCommand(command="get_num", description="Получить номер"),
        BotCommand(command="my_nums", description="Мои номера"),
        BotCommand(command="admin_get", description="Выдать другому (Админ)")
    ])
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

if __name__ == "__main__":
    asyncio.run(main())
