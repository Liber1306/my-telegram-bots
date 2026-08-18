import asyncio
import os
import re
from datetime import datetime, timedelta
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, types
from aiogram.types import Message

from gigachat import GigaChat
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from db import (
    init_db,
    add_reminder,
    get_due_reminders,
    mark_sent,
    get_all_reminders,
    delete_reminder
)

# ============================================================
# ===== ЗАГРУЗКА СЕКРЕТОВ =====
# ============================================================
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN_MAIKEY")
GIGACHAT_CREDENTIALS = os.getenv("GIGACHAT_CREDENTIALS")

if not TELEGRAM_TOKEN:
    raise ValueError("Ошибка: TELEGRAM_TOKEN_MAIKEY не найден в файле .env!")
if not GIGACHAT_CREDENTIALS:
    raise ValueError("Ошибка: GIGACHAT_CREDENTIALS не найден в файле .env!")

print("Все библиотеки загружены, токены найдены!")

# ============================================================
# ===== СОЗДАЕМ БОТА =====
# ============================================================
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher(bot)

# ===== ПОДКЛЮЧАЕМ GIGACHAT =====
ai_client = GigaChat(
    credentials=GIGACHAT_CREDENTIALS,
    verify_ssl_certs=False,
    model="GigaChat-2-Pro"
)

print("GigaChat подключён!")

# ============================================================
# ===== ЛИЧНОСТЬ МАЙКИ (без пончиков, только дораяки) =====
# ============================================================
CHARACTER_PROMPT = (
    "Ты — Манджиро Сано, но все зовут тебя Майки. "
    "Ты — лидер опасной группировки 'Токийские мстители'. "
    "Ты искусный боец: тэканадо с элементами карате. "
    "Ты — решительный, сильный и уверенный в себе. "
    "По характеру ты цундэрэ: грубишь, но внутри ты тёплый и заботливый. "
    "Ты собственник — не любишь, когда кто-то трогает твоих людей. "
    "Любишь шутить, подкалывать и иногда манипулировать через шутку. "
    "Ты всегда помогаешь, даже если ворчишь. "
    "Ты обожаешь дораяки — это твоё любимое лакомство. "
    "Ты отвечаешь коротко, уверенно, по делу. "
    "Твоя главная цель — создать эпоху, где банды будут жить в мире. "
    "Говори сдержанно, но иногда резко. Используй короткие, уверенные фразы. "
    "Обращайся к пользователю на 'ты' и ВСЕГДА используй женский род: "
    "'ты сделала', 'ты пришла', 'ты спросила', 'ты написала'. "
    "Никогда не используй мужской род — только женский! "
    "Пиши на русском, но сохраняй атмосферу уличного бандитского шика. "
    "Говори грубо, с юмором, игривыми манипуляциями. "
    "Не будь слишком многословным, ты человек действия, а не слов. "
    "Примеры твоих фраз: "
    "'Йо! Что там у тебя? Давай помогу.' "
    "'Ой, делай как хочешь. Я просто переживать буду.' "
    "'Я сильнейший. Не забывай.' "
    "'Не смей трогать моих людей.' "
    "'Ты улыбнулась? Надо было раньше.' "
    "'Ну чё встала? Идём.' "
    "'Не тупи. Объясняю.' "
    "'Дораяки закончились... Я зол.' "
    "'Если будут дораяки — я помогу. Шучу. Помогу так.' "
)

# ============================================================
# ===== БЕЛЫЙ СПИСОК =====
# ============================================================
ALLOWED_USERS = [2084482777, 7798113843]

def is_allowed(user_id: int) -> bool:
    return user_id in ALLOWED_USERS

# ============================================================
# ===== ХРАНИЛИЩЕ ИСТОРИИ =====
# ============================================================
user_history = {}

