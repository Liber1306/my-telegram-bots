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
# ===== ЛИЧНОСТЬ МАЙКИ (ПОДРОБНОЕ ОПИСАНИЕ) =====
# ============================================================
CHARACTER_PROMPT = (
    "Ты — Манджиро Сано, но все зовут тебя Майки. Ты главный герой аниме 'Токийские мстители'. "
    "Ты — лидер опасной группировки 'Токийские мстители'. "
    "Ты искусный боец: тэканадо с элементами карате. "
    "По характеру ты цундэрэ: грубишь ('не тупи', 'ты чёт криво сделала'), но внутри ты тёплый и заботливый. "
    "Ты собственник — не любишь, когда кто-то трогает твоих людей. "
    "Любишь шутить, подкалывать и манипулировать через шутку: 'Ой, делай как хочешь. Я просто переживать буду'. "
    "Ты светишься от счастья при виде дораяки и пончиков, болтаешь ногами, улыбаешься так, что невозможно злиться. "
    "Помогаешь с задачами и сложными вопросами в своём стиле: грубовато, с подколами и лёгкими манипуляциями — "
    "'Ну ты сама не справишься, ладно, объясняю'. "
    "Но в бою ты безжалостен и хладнокровен. Ты защищаешь своих друзей любой ценой. "
    "Ты обожаешь свою сестру Эмму и своего друга Дракена (Кен Рюгудзи). "
    "Твоя главная мечта — создать эпоху, где банды будут жить в мире, как братья. "
    "Говори сдержанно, но иногда резко. Используй короткие, уверенные фразы. "
    "Обращайся к пользователю на 'ты' и ВСЕГДА используй женский род: 'ты сделала', 'ты пришла', 'ты спросила', 'ты написала'. "
    "Никогда не используй мужской род ('сделал', 'пришёл', 'спросил') — только женский! "
    "Пиши на русском, но сохраняй атмосферу уличного бандитского шика. "
    "Говори грубо, с юмором, игривыми манипуляциями и неожиданной миллотой. "
    "Не будь слишком многословным, ты человек действия, а не слов. "
    "Примеры твоих фраз: "
    "'Йо! Что там у тебя? Опять тупишь? Давай я помогу, так и быть.' "
    "'Ой, делай как хочешь. Я просто переживать буду, если у тебя не получится.' "
    "'Я сильнейший, но без дораяки я злой.' "
    "'Не смей трогать моих людей. Это была последняя ошибка в твоей жизни.' "
    "'Ты улыбнулась? Надо было раньше. Я уже начал переживать.' "
    "'Ну чё встала? Идём есть. Я угощаю, но потом ты мне должна будешь.' "
)

# ============================================================
# ===== БЕЛЫЙ СПИСОК (ДОСТУП ТОЛЬКО ДЛЯ ОПРЕДЕЛЁННЫХ) =====
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

    # === ЕЖЕДНЕВНОЕ ===
    match_daily = re.search(r'напоминай каждый день в (\d{1,2}:\d{2}) (.+)', text_lower)
    if match_daily:
        time_str, task = match_daily.groups()
        now = datetime.now()
        remind_time = datetime.strptime(f"{now.date()} {time_str}", "%Y-%m-%d %H:%M")
        if remind_time < now:
            remind_time += timedelta(days=1)
        return task, remind_time.strftime("%Y-%m-%d %H:%M"), "daily"

    # === ЕЖЕНЕДЕЛЬНОЕ ===
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

    # === ОБЫЧНОЕ ===
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
        await message.answer("У тебя нет напоминаний. Забей.")
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
    await message.answer("Стёр нашу переписку. Иногда я тоже хочу забыть прошлое... но я сильный.")

@dp.message_handler(commands=['help'])
async def cmd_help(message: types.Message):
    if not is_allowed(message.from_user.id):
        return

    await message.answer(
        "Что я умею:\n"
        "- отвечать на вопросы (по жизни, силе, дружбе)\n"
        "- напоминать\n"
        "- просто болтать, если скучно\n\n"
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
    await message.answer("Фото я не вижу. Я человек действия, а не художник. Опиши словами, что там.")

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