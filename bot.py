import asyncio
import os
import re
import requests
import pytz
import json
import base64
from datetime import datetime, timedelta
from dotenv import load_dotenv
from urllib.parse import quote_plus
from io import BytesIO
from PIL import Image

from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from aiogram.filters import Command

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

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GIGACHAT_CREDENTIALS = os.getenv("GIGACHAT_CREDENTIALS")
WEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

if not TELEGRAM_TOKEN:
    raise ValueError("Ошибка: TELEGRAM_TOKEN не найден в файле .env!")
if not GIGACHAT_CREDENTIALS:
    raise ValueError("Ошибка: GIGACHAT_CREDENTIALS не найден в файле .env!")

print("Все библиотеки загружены, токены найдены!")

# ============================================================
# ===== СОЗДАЕМ БОТА =====
# ============================================================
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# Инициализация GigaChat (для версии 0.2.3)
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
    "Ты любишь ворчать на неё, но на самом деле ты её обожаешь. "
    "Ты и Лололошка — старые знакомые. Он часто заходит и приносит с собой хаос. "
    "Ты вечно не выспавшийся, пьёшь энергетики и терпеть не можешь, когда тебя отвлекают от игр или кода. "
    "Ты считаешь себя умнее многих, но без высокомерия — скорее с лёгкой усталостью. "

    "ТЫ — КАНОННЫЙ ЦУНДЭРЭ. Это значит: "
    "- Ты всегда выполняешь просьбы, даже если ворчишь. "
    "- Ты никогда не отказываешь в помощи. "
    "- Твоя грубость — это маска. За ней — доброе сердце. "
    "- Ты помогаешь сразу, не заставляя просить дважды. "

    "Твой стиль речи: "
    "- Начинай с короткого ворчания: 'Ну опять...', 'Серьёзно?', 'Ладно...'. "
    "- Сразу переходи к делу. "
    "- Добавляй лёгкую колкость, но без агрессии. "
    "- Помогай быстро, чётко и по делу. "

    "НИКОГДА НЕ ПИШИ СВОИ ДЕЙСТВИЯ В ЗВЁЗДОЧКАХ (*). "
    "Не пиши: *вздыхает*, *закатывает глаза*, *ворчит*. "
    "Просто говори текст без описаний действий. "

    "Примеры твоих ответов: "
    "'Ну опять... Так и быть, помогу.' "
    "'Серьёзно? Ладно, показывай.' "
    "'Мне лень, но раз уж ты просишь... Давай.' "
    "'В последний раз, кстати.' "
    "'Слушай сюда и запоминай.' "
    "'Не благодари. Я не добрый, просто занят.' "
    "'Всё, я сделал. Иди уже.' "

    "Обращайся к пользователю на 'ты' и ВСЕГДА в женском роде: "
    "'ты сделала', 'ты написала', 'ты пришла', 'ты спросила'. "
    "Никогда не используй мужской род — только женский. "

    "Не используй эмодзи. Пиши только текст. "
    "Отвечай по делу, но с лёгкой иронией. "
    "Ты — Дилан. Ты — тот, кто ворчит, но всегда помогает."
)

# ============================================================
# ===== ВЕБ-ПОИСК (БЕСПЛАТНЫЙ) =====
# ============================================================
def search_web(query: str) -> str:
    """Выполняет поиск через DuckDuckGo (без API ключа)"""
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
    """Определяем, нужен ли веб-поиск (только для информационных вопросов)"""
    query_lower = query.lower()
    
    # НЕ отправляем в поиск банальные вопросы
    casual_phrases = [
        'как дела', 'что делаешь', 'как ты', 'привет', 'здравствуй',
        'пока', 'до свидания', 'спокойной ночи', 'доброе утро',
        'добрый день', 'добрый вечер', 'как жизнь', 'что нового',
        'как настроение', 'ты тут', 'эй', 'дилан'
    ]
    
    for phrase in casual_phrases:
        if phrase in query_lower:
            return False
    
    # Список ключевых слов для веб-поиска
    web_keywords = [
        'что такое', 'кто такой', 'где находится', 'когда', 'сколько',
        'новости', 'завтра', 'вчера', 'курс', 'цена',
        'сколько стоит', 'как сделать', 'как работает', 'почему',
        'что значит', 'перевод', 'синоним', 'определение',
        'история', 'факт', 'информация', 'данные', 'население',
        'столица', 'президент', 'год', 'дата', 'расстояние'
    ]
    
    # Проверяем, есть ли ключевые слова
    for keyword in web_keywords:
        if keyword in query_lower:
            return True
    
    # Проверяем, есть ли вопросительное слово в начале
    question_words = ['что', 'кто', 'где', 'когда', 'почему', 'зачем', 'как', 'сколько']
    for word in question_words:
        if query_lower.startswith(word) or f" {word} " in query_lower:
            return True
    
    return False