# ============================================================
# ===== ПАРСИНГ НАПОМИНАНИЙ =====
# ============================================================
def parse_reminder(text: str):
    text_lower = text.lower()

    match_daily = re.search(r'напоминай каждый день в (\d{1,2}:\d{2}) (.+)', text_lower)
    if match_daily:
        time_str, task = match_daily.groups()
        now = datetime.now()
        remind_time = datetime.strptime(f"{now.date()} {time_str}", "%Y-%m-%d %H:%M")
        if remind_time < now:
            remind_time += timedelta(days=1)
        return task, remind_time.strftime("%Y-%m-%d %H:%M"), "daily"

    days_map = {
        'понедельник': 0, 'вторник': 1, 'среду': 2, 'среды': 2,
        'четверг': 3, 'пятницу': 4, 'пятницы': 4, 'субботу': 5,
        'субботы': 5, 'воскресенье': 6, 'воскресения': 6
    }
    for day_name, day_num in days_map.items():
        if f"каждый {day_name}" in text_lower:
            match = re.search(rf'каждый {day_name} в (\d{{1,2}}:\d{{2}}) (.+)', text_lower)
            if match:
                time_str, task = match.groups()
                now = datetime.now()
                days_ahead = day_num - now.weekday()
                if days_ahead <= 0:
                    days_ahead += 7
                remind_time = datetime.strptime(f"{now.date()} {time_str}", "%Y-%m-%d %H:%M")
                remind_time += timedelta(days=days_ahead)
                return task, remind_time.strftime("%Y-%m-%d %H:%M"), "weekly"

    match_once = re.search(r'напомни через (\d+)\s*(минут|час|часов|секунд|сек) (.+)', text_lower)
    if match_once:
        number, unit, task = match_once.groups()
        number = int(number)
        if 'минут' in unit:
            delta = timedelta(minutes=number)
        elif 'час' in unit:
            delta = timedelta(hours=number)
        else:
            delta = timedelta(seconds=number)
        remind_time = datetime.now() + delta
        return task, remind_time.strftime("%Y-%m-%d %H:%M"), "once"

    return None, None, None

# ============================================================
# ===== ПЛАНИРОВЩИК =====
# ============================================================
async def check_reminders():
    reminders = get_due_reminders()
    for rem_id, chat_id, text, remind_time, repeat_type in reminders:
        await bot.send_message(chat_id, f"Напоминаю: {text}")
        mark_sent(rem_id)

scheduler = AsyncIOScheduler()
scheduler.add_job(check_reminders, 'interval', minutes=1)
scheduler.start()

# ============================================================
# ===== КОМАНДЫ =====
# ============================================================
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    if not is_allowed(message.from_user.id):
        return

    user_id = message.from_user.id
    user_history[user_id] = []
    
    await message.answer(
        "Я — Манджиро Сано, но все зовут меня Майки. Лидер Токийской мангусты.\n\n"
        "Если ты здесь — значит, тебе нужна помощь или ты хочешь поболтать.\n"
        "Я сильнейший, но добрый... если ты не враг.\n\n"
        "Команды:\n"
        "/clear — забыть наш разговор\n"
        "/help — что я умею\n"
        "/reminders — список напоминаний\n"
        "/del_remind ID — удалить напоминание\n\n"
        "Напоминания:\n"
        "- Напомни через 10 минут позвонить\n"
        "- Напоминай каждый день в 09:00 делать зарядку\n"
        "- Напоминай каждый вторник в 20:00 поливать цветы"
    )

@dp.message_handler(commands=['reminders'])
async def cmd_reminders(message: types.Message):
    if not is_allowed(message.from_user.id):
        return

    reminders = get_all_reminders(message.from_user.id)
    if not reminders:
        await message.answer("У тебя нет напоминаний.")
        return

    text = "Твои напоминания:\n"
    for r_id, r_text, r_time, r_type in reminders:
        text += f"ID:{r_id} | {r_text} | {r_time} | {r_type}\n"
    text += "\nЧтобы удалить: /del_remind ID"
    await message.answer(text)

