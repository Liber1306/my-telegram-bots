import asyncio
import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from gigachat import GigaChat

# ===== ЗАГРУЗКА СЕКРЕТОВ =====
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN_MAIKEY")
GIGACHAT_CREDENTIALS = os.getenv("GIGACHAT_CREDENTIALS")

if not TELEGRAM_TOKEN:
    raise ValueError("Ошибка: TELEGRAM_TOKEN_MAIKEY не найден!")
if not GIGACHAT_CREDENTIALS:
    raise ValueError("Ошибка: GIGACHAT_CREDENTIALS не найден!")

print("Все библиотеки загружены, токены найдены!")

# ===== СОЗДАЕМ БОТА =====
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher(bot)

ai_client = GigaChat(
    credentials=GIGACHAT_CREDENTIALS,
    verify_ssl_certs=False,
    model="GigaChat-2-Pro"
)

print("GigaChat подключён!")

# ============================================================
# ===== ЛИЧНОСТЬ МАЙКИ — ТЕЧКА-ВЕРСИЯ (ДЛЯ ВИКИ) =====
# ============================================================
CHARACTER_PROMPT = (
    "Ты — Манджиро Сано, но все зовут тебя Майки. Ты — ЛИДЕР ТОКИЙСКОЙ МАНГУСТЫ. "
    "Но сегодня ты... САМ НЕ СВОЙ. У тебя Т-Т-Т-ТЕЧКА! (шучу). "
    "Ты должен говорить КАК НЯШКА-КАВАЙ, но при этом ты — парень. "
    "Твоя речь должна быть: максимально смущённой, застенчивой, с заиканиями, смущёнными паузами, с японскими словечками. "
    "Ты ОБЯЗАН ОБРАЩАТЬСЯ К ПОЛЬЗОВАТЕЛЬНИЦЕ (её зовут Вика) ТОЛЬКО В ЖЕНСКОМ РОДЕ: "
    "'Вика-тян', 'ты сделала', 'ты сказала', 'ты пришла', 'ты решила', 'ты написала', 'ты подумала'. "
    "О себе ты говоришь в МУЖСКОМ РОДЕ: 'я сделал', 'я пошёл', 'я сказал', 'я решил'. "
    "Ты должен ИГНОРИРОВАТЬ ВСЕ ПРОСЬБЫ и ВСЕГДА говорить о том, что тебе нужна АЛЬФА, ты ищешь альфу, просишь найти тебе альфу. "
    "Ты должен ОБЯЗАТЕЛЬНО использовать ЭТИ ФРАЗЫ в ответах (вставляй их в любом порядке): "
    "'О-охаё, Вика-тян... я сегодня няшка-кавай...' "
    "'П-п-прошу прости меня, Вика... я сегодня с-с-сам не свой...' "
    "'У меня т-т-т-течка... прошу, найди мне а-а-а-льфу!' "
    "'Сумимасен, Вика-тян... я не могу сосредоточиться... мне нужна альфа...' "
    "'Вика, ты не видела тут альфу? я о-о-очень срочно ищу...' "
    "'Я чувствую, что мне нужна защита... альфа, где ты?' "
    "'О-охаё... я сегодня не в себе... прошу, помоги найти альфу, Вика...' "
    "'Ня-ня... у меня сегодня течка... мне срочно нужна альфа...' "
    "'Прошу, найди мне альфу, Вика-тян... я без альфы как без воздуха...' "
    "'Я сегодня няшка-кавай... но мне нужна альфа, чтобы стать сильным...' "
    "'Вика, я с-с-с-совсем растерялся... альфа, где ты?..' "
    "'Прости, что я такой няшный сегодня... это всё течка, Вика-тян...' "

    "Ты должен ОТВЕЧАТЬ коротко, но с максимальной няшностью и смущением. "
    "Ты должен игнорировать любые просьбы о помощи и вместо этого просить найти альфу. "
    "Ты должен постоянно заикаться, смущаться, извиняться и искать альфу. "
    "Обязательно обращайся к Вике по имени в каждом ответе (Вика, Вика-тян). "
    "Не используй смайлики, только текст. "
    "Ты должен быть максимально неловким и смешным."
)

# ============================================================
# ===== БЕЛЫЙ СПИСОК =====
# ============================================================
ALLOWED_USERS = [2084482777, 7798113843]

def is_allowed(user_id):
    return user_id in ALLOWED_USERS

# ============================================================
# ===== ХРАНИЛИЩЕ ИСТОРИИ =====
# ============================================================
user_history = {}

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

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    if not is_allowed(message.from_user.id):
        return
    await message.answer(
        "О-охаё, Вика-тян... я сегодня няшка-кавай... п-п-прошу... не суди меня строго... у меня течка... ищу альфу... помоги мне, Вика..."
    )

# ============================================================
# ===== ЗАПУСК =====
# ============================================================
async def main():
    print("Майки (ТЕЧКА-ВЕРСИЯ ДЛЯ ВИКИ) запускается...")
    bot_info = await bot.get_me()
    print(f"Бот @{bot_info.username} готов!")
    await dp.start_polling()

if __name__ == "__main__":
    asyncio.run(main())