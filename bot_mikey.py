import asyncio
import os
from dotenv import load_dotenv

# Импорты для aiogram 2.x
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message

from gigachat import GigaChat

# ============================================================
# ===== ЗАГРУЗКА СЕКРЕТОВ ИЗ .env =====
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
    model="GigaChat-2-Pro"  # ← как у Дилана
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
    "'Я сильнейший, но без дораяки я злой.?' "
    "'Не смей трогать моих людей. Это была последняя ошибка в твоей жизни.' "
    "'Ты улыбнулась? Надо было раньше. Я уже начал переживать.' "
    "'Ну чё встала? Идём есть. Я угощаю, но потом ты мне должна будешь.' "
)

# ============================================================
# ===== БЕЛЫЙ СПИСОК (ДОСТУП ТОЛЬКО ДЛЯ ОПРЕДЕЛЁННЫХ) =====
# ============================================================
ALLOWED_USERS = [2084482777, 7798113843]  # ← СЮДА ВСТАВЛЯЙ ID

def is_allowed(user_id: int) -> bool:
    """Проверяет, есть ли пользователь в белом списке"""
    return user_id in ALLOWED_USERS

# ============================================================
# ===== ХРАНИЛИЩЕ ИСТОРИИ =====
# ============================================================
user_history = {}

# ============================================================
# ===== НАПОМИНАЛКА =====
# ============================================================
async def send_reminder(chat_id: int, task_text: str, seconds: int):
    await asyncio.sleep(seconds)
    await bot.send_message(
        chat_id,
        f"Напоминаю: {task_text}. Иди делай, я занят."
    )

# ============================================================
# ===== КОМАНДА /START =====
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
        "/help — что я умею\n\n"
        "Напоминания: напиши 'Напомни через X минут сделать...'\n"
        "Фото я не вижу, так что описывай словами."
    )

# ============================================================
# ===== КОМАНДА /CLEAR =====
# ============================================================
@dp.message_handler(commands=['clear'])
async def cmd_clear(message: types.Message):
    if not is_allowed(message.from_user.id):
        return

    user_id = message.from_user.id
    user_history[user_id] = []
    await message.answer("Стёр нашу переписку. Иногда я тоже хочу забыть прошлое... но я сильный.")

# ============================================================
# ===== КОМАНДА /HELP =====
# ============================================================
@dp.message_handler(commands=['help'])
async def cmd_help(message: types.Message):
    if not is_allowed(message.from_user.id):
        return

    await message.answer(
        "Что я умею:\n"
        "- отвечать на вопросы (по жизни, силе, дружбе)\n"
        "- напоминать о делах: 'Напомни через 5 минут поесть'\n"
        "- просто болтать, если скучно\n\n"
        "Фото я не вижу. Опиши словами.\n\n"
        "Могу научить тебя Тёмному импульсу... но лучше не надо."
    )

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

    # ===== НАПОМИНАЛКА =====
    if "напомни через" in text.lower():
        try:
            parts = text.lower().split("напомни через ")[1].split()
            number = int(parts[0])
            unit = parts[1]
            
            if "минут" in unit:
                seconds = number * 60
            elif "час" in unit:
                seconds = number * 3600
            elif "секунд" in unit:
                seconds = number
            else:
                await message.answer("Пиши: 'через 5 минут' или 'через 2 часа'")
                return
            
            task_text = " ".join(parts[2:]) if len(parts) > 2 else "что-то"
            asyncio.create_task(send_reminder(message.chat.id, task_text, seconds))
            await message.answer(f"Запомнил. Напомню через {number} {unit}.")
            return
        except:
            await message.answer("Пиши: 'Напомни через 5 минут поесть'")
            return

    # ===== ДИАЛОГ =====
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
    print("Майки (Манджиро Сано) запускается...")
    
    bot_info = await bot.get_me()
    print(f"Бот @{bot_info.username} готов к работе!")
    print("Нажми Ctrl+C для остановки")
    
    try:
        await dp.start_polling()
    except Exception as e:
        print(f"Критическая ошибка: {e}")
    finally:
        await bot.close()

if __name__ == "__main__":
    asyncio.run(main())