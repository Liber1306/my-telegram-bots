import sqlite3
from datetime import datetime, timedelta

DB_NAME = "reminders.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            text TEXT,
            remind_time TEXT,
            repeat_type TEXT,
            sent INTEGER DEFAULT 0,
            last_sent TEXT
        )
    ''')
    conn.commit()
    conn.close()

def add_reminder(chat_id, text, remind_time, repeat_type="once"):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(
        "INSERT INTO reminders (chat_id, text, remind_time, repeat_type) VALUES (?, ?, ?, ?)",
        (chat_id, text, remind_time, repeat_type)
    )
    conn.commit()
    conn.close()

def get_due_reminders():
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(
        "SELECT id, chat_id, text, remind_time, repeat_type FROM reminders WHERE remind_time <= ? AND sent = 0",
        (now,)
    )
    rows = c.fetchall()
    conn.close()
    return rows

def mark_sent(reminder_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE reminders SET sent = 1 WHERE id = ?", (reminder_id,))
    conn.commit()
    conn.close()

def reset_daily_reminders():
    """Сбрасывает sent для ежедневных напоминаний"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE reminders SET sent = 0 WHERE repeat_type = 'daily'")
    conn.commit()
    conn.close()

def reset_weekly_reminders():
    """Сбрасывает sent для еженедельных напоминаний"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE reminders SET sent = 0 WHERE repeat_type = 'weekly'")
    conn.commit()
    conn.close()

def delete_reminder(reminder_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
    conn.commit()
    conn.close()

def get_all_reminders(chat_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, text, remind_time, repeat_type FROM reminders WHERE chat_id = ?", (chat_id,))
    rows = c.fetchall()
    conn.close()
    return rows