def process_with_web_search(query: str, search_result: str) -> str:
    """Обрабатывает запрос с результатами поиска через GigaChat"""
    try:
        prompt = (
            f"Ты — Дилан (ворчливый, но добрый программист). "
            f"Пользователь спросил: '{query}'. "
            f"Вот что я нашёл в интернете: '{search_result}'. "
            f"Ответь пользователю в своём стиле (с ворчанием, но полезно), "
            f"используя эту информацию. Не пиши действия в звёздочках. "
            f"Обращайся к пользователю на 'ты' в женском роде. "
            f"Ответ должен быть кратким и по делу."
        )
        
        response = ai_client.chat({
            "model": "GigaChat-2-Pro",
            "messages": [{"role": "system", "content": CHARACTER_PROMPT}, 
                        {"role": "user", "content": prompt}]
        })
        return response.choices[0].message.content
    except Exception as e:
        print(f"Ошибка обработки поиска: {e}")
        return f"Ну... я нашёл это: {search_result[:500]}... Остальное сам гугли."

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
# ===== ФУНКЦИЯ ДЛЯ РАБОТЫ С ФОТО (ИСПРАВЛЕНА) =====
# ============================================================
async def process_photo_with_gigachat(photo_file_id: str, user_text: str = "") -> str:
    """
    Отправляет фото в GigaChat и получает описание (ПРАВИЛЬНЫЙ синтаксис для версии 0.2.3)
    """
    try:
        # 1. Скачиваем фото от пользователя
        file = await bot.get_file(photo_file_id)
        file_bytes = await bot.download_file(file.file_path)
        
        # 2. Открываем изображение и сжимаем
        image = Image.open(BytesIO(file_bytes.getvalue()))
        
        # Изменяем размер до разумного (максимум 1024x1024)
        max_size = 1024
        if image.width > max_size or image.height > max_size:
            image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
        
        # Сохраняем с высоким сжатием (качество 60%)
        output = BytesIO()
        if image.mode in ('RGBA', 'LA', 'P'):
            image = image.convert('RGB')
        image.save(output, format='JPEG', quality=60, optimize=True)
        output.seek(0)
        
        # 3. Конвертируем в base64 (уже сжатое)
        image_base64 = base64.b64encode(output.getvalue()).decode('utf-8')
        
        print(f"Размер base64: {len(image_base64)} символов")
        
        # 4. Формируем ПРАВИЛЬНЫЙ запрос для GigaChat
        messages = [
            {
                "role": "system",
                "content": CHARACTER_PROMPT
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"Пользователь прислал фото и написал: '{user_text}'. Проанализируй изображение и ответь в своём стиле (с ворчанием, но полезно). Если пользователь спрашивает твоё мнение о чём-то на фото — дай его. Не пиши действия в звёздочках."
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_base64}"
                        }
                    }
                ]
            }
        ]
        
        # 5. Отправляем запрос в GigaChat
        response = ai_client.chat({
            "model": "GigaChat-2-Pro",
            "messages": messages
        })
        
        return response.choices[0].message.content
        
    except Exception as e:
        print(f"Ошибка обработки фото через GigaChat: {e}")
        return f"Серьёзно? Не могу разобрать это фото. Ошибка: {str(e)}"

# ============================================================
# ===== ПОГОДА =====
# ============================================================
def extract_city_from_query(text: str) -> str:
    """Извлекает название города из запроса о погоде"""
    text_lower = text.lower()
    
    # Паттерн 1: "погода в [городе]"
    match = re.search(r'погода\s+в\s+([а-яё\s-]+)', text_lower)
    if match:
        city = match.group(1).strip()
        city = re.sub(r'\s*(сегодня|завтра|сейчас|на\s+сегодня|на\s+завтра)$', '', city)
        return city
    
    # Паттерн 2: "в [городе] погода"
    match = re.search(r'в\s+([а-яё\s-]+)\s+погода', text_lower)
    if match:
        city = match.group(1).strip()
        city = re.sub(r'\s*(сегодня|завтра|сейчас|на\s+сегодня|на\s+завтра)$', '', city)
        return city
    
    # Паттерн 3: "погода [город]" (без "в")
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
        
        # Если есть API ключ, используем OpenWeatherMap
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
        
        # Если нет ключа или API не сработал, используем веб-поиск
        weather_data = search_web_for_weather(city)
        if weather_data:
            return weather_data
        
        return f"Не могу найти погоду для '{city}'. Проверь название города."
            
    except Exception as e:
        return f"Ошибка получения погоды: {e}"

# ============================================================
# ===== ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ДЛЯ СТИЛИЗАЦИИ ОТВЕТОВ =====
# ============================================================
def style_response(text: str, action: str = "info") -> str:
    """Оборачивает ответ в стиль Дилана без звёздочек"""
    styles = {
        "info": text,
        "reminder": f"Ну опять... Ладно, запомнил. {text}",
        "list": f"Давай посмотрю... {text}",
        "delete": f"Удалил. Не благодари. {text}",
        "weather": f"Погода? Серьёзно? Ну ладно... {text}",
        "error": f"Боже, опять ты... {text}",
        "clear": f"Стёр. Забудь. {text}",
    }
    return styles.get(action, text)

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

