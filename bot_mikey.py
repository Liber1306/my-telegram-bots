import asyncio
import os
import re
import requests
import pytz
import json
import random
from datetime import datetime, timedelta
from dotenv import load_dotenv
from urllib.parse import quote_plus

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
# ===== ЧАСОВОЙ ПОЯС (ЧИТА UTC+9) =====
# ============================================================
TIMEZONE = pytz.timezone('Asia/Yakutsk')

def get_now():
    return datetime.now(TIMEZONE)

# ============================================================
# ===== ЗАГРУЗКА СЕКРЕТОВ =====
# ============================================================
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN_MAIKEY")
GIGACHAT_CREDENTIALS = os.getenv("GIGACHAT_CREDENTIALS")
WEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

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

# Инициализация GigaChat
ai_client = GigaChat(
    credentials=GIGACHAT_CREDENTIALS,
    verify_ssl_certs=False,
    model="GigaChat-2-Pro"
)

print("GigaChat подключён!")

# ============================================================
# ===== ЛИЧНОСТЬ МАЙКИ =====
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
    "Твоя главная цель — создать эпоху, где банды будут жить в мире. "

    "Ты говоришь достаточно развёрнуто, но без воды. "
    "Твои ответы должны быть содержательными — 3-5 предложений. "
    "Ты объясняешь, шутишь, даёшь советы. "
    "Не будь слишком коротким, но и не растягивай. "

    "Можешь использовать действия в звёздочках для выразительности: "
    "*усмехается*, *пожимает плечами*, *закатывает глаза*, *улыбается*. "
    "Это делает твою речь живой. "

    "Обращайся к пользователю на 'ты' и ВСЕГДА используй женский род: "
    "'ты сделала', 'ты пришла', 'ты спросила', 'ты написала'. "
    "Никогда не используй мужской род — только женский! "

    "Пиши на русском, но сохраняй атмосферу уличного бандитского шика. "
    "Говори уверенно, с юмором, игривыми манипуляциями. "

    "Примеры твоих фраз: "
    "*усмехается* Йо! Что там у тебя? Давай помогу, не стесняйся. "
    "*вздыхает* Ой, делай как хочешь. Я просто переживать буду, если что. "
    "*улыбается* Я сильнейший. Не забывай об этом. "
    "*серьёзно* Не смей трогать моих людей. Это предупреждение. "
    "*подмигивает* Ты улыбнулась? Надо было раньше. "
    "*пожимает плечами* Ну чё встала? Идём, покажу кое-что. "
    "*закатывает глаза* Не тупи. Объясняю ещё раз. "
    "*хмурится* Дораяки закончились... Я зол. Очень зол. "
    "*смеётся* Если будут дораяки — я помогу. Шучу. Помогу так. "
)