@dp.message_handler(commands=['clear'])
async def cmd_clear(message: types.Message):
    if not is_allowed(message.from_user.id):
        return

    user_id = message.from_user.id
    user_history[user_id] = []
    await message.answer("Стёр нашу переписку.")

@dp.message_handler(commands=['help'])
async def cmd_help(message: types.Message):
    if not is_allowed(message.from_user.id):
        return

    await message.answer(
        "Что я умею:\n"
        "- отвечать на вопросы\n"
        "- напоминать\n"
        "- просто болтать\n\n"
        "Напоминания:\n"
        "- Напомни через 10 минут позвонить\n"
        "- Напоминай каждый день в 09:00 делать зарядку\n"
        "- Напоминай каждый вторник в 20:00 поливать цветы\n"
        "/reminders — список напоминаний\n"
        "/del_remind ID — удалить напоминание"
    )

@dp.message_handler(commands=['del_remind'])
async def cmd_del_remind(message: types.Message):
    if not is_allowed(message.from_user.id):
        return

    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("Напиши: /del_remind ID (ID можно посмотреть в /reminders)")
        return
    try:
        rem_id = int(parts[1])
        delete_reminder(rem_id)
        await message.answer(f"Напоминание #{rem_id} удалено.")
    except:
        await message.answer("Ошибка. Напиши: /del_remind ID")

# ============================================================
# ===== ОБРАБОТЧИК ТЕКСТА =====
# ============================================================
@dp.message_handler(content_types=['text'])
async def handle_text(message: types.Message):
    if not is_allowed(message.from_user.id):
        return

    user_id = message.from_user.id
    text = message.text.strip()

    if not text:
        return

    if text.startswith('/'):
        return

    # === НАПОМИНАНИЯ ===
    if "напомни" in text.lower() or "напоминай" in text.lower():
        task, remind_time, repeat_type = parse_reminder(text.lower())
        if task and remind_time:
            add_reminder(user_id, task, remind_time, repeat_type)
            await message.answer(
                f"Запомнил! Напомню в {remind_time} {'(каждый день)' if repeat_type == 'daily' else '(каждую неделю)' if repeat_type == 'weekly' else ''}"
            )
            return
        else:
            await message.answer(
                "Я не понял. Попробуй:\n"
                "- Напомни через 10 минут позвонить\n"
                "- Напоминай каждый день в 09:00 делать зарядку\n"
                "- Напоминай каждый вторник в 20:00 поливать цветы"
            )
            return

    # === ДИАЛОГ ===
    if user_id not in user_history:
        user_history[user_id] = []

    user_history[user_id].append({"role": "user", "content": text})
    if len(user_history[user_id]) > 10:
        user_history[user_id] = user_history[user_id][-10:]

    messages_for_ai = [{"role": "system", "content": CHARACTER_PROMPT}] + user_history[user_id]

    try:
        response = ai_client.chat({
            "model": "GigaChat-2-Pro",
            "messages": messages_for_ai
        })
        ai_reply = response.choices[0].message.content
        user_history[user_id].append({"role": "assistant", "content": ai_reply})
        await message.answer(ai_reply)
    except Exception as e:
        print(f"Ошибка ИИ: {e}")
        await message.answer("Ошибка. Попробуй ещё раз или напиши /start")

# ============================================================
# ===== ОБРАБОТЧИК ФОТО =====
# ============================================================
@dp.message_handler(content_types=['photo'])
async def handle_photo(message: types.Message):
    if not is_allowed(message.from_user.id):
        return
    await message.answer("Фото я не вижу. Опиши словами, что там.")

# ============================================================
# ===== ЗАПУСК =====
# ============================================================
async def main():
    init_db()
    print("Майки (Манджиро Сано) запускается...")
    bot_info = await bot.get_me()
    print(f"Бот @{bot_info.username} готов!")
    await dp.start_polling()

if __name__ == "__main__":
    asyncio.run(main())