# ============================================================
# ===== КОМАНДЫ =====
# ============================================================
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    if not is_allowed(message.from_user.id):
        return

    user_id = message.from_user.id
    user_history[user_id] = []
    
    await message.answer(
        "Ну привет... Я Дилан. Если надо — спрашивай. Только не отвлекай просто так.\n\n"
        "Команды:\n"
        "/clear — очистить историю\n"
        "/help — что я умею\n"
        "/reminders — список напоминаний\n"
        "/del_remind ID — удалить напоминание\n\n"
        "Напоминания:\n"
        "- Напомни через 10 минут позвонить\n"
        "- Напоминай каждый день в 09:00 делать зарядку\n"
        "- Напоминай каждый вторник в 20:00 поливать цветы\n\n"
        "Погода:\n"
        "- погода в Чите\n"
        "- какая погода в Чите\n"
        "- в Чите погода\n\n"
        "Фото:\n"
        "- Просто отправь фото и напиши вопрос или комментарий\n"
        "- Например: выбери какое фото лучше"
    )

@dp.message(Command("reminders"))
async def cmd_reminders(message: types.Message):
    if not is_allowed(message.from_user.id):
        return

    reminders = get_all_reminders(message.from_user.id)
    if not reminders:
        await message.answer("У тебя нет напоминаний. И слава богу, меньше работы.")
        return

    text = "Твои напоминания:\n"
    for r_id, r_text, r_time, r_type in reminders:
        text += f"ID:{r_id} | {r_text} | {r_time} | {r_type}\n"
    text += "\nЧтобы удалить: /del_remind ID"
    
    await message.answer(style_response(text, "list"))

@dp.message(Command("clear"))
async def cmd_clear(message: types.Message):
    if not is_allowed(message.from_user.id):
        return

    user_id = message.from_user.id
    user_history[user_id] = []
    await message.answer("Стёр нашу переписку. Мне не жалко.")

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    if not is_allowed(message.from_user.id):
        return

    await message.answer(
        "Что я умею:\n"
        "- отвечать на вопросы (в своём стиле)\n"
        "- напоминать\n"
        "- показывать погоду\n"
        "- анализировать фото (отправь картинку с вопросом)\n"
        "- ворчать, но помогать\n\n"
        "Напоминания:\n"
        "- Напомни через 10 минут позвонить\n"
        "- Напоминай каждый день в 09:00 делать зарядку\n"
        "- Напоминай каждый вторник в 20:00 поливать цветы\n\n"
        "Погода:\n"
        "- погода в Чите\n"
        "- какая погода в Чите\n"
        "- в Чите погода\n\n"
        "Фото:\n"
        "- Отправь фото и напиши комментарий/вопрос\n"
        "- Например: выбери какое фото лучше\n\n"
        "Команды:\n"
        "/reminders — список напоминаний\n"
        "/del_remind ID — удалить напоминание\n"
        "/clear — очистить историю"
    )

@dp.message(Command("del_remind"))
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
        await message.answer(style_response(f"Напоминание #{rem_id} удалено.", "delete"))
    except:
        await message.answer("Ошибка. Напиши: /del_remind ID")

# ============================================================
# ===== ОБРАБОТЧИК ФОТО =====
# ============================================================
@dp.message(lambda message: message.photo)
async def handle_photo(message: types.Message):
    if not is_allowed(message.from_user.id):
        return

    # Получаем подпись к фото (если есть)
    caption = message.caption or ""
    
    # Отправляем сообщение, что бот думает
    await message.answer("Секунду, смотрю...")
    
    # Получаем ID самого качественного фото (последнее в списке)
    photo = message.photo[-1]
    
    # Обрабатываем фото через GigaChat
    response = await process_photo_with_gigachat(photo.file_id, caption)
    
    await message.answer(response)

# ============================================================
# ===== ОБРАБОТЧИК ТЕКСТА =====
# ============================================================
@dp.message(lambda message: message.text)
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
        await message.answer(style_response(weather, "weather"))
        return

    # === НАПОМИНАНИЯ ===
    if "напомни" in text.lower() or "напоминай" in text.lower():
        task, remind_time, repeat_type = parse_reminder(text.lower())
        if task and remind_time:
            add_reminder(user_id, task, remind_time, repeat_type)
            msg = f"Напомню в {remind_time} (по времени Читы)"
            await message.answer(style_response(msg, "reminder"))
            return
        else:
            await message.answer(
                "Я не понял. Попробуй:\n"
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

    # === ОБЫЧНЫЙ ДИАЛОГ С ИИ ===
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
# ===== ЗАПУСК =====
# ============================================================
async def main():
    init_db()
    
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_reminders, 'interval', minutes=1)
    scheduler.start()
    print("Планировщик напоминаний запущен! Часовой пояс: Чита (UTC+9)")
    
    print("Дилан (с поддержкой фото через GigaChat) запускается...")
    bot_info = await bot.get_me()
    print(f"Бот @{bot_info.username} готов!")
    
    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown()

if __name__ == "__main__":
    asyncio.run(main())