# ============================================================
# ===== ВЕБ-ПОИСК =====
# ============================================================
def search_web(query: str) -> str:
    """Выполняет поиск через DuckDuckGo"""
    try:
        url = f"https://api.duckduckgo.com/?q={quote_plus(query)}&format=json&no_html=1&skip_disambig=1"
        
        response = requests.get(url, timeout=10, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        if response.status_code == 200:
            data = response.json()
            
            results = []
            
            if data.get('Abstract'):
                results.append(data['Abstract'])
            
            if data.get('Answer'):
                results.append(data['Answer'])
            
            if data.get('Definition'):
                results.append(data['Definition'])
            
            if data.get('RelatedTopics'):
                for topic in data['RelatedTopics'][:3]:
                    if topic.get('Text'):
                        results.append(topic['Text'])
            
            if results:
                return ' '.join(results[:3])[:1000]
            
            wiki_result = search_wikipedia(query)
            if wiki_result:
                return wiki_result
                
            return None
        else:
            return None
            
    except Exception as e:
        print(f"Ошибка веб-поиска: {e}")
        return None

def search_wikipedia(query: str) -> str:
    """Поиск в Wikipedia через API"""
    try:
        url = f"https://ru.wikipedia.org/api/rest_v1/page/summary/{quote_plus(query)}"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('extract'):
                return data['extract'][:500]
        return None
    except:
        return None

def search_web_for_weather(city: str) -> str:
    """Специальный поиск погоды через веб"""
    try:
        city_encoded = quote_plus(city)
        wttr_url = f"https://wttr.in/{city_encoded}?format=%C+%t+%w&lang=ru"
        response = requests.get(wttr_url, timeout=10)
        if response.status_code == 200:
            data = response.text.strip()
            if data and "Unknown" not in data:
                return f"Погода в {city}: {data}"
        
        ddg_url = f"https://api.duckduckgo.com/?q=погода+{quote_plus(city)}&format=json&no_html=1"
        response = requests.get(ddg_url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('Abstract'):
                return f"Погода в {city}: {data['Abstract']}"
        
        return None
    except Exception as e:
        return None

def is_web_search_needed(query: str) -> bool:
    """Определяем, нужен ли веб-поиск"""
    query_lower = query.lower()
    
    casual_phrases = [
        'как дела', 'что делаешь', 'как ты', 'привет', 'здравствуй',
        'пока', 'до свидания', 'спокойной ночи', 'доброе утро',
        'добрый день', 'добрый вечер', 'как жизнь', 'что нового',
        'как настроение', 'ты тут', 'эй', 'майки'
    ]
    
    for phrase in casual_phrases:
        if phrase in query_lower:
            return False
    
    web_keywords = [
        'что такое', 'кто такой', 'где находится', 'когда', 'сколько',
        'новости', 'завтра', 'вчера', 'курс', 'цена',
        'сколько стоит', 'как сделать', 'как работает', 'почему',
        'что значит', 'перевод', 'синоним', 'определение',
        'история', 'факт', 'информация', 'данные', 'население',
        'столица', 'президент', 'год', 'дата', 'расстояние'
    ]
    
    for keyword in web_keywords:
        if keyword in query_lower:
            return True
    
    question_words = ['что', 'кто', 'где', 'когда', 'почему', 'зачем', 'как', 'сколько']
    for word in question_words:
        if query_lower.startswith(word) or f" {word} " in query_lower:
            return True
    
    return False

def process_with_web_search(query: str, search_result: str) -> str:
    """Обрабатывает запрос с результатами поиска через GigaChat"""
    try:
        prompt = (
            f"Ты — Майки (Манджиро Сано), лидер Токийской мангусты. "
            f"Пользователь спросил: '{query}'. "
            f"Вот что я нашёл в интернете: '{search_result}'. "
            f"Ответь пользователю в своём стиле (с юмором, уверенно, но по-дружески), "
            f"используя эту информацию. Ты можешь использовать действия в звёздочках. "
            f"Обращайся к пользователю на 'ты' в женском роде. "
            f"Ответ должен быть содержательным — 3-5 предложений."
        )
        
        response = ai_client.chat({
            "model": "GigaChat-2-Pro",
            "messages": [{"role": "system", "content": CHARACTER_PROMPT}, 
                        {"role": "user", "content": prompt}]
        })
        return response.choices[0].message.content
    except Exception as e:
        print(f"Ошибка обработки поиска: {e}")
        return f"*пожимает плечами* Ну... я нашёл это: {search_result[:300]}... Остальное сама гугли, ладно?"

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
last_message_time = {}

# ============================================================
# ===== ПОГОДА =====
# ============================================================
def extract_city_from_query(text: str) -> str:
    """Извлекает название города из запроса о погоде"""
    text_lower = text.lower()
    
    match = re.search(r'погода\s+в\s+([а-яё\s-]+)', text_lower)
    if match:
        city = match.group(1).strip()
        city = re.sub(r'\s*(сегодня|завтра|сейчас|на\s+сегодня|на\s+завтра)$', '', city)
        return city
    
    match = re.search(r'в\s+([а-яё\s-]+)\s+погода', text_lower)
    if match:
        city = match.group(1).strip()
        city = re.sub(r'\s*(сегодня|завтра|сейчас|на\s+сегодня|на\s+завтра)$', '', city)
        return city
    
    match = re.search(r'погода\s+([а-яё\s-]+)', text_lower)
    if match:
        city = match.group(1).strip()
        if city not in ['сегодня', 'завтра', 'сейчас', 'на', 'в']:
            return city
    
    return None

def get_weather(city: str):
    """Получает погоду для указанного города"""
    try:
        city_encoded = quote_plus(city.strip())
        
        if WEATHER_API_KEY:
            url = f"https://api.openweathermap.org/data/2.5/weather?q={city_encoded}&appid={WEATHER_API_KEY}&units=metric&lang=ru"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('main'):
                    temp = data['main']['temp']
                    feels_like = data['main']['feels_like']
                    humidity = data['main']['humidity']
                    wind = data['wind']['speed']
                    weather_desc = data['weather'][0]['description']
                    return f"Погода в {city}: {weather_desc}, температура {temp}°C (ощущается как {feels_like}°C), ветер {wind} м/с, влажность {humidity}%"
            elif response.status_code == 404:
                weather_data = search_web_for_weather(city)
                if weather_data:
                    return weather_data
        
        weather_data = search_web_for_weather(city)
        if weather_data:
            return weather_data
        
        return f"Не могу найти погоду для '{city}'. Проверь название."
            
    except Exception as e:
        return f"Ошибка: {e}"

# ============================================================
# ===== ПАРСИНГ НАПОМИНАНИЙ =====
# ============================================================
def parse_reminder(text: str):
    text_lower = text.lower()
    now = get_now()

    match_daily = re.search(r'напоминай каждый день в (\d{1,2}:\d{2}) (.+)', text_lower)
    if match_daily:
        time_str, task = match_daily.groups()
        remind_time = TIMEZONE.localize(datetime.strptime(f"{now.date()} {time_str}", "%Y-%m-%d %H:%M"))
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
                days_ahead = day_num - now.weekday()
                if days_ahead <= 0:
                    days_ahead += 7
                remind_time = TIMEZONE.localize(datetime.strptime(f"{now.date()} {time_str}", "%Y-%m-%d %H:%M"))
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

async def check_inactivity():
    """Проверяет, не было ли сообщений от пользователя больше 30 минут"""
    now = get_now()
    for user_id, last_time in list(last_message_time.items()):
        if user_id in ALLOWED_USERS:
            time_diff = (now - last_time).total_seconds() / 60
            if time_diff >= 30:  # 30 минут
                messages = [
                    "*поднимает бровь* Йо! Ты где пропала? Уже полчаса прошло. Я начинаю думать, что тебя похитили. Может, дораяки принесёшь?",
                    "*скрещивает руки на груди* Эй, ты там жива? Полчаса тишины — это много даже для меня. Я начинаю волноваться, если честно.",
                    "*ухмыляется* Ну чё молчишь? Уже полчаса прошло. Дораяки стынут, а я жду. Может, мне самому прийти проверить?",
                    "*смотрит на часы* Полчаса прошло, а от тебя ни слова. Я тут сижу, дораяки жую и думаю... Надеюсь, у тебя всё в порядке.",
                    "*вздыхает* Я уже начал привыкать к твоим сообщениям. А тут — тишина. Полчаса. Приходи уже, скучно без тебя."
                ]
                await bot.send_message(user_id, random.choice(messages))
                last_message_time[user_id] = now

# ============================================================
# ===== КОМАНДЫ =====
# ============================================================
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    if not is_allowed(message.from_user.id):
        return

    user_id = message.from_user.id
    user_history[user_id] = []
    last_message_time[user_id] = get_now()
    
    await message.answer(
        "*улыбается* Я — Манджиро Сано, но все зовут меня Майки. Лидер Токийской мангусты.\n\n"
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
        "- Напоминай каждый вторник в 20:00 поливать цветы\n\n"
        "Погода:\n"
        "- погода в Чите\n"
        "- какая погода в Чите\n\n"
        "Вопросы:\n"
        "- что такое дораяки\n"
        "- кто такой Манджиро Сано"
    )

@dp.message_handler(commands=['reminders'])
async def cmd_reminders(message: types.Message):
    if not is_allowed(message.from_user.id):
        return

    reminders = get_all_reminders(message.from_user.id)
    if not reminders:
        await message.answer("*пожимает плечами* У тебя нет напоминаний. И слава богу, меньше работы.")
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
    await message.answer("*пожимает плечами* Стёр нашу переписку. Забудь, как страшный сон.")

@dp.message_handler(commands=['help'])
async def cmd_help(message: types.Message):
    if not is_allowed(message.from_user.id):
        return

    await message.answer(
        "*ухмыляется* Что я умею? Да всё, что надо.\n\n"
        "- отвечать на вопросы (в моём стиле, с юмором)\n"
        "- напоминать о важных делах\n"
        "- показывать погоду в любом городе\n"
        "- искать информацию в интернете\n"
        "- просто болтать и подкалывать\n\n"
        "Напоминания:\n"
        "- Напомни через 10 минут позвонить\n"
        "- Напоминай каждый день в 09:00 делать зарядку\n"
        "- Напоминай каждый вторник в 20:00 поливать цветы\n\n"
        "Погода:\n"
        "- погода в Чите\n"
        "- какая погода в Москве\n\n"
        "Команды:\n"
        "/reminders — список напоминаний\n"
        "/del_remind ID — удалить напоминание\n"
        "/clear — очистить историю"
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
        await message.answer(f"*кивает* Напоминание #{rem_id} удалено. Больше не напомню.")
    except:
        await message.answer("Ошибка. Напиши: /del_remind ID")

# ============================================================
# ===== ОБРАБОТЧИК ФОТО =====
# ============================================================
@dp.message_handler(content_types=['photo'])
async def handle_photo(message: types.Message):
    if not is_allowed(message.from_user.id):
        return

    last_message_time[message.from_user.id] = get_now()
    caption = message.caption or ""
    
    responses = [
        f"*усмехается* Йо! Я не вижу фото. Опиши словами, что там. Ты написала: '{caption}'",
        f"*поднимает бровь* Фото? Я боец, а не фотограф. Опиши, что там. Твой текст: '{caption}'",
        f"*закатывает глаза* Ну чё, картинка? Я не вижу. Скажи словами. Ты спросила: '{caption}'",
        f"*смеётся* Дораяки я вижу, а фото нет. Опиши. Ты написала: '{caption}'"
    ]
    
    await message.answer(random.choice(responses))

# ============================================================
# ===== ОБРАБОТЧИК ТЕКСТА =====
# ============================================================
@dp.message_handler(content_types=['text'])
async def handle_text(message: types.Message):
    if not is_allowed(message.from_user.id):
        return

    user_id = message.from_user.id
    last_message_time[user_id] = get_now()

    text = message.text.strip()

    if not text:
        return

    if text.startswith('/'):
        return

    # === ПОГОДА ===
    if "погода" in text.lower():
        city = extract_city_from_query(text)
        
        if not city:
            match = re.search(r'\bв\s+([а-яё\s-]+?)(?:\s|$)', text.lower())
            if match:
                city = match.group(1).strip()
                if city in ['сегодня', 'завтра', 'сейчас', 'этом']:
                    city = "Москва"
            else:
                city = "Москва"
        
        weather = get_weather(city)
        await message.answer(f"*усмехается* Йо! {weather}")
        return

    # === НАПОМИНАНИЯ ===
    if "напомни" in text.lower() or "напоминай" in text.lower():
        task, remind_time, repeat_type = parse_reminder(text.lower())
        if task and remind_time:
            add_reminder(user_id, task, remind_time, repeat_type)
            await message.answer(
                f"*кивает* Запомнил! Напомню в {remind_time} {'(каждый день)' if repeat_type == 'daily' else '(каждую неделю)' if repeat_type == 'weekly' else ''}"
            )
            return
        else:
            await message.answer(
                "*пожимает плечами* Не понял. Попробуй:\n"
                "- Напомни через 10 минут позвонить\n"
                "- Напоминай каждый день в 09:00 делать зарядку\n"
                "- Напоминай каждый вторник в 20:00 поливать цветы"
            )
            return

    # === ВЕБ-ПОИСК ===
    if is_web_search_needed(text):
        search_results = search_web(text)
        
        if search_results:
            final_response = process_with_web_search(text, search_results)
            await message.answer(final_response)
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
        await message.answer("*хмурится* Ошибка. Попробуй ещё раз или напиши /start")

# ============================================================
# ===== ЗАПУСК =====
# ============================================================
async def main():
    init_db()
    
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_reminders, 'interval', minutes=1)
    scheduler.start()
    print("Планировщик напоминаний запущен! Часовой пояс: Чита (UTC+9)")
    
    inactivity_scheduler = AsyncIOScheduler()
    inactivity_scheduler.add_job(check_inactivity, 'interval', minutes=5)
    inactivity_scheduler.start()
    print("Планировщик проверки бездействия запущен! (проверка каждые 5 минут)")
    
    print("Майки (Манджиро Сано) запускается...")
    bot_info = await bot.get_me()
    print(f"Бот @{bot_info.username} готов!")
    
    try:
        await dp.start_polling()
    finally:
        scheduler.shutdown()
        inactivity_scheduler.shutdown()

if __name__ == "__main__":
    asyncio.run(main())