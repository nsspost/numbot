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
from aiogram.types import FSInputFile

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# --- НАСТРОЙКИ ---
TOKEN = '8589045432:AAE5q28wXEtewrgEUjZp2TcGO2LGqec5n3A'
ADMIN_ID = 1292069307  # ЗАМЕНИТЕ на ваш числовой ID
# ВНИМАНИЕ!!! НАДО ВЫБРАТЬ ДЛЯ ОТЛАДКИ ИЛИ ДЛЯ СЕРВЕРА ПУТЬ К ФАЙЛУ БАЗЫ ДАННЫХ
#DB_FILE = 'bot_database.json' # для локальных тестов
DB_FILE = '/data/bot_database.json' # для сервера
 
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- РАБОТА С БАЗОЙ ДАННЫХ ---
async def load_data():
    if not os.path.exists(DB_FILE):
        return {"counter": 0, "users": {}, "history": []}
    try:
        async with aiofiles.open(DB_FILE, mode='r', encoding='utf-8') as f:
            content = await f.read()
            data = json.loads(content)
            data.setdefault("counter", 0)
            data.setdefault("users", {})
            data.setdefault("history", [])
            return data
    except Exception as e:
        logging.error(f"Ошибка чтения базы: {e}")
        return {"counter": 0, "users": {}}

async def save_data(data):
    async with aiofiles.open(DB_FILE, mode='w', encoding='utf-8') as f:
        await f.write(json.dumps(data, ensure_ascii=False, indent=4))

# --- ОБРАБОТЧИКИ (ВАЖЕН ПОРЯДОК) ---

# 1. Команда СТАРТ (доступна всем)
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 Привет! Я бот для регистрации и выдачи номеров.\n\n"
        "Чтобы начать, обязательно зарегистрируйтесь:\n"
        "👉 /name Имя Фамилия\n\n"
        "После этого вы сможете получать номера командой /get_num"
    )

# 2. Команда РЕГИСТРАЦИИ (доступна всем)
@dp.message(Command("name"))
async def set_name(message: types.Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) > 1:
        full_name = parts[1]
        user_id = str(message.from_user.id)
        username = f"@{message.from_user.username}" if message.from_user.username else "нет ника"
        
        data = await load_data()
        data["users"][user_id] = {
            "real_name": full_name,
            "tg_nick": username
        }
        await save_data(data)
        await message.reply(f"✅ Регистрация успешна! Теперь вы можете получить номер: /get_num")
    else:
        await message.reply("⚠️ Ошибка! Напишите: /name Имя Фамилия")

# 3. ПРОВЕРКА РЕГИСТРАЦИИ (Блокирует всё остальное для незнакомцев)
@dp.message(lambda message: True) # Ловим любое сообщение
async def check_registration(message: types.Message):
    user_id = str(message.from_user.id)
    data = await load_data()
    
    # Если пользователь уже в базе — пропускаем его к следующим командам
    if user_id in data["users"]:
        # Если это была команда, которую мы знаем, позволяем ей сработать
        if message.text.startswith('/get_num'):
            return await get_number(message)
        elif message.text.startswith('/report'):
            return await send_report(message)
        elif message.text.startswith('/reset_numbers'):
            return await reset_numbers(message)
        else:
            await message.answer("Команда не распознана. Используйте /get_num для получения номера.")
            return

    # Если пользователя НЕТ в базе — выводим справку
    await message.answer(
        "❌ Вы не зарегистрированы в системе!\n\n"
        "Пожалуйста, введите ваше имя командой:\n"
        "👉 /name Имя Фамилия\n\n"
        "Без этого функции получения номеров недоступны."
    )

# 4. Функциональные команды (вызываются из обработчика выше)

async def get_number(message: types.Message):
    user_id = str(message.from_user.id)
    data = await load_data()
    user_info = data["users"][user_id]

    data["counter"] += 1
    new_num = data["counter"]
    now = datetime.now()
    
    record = {
        "Номер": new_num,
        "Дата": now.strftime("%d.%m.%Y"),
        "Время": now.strftime("%H:%M:%S"),
        "Имя Фамилия": user_info["real_name"],
        "Ник": user_info["tg_nick"],
        "User ID": user_id
    }
    data["history"].append(record)
    await save_data(data)
    
    await message.answer(f"🎉 Ваш номер: {new_num}\n👤 Владелец: {user_info['real_name']}\n📅 Дата: {record['Дата']} {record['Время']}")

async def send_report(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Доступ только для администратора.")
        return

    data = await load_data()
    if not data["history"]:
        await message.answer("📭 История пуста.")
        return

    file_path = "report.xlsx"
    df = pd.DataFrame(data["history"])
    df.to_excel(file_path, index=False)
    
    await message.answer_document(FSInputFile(file_path), caption="📊 Отчет по выданным номерам")
    if os.path.exists(file_path): os.remove(file_path)

async def reset_numbers(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Доступ только для администратора.")
        return

    data = await load_data()
    data["counter"] = 0
    data["history"] = []
    await save_data(data)
    await message.answer("🔄 История и счетчик сброшены. Имена пользователей сохранены.")

# --- ЗАПУСК ---
async def main():
    print("Бот запущен и готов к работе!")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Бот остановлен")
