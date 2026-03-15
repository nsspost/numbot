
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
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Логирование
logging.basicConfig(level=logging.INFO)

# --- КОНФИГУРАЦИЯ ---
TOKEN = '8712709130:AAEkxYNQUcvEKshgU2DpsI35-TBRIKo_kj8'
ADMIN_ID = 1305647823  # ВАШ ID (числом)
DB_FILE = '/app/data/bot_database.json'

bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- РАБОТА С БАЗОЙ ДАННЫХ ---
async def load_data():
    if not os.path.exists(DB_FILE):
        return {"next_new_num": 1, "users": {}, "history": [], "free_numbers": []}
    try:
        async with aiofiles.open(DB_FILE, mode='r', encoding='utf-8') as f:
            content = await f.read()
            data = json.loads(content)
            # Гарантируем наличие всех ключей
            data.setdefault("next_new_num", 1)
            data.setdefault("users", {})
            data.setdefault("history", [])
            data.setdefault("free_numbers", [])
            return data
    except:
        return {"next_new_num": 1, "users": {}, "history": [], "free_numbers": []}

async def save_data(data):
    async with aiofiles.open(DB_FILE, mode='w', encoding='utf-8') as f:
        await f.write(json.dumps(data, ensure_ascii=False, indent=4))

# --- ЛОГИКА ВЫДАЧИ НОМЕРА ---
async def assign_num_to_user(target_uid, data):
    """Общая функция: берет свободный номер или создает новый"""
    if data["free_numbers"]:
        data["free_numbers"].sort()
        assigned_num = data["free_numbers"].pop(0)
    else:
        assigned_num = data["next_new_num"]
        data["next_new_num"] += 1

    user_info = data["users"][target_uid]
    # Очищаем имя от возможных списков/скобок для истории
    raw_name = user_info["real_name"]
    clean_name = " ".join(raw_name) if isinstance(raw_name, list) else str(raw_name)
    clean_name = clean_name.replace("[", "").replace("]", "").replace("'", "").strip()

    now = datetime.now()
    record = {
        "number": assigned_num,
        "user_id": target_uid,
        "real_name": clean_name,
        "tg_nick": user_info.get("tg_nick", "нет"),
        "date": now.strftime("%d.%m.%Y"),
        "time": now.strftime("%H:%M:%S")
    }
    data["history"].append(record)
    data["history"].sort(key=lambda x: x["number"])
    return assigned_num

# --- ОБРАБОТЧИКИ ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 Бот для выдачи номеров.\n\n"
        "1️⃣ /name Имя Фамилия — регистрация\n"
        "2️⃣ /get_num — получить номер\n"
        "3️⃣ /my_nums — посмотреть свои номера\n"
        "🆘 /help — все команды"
    )

@dp.message(Command("name"))
async def cmd_name(message: types.Message):
    # Берем текст после команды /name
    full_name = message.text.replace("/name", "").strip()
    
    if full_name:
        data = await load_data()
        user_id = str(message.from_user.id)
        data["users"][user_id] = {
            "real_name": full_name, 
            "tg_nick": f"@{message.from_user.username}" if message.from_user.username else "нет"
        }
        await save_data(data)
        await message.answer(f"✅ Регистрация успешна: {full_name}")
    else:
        await message.answer("⚠️ Напишите: /name Ваше Имя и Фамилия")

# --- КОМАНДЫ ПОЛЬЗОВАТЕЛЯ ---

@dp.message(Command("get_num"))  # Добавлена эта строка!
async def get_num_self(message: types.Message):
    uid = str(message.from_user.id)
    data = await load_data()
    
    if uid not in data["users"]:
        return await message.answer("❌ Сначала зарегистрируйтесь: /name Имя Фамилия")

    num = await assign_num_to_user(uid, data)
    await save_data(data)
    await message.answer(f"🎉 Ваш номер: {num}")

@dp.message(Command("my_nums"))  # Добавлена эта строка!
async def cmd_my_nums(message: types.Message):
    data = await load_data()
    uid = str(message.from_user.id)
    user_nums = [str(r["number"]) for r in data["history"] if r["user_id"] == uid]
    
    if user_nums:
        await message.answer(f"📋 Ваши активные номера: {', '.join(user_nums)}")
    else:
        await message.answer("🤷‍♂️ У вас пока нет ни одного номера.")

