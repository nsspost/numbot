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

# --- СИСТЕМНЫЕ ФУНКЦИИ ---
async def load_data():
    if not os.path.exists(DB_FILE):
        return {"next_new_num": 1, "users": {}, "history": [], "free_numbers": []}
    try:
        async with aiofiles.open(DB_FILE, mode='r', encoding='utf-8') as f:
            data = json.loads(await f.read())
            for key in ["next_new_num", "users", "history", "free_numbers"]:
                data.setdefault(key, [] if "history" in key or "free" in key else ({} if "users" in key else 1))
            return data
    except:
        return {"next_new_num": 1, "users": {}, "history": [], "free_numbers": []}

async def save_data(data):
    async with aiofiles.open(DB_FILE, mode='w', encoding='utf-8') as f:
        await f.write(json.dumps(data, ensure_ascii=False, indent=4))

async def assign_num_logic(target_uid, data):
    """Выбор номера: из свободных или следующий новый"""
    if data["free_numbers"]:
        data["free_numbers"].sort()
        assigned_num = data["free_numbers"].pop(0)
    else:
        assigned_num = data["next_new_num"]
        data["next_new_num"] += 1

    user_info = data["users"][target_uid]
    now = datetime.now()
    record = {
        "number": assigned_num,
        "user_id": target_uid,
        "real_name": user_info["real_name"],
        "tg_nick": user_info["tg_nick"],
        "date": now.strftime("%d.%m.%Y"),
        "time": now.strftime("%H:%M:%S")
    }
    data["history"].append(record)
    data["history"].sort(key=lambda x: x["number"])
    return assigned_num

# --- НАСТРОЙКА МЕНЮ КОМАНД (ПОДСКАЗКИ) ---
async def set_main_menu(bot: Bot):
    # Общие команды
    user_commands = [
        BotCommand(command="start", description="Запустить бота"),
        BotCommand(command="name", description="Регистрация (Имя Фамилия)"),
        BotCommand(command="get_num", description="Получить номер"),
        BotCommand(command="my_nums", description="Мои номера"),
    ]
    await bot.set_my_commands(commands=user_commands, scope=BotCommandScopeDefault())
    
    # Команды только для админа
    admin_commands = user_commands + [
        BotCommand(command="admin_get", description="👑 Выдать номер другому"),
        BotCommand(command="report", description="📊 Отчет Excel"),
        BotCommand(command="del_num", description="🗑 Удалить номер [№]"),
        BotCommand(command="reset_numbers", description="🔄 Сброс базы")
    ]
    await bot.set_my_commands(commands=admin_commands, scope=BotCommandScopeChat(chat_id=ADMIN_ID))

# --- ОБРАБОТЧИКИ ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("👋 Используйте меню команд или введите /name Имя Фамилия")

@dp.message(Command("name"))
async def set_name(message: types.Message):
    args = message.text.split(maxsplit=1)
    if len(args) > 1:
        data = await load_data()
        data["users"][str(message.from_user.id)] = {
            "real_name": args[1], 
            "tg_nick": f"@{message.from_user.username}" if message.from_user.username else "нет"
        }
        await save_data(data)
        await message.reply(f"✅ Регистрация: {args[1]}")
    else:
        await message.reply("⚠️ Напишите: /name Имя Фамилия")

@dp.message(Command("get_num"))
async def get_num_self(message: types.Message):
    uid = str(message.from_user.id)
    data = await load_data()
    if uid not in data["users"]: return await message.answer("Сначала /name")
    
    num = await assign_num_logic(uid, data)
    await save_data(data)
    await message.answer(f"🎉 Ваш номер: {num}")

@dp.message(Command("my_nums"))
async def my_nums(message: types.Message):
    data = await load_data()
    uid = str(message.from_user.id)
    nums = [str(r["number"]) for r in data["history"] if r["user_id"] == uid]
    await message.answer(f"📋 Ваши номера: {', '.join(nums)}" if nums else "У вас нет номеров.")

# --- АДМИН-ПАНЕЛЬ ---

@dp.message(Command("admin_get"))
async def admin_get_menu(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    data = await load_data()
    if not data["users"]: return await message.answer("База пуста.")

    keyboard = []
    for uid, info in data["users"].items():
        # Добавляем ник в текст кнопки для удобства
        text = f"{info['real_name']} ({info['tg_nick']})"
        keyboard.append([InlineKeyboardButton(text=text, callback_query_data=f"give_to_{uid}")])
    
    await message.answer("🎯 Кому выдать номер?", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))

@dp.callback_query(F.data.startswith("give_to_"))
async def process_admin_give(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    target_uid = callback.data.split("_")[-1]
    data = await load_data()
    
    num = await assign_num_logic(target_uid, data)
    await save_data(data)
    
    await callback.message.edit_text(f"✅ Номер {num} выдан пользователю {data['users'][target_uid]['real_name']}")
    try:
        await bot.send_message(target_uid, f"🎁 Администратор выдал вам номер: {num}")
    except: pass

@dp.message(Command("report"))
async def report(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    data = await load_data()
    if not data["history"]: return await message.answer("Пусто.")
    pd.DataFrame(data["history"]).to_excel("report.xlsx", index=False)
    await message.answer_document(FSInputFile("report.xlsx"))

@dp.message(Command("del_num"))
async def del_num(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    args = message.text.split()
    if len(args) < 2 or not args[1].isdigit(): return await message.answer("Пример: /del_num 5")
    
    target = int(args[1])
    data = await load_data()
    found = False
    for i, rec in enumerate(data["history"]):
        if rec["number"] == target:
            data["free_numbers"].append(target)
            data["history"].pop(i)
            found = True
            break
    if found:
        await save_data(data)
        await message.answer(f"🗑 Номер {target} удален.")

@dp.message(Command("reset_numbers"))
async def reset(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    data = await load_data()
    data.update({"next_new_num": 1, "history": [], "free_numbers": []})
    await save_data(data)
    await message.answer("🔄 Все номера сброшены.")

async def main():
    await set_main_menu(bot)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
