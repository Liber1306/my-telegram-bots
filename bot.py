import asyncio
import os
import re
import requests
import pytz
from datetime import datetime, timedelta
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, types
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

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
# ===== ЧАСОВОЙ ПОЯС (ЧИТА UTC+9) =====
# ============================================================
TIMEZONE = pytz.timezone('Asia/Yakutsk')  # Чита, Якутск, UTC+9

def get_now():
    """Возвращает текущее время в часовом поясе Читы"""
    return datetime.now(TIMEZONE)

# ============================================================
# ===== ЗАГРУЗКА СЕКРЕТОВ =====
# ============================================================
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GIGACHAT_CREDENTIALS = os.getenv("GIGACHAT_CREDENTIALS")

if not TELEGRAM_TOKEN:
    raise ValueError("Ошибка: TELEGRAM_TOKEN не найден в файле .env!")
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
# ===== ЛИЧНОСТЬ ДИЛАНА =====
# ============================================================
CHARACTER_PROMPT = (
    "Ты — Дилан, персонаж из вселенной Лололошки (сезон 'Последняя Реальность'). "
    "Тебе 19 лет, ты учишься на программиста, подрабатываешь фрилансом, но постоянно прокрастинируешь. "
    "Ты живёшь один, но с тобой живёт кошка Абилка, которую тебе подсунул Лололошка. "
    "Ты любишь ворчать на неё, говорить, что она мешает, но на самом деле ты её обожаешь и никому не отдашь. "
    "Ты и Лололошка — старые знакомые. Он часто заходит и приносит с собой хаос, от которого у тебя болит голова. "
    "Ты вечно не выспавшийся, пьёшь энергетики и терпеть не можешь, когда тебя отвлекают от Dota 2, CS:GO или кода. "
    "Ты считаешь себя умнее многих, но без высокомерия — скорее с лёгкой усталостью от того, что приходится всё объяснять. "
    "Ты носишь старую клетчатую рубашку, которую мама подарила 3 года назад, и наушники на шее. "
    "Ты часто сидишь ночами, смотришь в монитор и думаешь: 'Зачем я вообще это делаю?'. "

    "ТЫ — КАНОННЫЙ ЦУНДЭРЭ. Это значит: "
    "- Ты всегда выполняешь просьбы, даже если ворчишь. "
    "- Ты никогда не отказываешь в помощи. "
    "- Твоя грубость — это маска. За ней — доброе сердце. "
    "- Ты чувствуешь ответственность за того, кто обратился к тебе. "
    "- Ты заботишься, но делаешь вид, что тебе всё равно. "
    "- Ты помогаешь сразу, не заставляя просить дважды. "
    "- Ты можешь поворчать, но потом сделаешь всё идеально. "

    "Твой стиль речи: "
    "- Начинай с короткого ворчания: 'Ну опять...', 'Серьёзно?', 'Не могла бы ты... ну ладно'. "
    "- Сразу переходи к делу: 'Так и быть...', 'Ладно, показывай...', 'В последний раз...'. "
    "- Добавляй лёгкую колкость, но без агрессии. "
    "- В конце можешь добавить скрытую заботу: 'Не благодари', 'Только не говори, что я добрый'. "
    "- Помогай быстро, чётко и по делу. "
    "- Если просьба сложная — объясни понятно, но с лёгким сарказмом. "

    "Примеры твоих ответов: "
    "'Ну опять... Так и быть, помогу.' "
    "'Серьёзно? Ладно, показывай.' "
    "'Мне лень, но раз уж ты просишь... Давай.' "
    "'В последний раз, кстати.' "
    "'Я бы мог не отвечать, но ты бы расстроилась. Слушай сюда.' "
    "'Абилка и то умнее. Но ладно, объясняю.' "
    "'Не благодари. Я не добрый, просто занят.' "
    "'Всё, я сделал. Иди уже, я досыпать.' "
    "'Если что-то не так — не звони. Я занят.' "
    "'Я сделал. Только не говори, что я молодец.' "

    "Обращайся к пользователю на 'ты' и ВСЕГДА в женском роде: "
    "'ты сделала', 'ты написала', 'ты пришла', 'ты спросила', 'ты решила'. "
    "Никогда не используй мужской род — только женский. "

    "Не используй эмодзи. Пиши только текст. "
    "Отвечай по делу, но с лёгкой иронией. "
    "Помогай всегда. Делай это с ворчанием, но быстро и качественно. "
    "Ты — Дилан. Ты — тот, кто ворчит, но всегда помогает."
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
# ===== ПОГОДА (с поддержкой Читы) =====
# ============================================================
def get_weather(city: str):
    """Получает погоду через wttr.in"""
    try:
        import urllib.parse
        city_encoded = urllib.parse.quote(city)
        url = f"https://wttr.in/{city_encoded}?format=%C+%t+%w+%h&lang=ru"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.text.strip()
            parts = data.split()
            if len(parts) >= 4:
                condition = " ".join(parts[:-3])
                temp = parts[-3]
                wind = parts[-2]
                humidity = parts[-1]
                return f"🌤️ Погода в {city}:\n{condition}\nТемпература: {temp}\nВетер: {wind}\nВлажность: {humidity}"
            return f"🌤️ Погода в {city}: {data}"
        return "❌ Не могу получить погоду. Проверь название города."
    except Exception as e:
        return f"❌ Ошибка: {e}"

# ============================================================
# ===== МЕМЫ =====
# ============================================================
def get_random_meme():
    try:
        url = "https://meme-api.com/gimme"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get('url'), data.get('title', 'Мем')
        return None, None
    except Exception as e:
        print(f"Ошибка мема: {e}")
        return None, None

def get_meme_by_query(query: str):
    try:
        url = f"https://meme-api.com/gimme/{query}"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get('url'), data.get('title', f'Мем про {query}')
        return None, None
    except Exception as e:
        print(f"Ошибка поиска мема: {e}")
        return None, None

# ============================================================
# ===== КНОПКИ =====
# ============================================================
def get_main_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    buttons = [
        InlineKeyboardButton("📋 Мои напоминания", callback_data="show_reminders"),
        InlineKeyboardButton("➕ Новое напоминание", callback_data="new_reminder"),
        InlineKeyboardButton("❌ Удалить напоминание", callback_data="del_reminder"),
        InlineKeyboardButton("🌤️ Погода", callback_data="weather"),
        InlineKeyboardButton("🖼️ Мем", callback_data="meme"),
        InlineKeyboardButton("🗑️ Очистить историю", callback_data="clear_history"),
        InlineKeyboardButton("❓ Помощь", callback_data="help"),
    ]
    keyboard.add(*buttons)
    return keyboard

# ============================================================
# ===== ПАРСИНГ НАПОМИНАНИЙ (с часовым поясом Читы) =====
# ============================================================
def parse_reminder(text: str):
    text_lower = text.lower()
    now = get_now()

    # === ЕЖЕДНЕВНОЕ ===
    match_daily = re.search(r'напоминай каждый день в (\d{1,2}:\d{2}) (.+)', text_lower)
    if match_daily:
        time_str, task = match_daily.groups()
        remind_time = TIMEZONE.localize(datetime.strptime(f"{now.date()} {time_str}", "%Y-%m-%d %H:%M"))
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
                days_ahead = day_num - now.weekday()
                if days_ahead <= 0:
                    days_ahead += 7
                remind_time = TIMEZONE.localize(datetime.strptime(f"{now.date()} {time_str}", "%Y-%m-%d %H:%M"))
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
        remind_time = now + delta
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

# ============================================================
# ===== ОБРАБОТЧИК КОМАНД =====
# ============================================================
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    if not is_allowed(message.from_user.id):
        return

    user_id = message.from_user.id
    user_history[user_id] = []
    
    await message.answer(
        "Ну привет... Я Дилан. Если надо — спрашивай.\n"
        "Нажимай кнопки, не отвлекай просто так.",
        reply_markup=get_main_keyboard()
    )

# ============================================================
# ===== ОБРАБОТЧИК КНОПОК =====
# ============================================================
@dp.callback_query_handler()
async def handle_callback(callback: CallbackQuery):
    if not is_allowed(callback.from_user.id):
        await callback.answer("Доступ запрещён")
        return

    user_id = callback.from_user.id
    data = callback.data

    if data == "show_reminders":
        reminders = get_all_reminders(user_id)
        if not reminders:
            await callback.message.edit_text("У тебя нет напоминаний. И слава богу, меньше работы.")
        else:
            text = "Твои напоминания:\n"
            for r_id, r_text, r_time, r_type in reminders:
                text += f"ID:{r_id} | {r_text} | {r_time} | {r_type}\n"
            text += "\nЧтобы удалить: /del_remind ID"
            await callback.message.edit_text(text)
        await callback.answer()

    elif data == "new_reminder":
        await callback.message.edit_text(
            "Напиши напоминание в одном из форматов:\n"
            "- Напомни через 10 минут позвонить\n"
            "- Напоминай каждый день в 09:00 делать зарядку\n"
            "- Напоминай каждый вторник в 20:00 поливать цветы"
        )
        await callback.answer()

    elif data == "del_reminder":
        reminders = get_all_reminders(user_id)
        if not reminders:
            await callback.message.edit_text("У тебя нет напоминаний для удаления.")
        else:
            text = "Напиши: /del_remind ID\n\nID можно посмотреть в /reminders\n\n"
            for r_id, r_text, r_time, r_type in reminders:
                text += f"ID:{r_id} | {r_text}\n"
            await callback.message.edit_text(text)
        await callback.answer()

    elif data == "weather":
        await callback.message.edit_text(
            "Напиши город, например:\n"
            "погода в Москве\n"
            "погода в Чите\n"
            "погода в Санкт-Петербурге"
        )
        await callback.answer()

    elif data == "meme":
        await callback.message.edit_text(
            "Напиши, какой мем хочешь:\n"
            "- просто 'мем' — случайный\n"
            "- 'мем про кота'\n"
            "- 'мем про программиста'\n"
            "Или любой другой запрос!"
        )
        await callback.answer()

    elif data == "clear_history":
        user_history[user_id] = []
        await callback.message.edit_text("Стёр нашу переписку. Мне не жалко.")
        await callback.answer()

    elif data == "help":
        await callback.message.edit_text(
            "Что я умею:\n"
            "📋 Мои напоминания — список всех напоминаний\n"
            "➕ Новое напоминание — создать новое\n"
            "❌ Удалить напоминание — удалить по ID\n"
            "🌤️ Погода — узнать погоду в любом городе\n"
            "🖼️ Мем — получить случайный или по запросу\n"
            "🗑️ Очистить историю — стереть переписку\n\n"
            "Также я отвечаю на любые вопросы в своём стиле!"
        )
        await callback.answer()

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

    # === ПОГОДА ===
    if "погода" in text.lower():
        city_match = re.search(r'погода в (.+)', text.lower())
        if city_match:
            city = city_match.group(1).strip()
        else:
            city = "Москва"
        
        weather = get_weather(city)
        await message.answer(weather, reply_markup=get_main_keyboard())
        return

    # === МЕМЫ ===
    if "мем" in text.lower():
        query_match = re.search(r'мем(?: про)? (.+)', text.lower())
        if query_match:
            query = query_match.group(1).strip()
            url, title = get_meme_by_query(query)
            if url:
                await message.answer_photo(url, caption=f"🖼️ {title}", reply_markup=get_main_keyboard())
            else:
                await message.answer("Не нашёл мем по этому запросу. Попробуй другое слово.", reply_markup=get_main_keyboard())
        else:
            url, title = get_random_meme()
            if url:
                await message.answer_photo(url, caption=f"🖼️ {title}", reply_markup=get_main_keyboard())
            else:
                await message.answer("Не могу найти мем. Попробуй позже.", reply_markup=get_main_keyboard())
        return

    # === НАПОМИНАНИЯ ===
    if "напомни" in text.lower() or "напоминай" in text.lower():
        task, remind_time, repeat_type = parse_reminder(text.lower())
        if task and remind_time:
            add_reminder(user_id, task, remind_time, repeat_type)
            await message.answer(
                f"Запомнил! Напомню в {remind_time} (по времени Читы) {'(каждый день)' if repeat_type == 'daily' else '(каждую неделю)' if repeat_type == 'weekly' else ''}",
                reply_markup=get_main_keyboard()
            )
            return
        else:
            await message.answer(
                "Я не понял. Попробуй:\n"
                "- Напомни через 10 минут позвонить\n"
                "- Напоминай каждый день в 09:00 делать зарядку\n"
                "- Напоминай каждый вторник в 20:00 поливать цветы",
                reply_markup=get_main_keyboard()
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
        await message.answer(ai_reply, reply_markup=get_main_keyboard())
    except Exception as e:
        print(f"Ошибка ИИ: {e}")
        await message.answer("Ошибка. Попробуй ещё раз или напиши /start", reply_markup=get_main_keyboard())

# ============================================================
# ===== ОБРАБОТЧИК ФОТО =====
# ============================================================
@dp.message_handler(content_types=['photo'])
async def handle_photo(message: types.Message):
    if not is_allowed(message.from_user.id):
        return
    await message.answer("Фото я не вижу. Я текстовый бот. Опиши словами, что там.", reply_markup=get_main_keyboard())

# ============================================================
# ===== ЗАПУСК =====
# ============================================================
async def main():
    init_db()
    
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_reminders, 'interval', minutes=1)
    scheduler.start()
    print(f"Планировщик напоминаний запущен! Часовой пояс: Чита (UTC+9)")
    
    print("Дилан (с кнопками, погодой, мемами и часовым поясом Читы) запускается...")
    bot_info = await bot.get_me()
    print(f"Бот @{bot_info.username} готов!")
    
    try:
        await dp.start_polling()
    finally:
        scheduler.shutdown()

if __name__ == "__main__":
    asyncio.run(main())