# --- АДМИН-ФУНКЦИИ ---

@dp.message(Command("admin_get"))
async def cmd_admin_get(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    data = await load_data()
    
    if not data["users"]:
        return await message.answer("База пуста. Никто не нажал /name")

    builder = InlineKeyboardBuilder()
    for uid, info in data["users"].items():
        raw_name = info.get("real_name", "Без имени")
        clean_name = " ".join(raw_name) if isinstance(raw_name, list) else str(raw_name)
        clean_name = clean_name.replace("[", "").replace("]", "").replace("'", "").strip()
        
        builder.button(
            text=f"👤 {clean_name} ({info.get('tg_nick', '')})", 
            callback_data=f"adm:{uid}"
        )
    
    builder.adjust(1)
    await message.answer("🎯 Кому выдать номер?", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("adm:"))
async def process_adm_give(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    target_uid = callback.data.split(":")[-1]
    data = await load_data()
    
    if target_uid not in data["users"]:
        return await callback.answer("Ошибка: пользователь не найден.")

    num = await assign_num_to_user(target_uid, data)
    await save_data(data)
    
    await callback.message.edit_text(f"✅ Номер {num} выдан пользователю {data['users'][target_uid]['real_name']}")
    try:
        await bot.send_message(target_uid, f"🎁 Администратор выдал вам новый номер: {num}")
    except: pass
    await callback.answer()

@dp.message(Command("report"))
async def cmd_report(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    data = await load_data()
    if not data["history"]:
        return await message.answer("История выдач пока пуста.")
    
    df = pd.DataFrame(data["history"])
    df.columns = ["№", "ID", "Имя", "Ник", "Дата", "Время"]
    file_path = "report.xlsx"
    df.to_excel(file_path, index=False)
    
    await message.answer_document(FSInputFile(file_path), caption="📊 Отчет по выданным номерам")
    if os.path.exists(file_path): os.remove(file_path)

@dp.message(Command("del_num"))
async def cmd_del_num(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    args = message.text.split()
    if len(args) < 2 or not args[1].isdigit():
        return await message.answer("⚠️ Пример: /del_num 5")
    
    target = int(args[1])
    data = await load_data()
    
    found = False
    new_history = []
    for rec in data["history"]:
        if rec["number"] == target:
            found = True
            if target not in data["free_numbers"]:
                data["free_numbers"].append(target)
        else:
            new_history.append(rec)
            
    if found:
        data["history"] = new_history
        await save_data(data)
        await message.answer(f"🗑 Номер {target} удален и возвращен в очередь.")
    else:
        await message.answer(f"❌ Номер {target} не найден в списке выданных.")

# --- КОМАНДА ПОМОЩИ ---
@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    is_admin = message.from_user.id == ADMIN_ID
    
    help_text = (
        "📖 **Доступные команды:**\n\n"
        "👤 **Для пользователей:**\n"
        "/name Имя Фамилия — регистрация в системе\n"
        "/get_num — получить свободный номер\n"
        "/my_nums — список ваших номеров\n"
    )
    
    if is_admin:
        help_text += (
            "\n👑 **Для администратора:**\n"
            "/admin_get — выдать номер пользователю из меню\n"
            "/report — выгрузить отчет в Excel\n"
            "/del_num [№] — удалить номер и вернуть в очередь\n"
            "/reset_numbers — полный сброс истории"
        )
    
    # Отправляем без Markdown, если в именах есть спецсимволы, чтобы бот не падал
    await message.answer(help_text)

# --- ЗАПУСК БОТА ---
async def main():
    # Создаем папку для Bothost, если её нет
    if not os.path.exists('/app/data'):
        try:
            os.makedirs('/app/data', exist_ok=True)
        except:
            pass

    # Устанавливаем подсказки в меню Telegram
    await bot.set_my_commands([
        types.BotCommand(command="name", description="Регистрация (Имя Фамилия)"),
        types.BotCommand(command="get_num", description="Получить номер"),
        types.BotCommand(command="my_nums", description="Мои номера"),
        types.BotCommand(command="help", description="Справка по командам")
    ])
    
    print(f"Бот запущен. База данных: {DB_FILE}")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Бот остановлен")
