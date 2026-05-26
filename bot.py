import os
import json
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from aiohttp import web
from openai import AsyncOpenAI
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ChatMemberHandler, ContextTypes, ConversationHandler, filters
)

# ---------- CONFIG ----------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
PORT = int(os.environ.get("PORT", 10000))
DATA_FILE = "channels.json"

# Use DeepSeek if available, else OpenAI
if DEEPSEEK_API_KEY:
    ai_client = AsyncOpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
    AI_MODEL = "deepseek-chat"
    AI_PROVIDER = "DeepSeek"
elif OPENAI_API_KEY:
    ai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    AI_MODEL = "gpt-4o-mini"
    AI_PROVIDER = "OpenAI"
else:
    ai_client = None
    AI_MODEL = None
    AI_PROVIDER = None

POST_CATEGORIES = [
    ("why", "Explain WHY this topic matters. Make it motivating and emotional. 2-3 short paragraphs."),
    ("important", "Share an IMPORTANT key concept or rule everyone must know about this topic. Be educational."),
    ("history", "Tell a short HISTORICAL fact or background story about this topic. Make it engaging."),
    ("fun fact", "Share a surprising or FUN FACT about this topic. Make people say 'wow'."),
    ("quiz", "Create a QUIZ question with 4 options (A, B, C, D) and reveal the correct answer at the end with explanation."),
    ("tips", "Give 3-5 practical TIPS related to this topic. Use bullet points or numbered list."),
]

POSTS_PER_DAY = 12
INTERVAL_MINUTES = (14 * 60) // POSTS_PER_DAY  # 12 posts spread across ~14 active hours = every 70 min
ACTIVE_START_HOUR = 8   # 8 AM UTC
ACTIVE_END_HOUR = 22    # 10 PM UTC

# ---------- STATES ----------
WAITING_TOPIC = 1

# ---------- LOGGING ----------
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------- STORAGE ----------
def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2, default=str)

def get_user_channels(user_id):
    data = load_data()
    return data.get(str(user_id), [])

def add_channel(user_id, chat_id, title):
    data = load_data()
    uid = str(user_id)
    if uid not in data:
        data[uid] = []
    for ch in data[uid]:
        if ch["id"] == chat_id:
            ch["title"] = title
            save_data(data)
            return
    data[uid].append({
        "id": chat_id,
        "title": title,
        "topic": None,
        "category_index": 0,
        "next_post_time": None,
        "active": False,
        "posts_today": 0,
        "last_post_date": None,
    })
    save_data(data)

def remove_channel(user_id, chat_id):
    data = load_data()
    uid = str(user_id)
    if uid in data:
        data[uid] = [c for c in data[uid] if c["id"] != chat_id]
        save_data(data)

def update_channel(user_id, chat_id, **updates):
    data = load_data()
    uid = str(user_id)
    if uid in data:
        for ch in data[uid]:
            if ch["id"] == chat_id:
                ch.update(updates)
                save_data(data)
                return ch
    return None

def find_channel(user_id, chat_id):
    for ch in get_user_channels(user_id):
        if ch["id"] == chat_id:
            return ch
    return None

# ---------- AI ----------
async def generate_post(topic: str, category: str, instructions: str) -> str:
    if not ai_client:
        return f"⚠️ No AI API key configured. Topic: {topic} | Category: {category}"
    system_prompt = (
        f"You are a Telegram channel content creator. The channel topic is: '{topic}'. "
        f"Write engaging Telegram posts. Use emojis. Keep posts under 800 characters. "
        f"Do not include hashtags unless natural. Do not greet or sign off — just deliver the content."
    )
    user_prompt = f"Write a Telegram post for category: {category.upper()}.\n\n{instructions}\n\nTopic: {topic}"
    try:
        resp = await ai_client.chat.completions.create(
            model=AI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.9,
            max_tokens=600,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"AI error: {e}")
        return None

# ---------- HANDLERS ----------
def main_menu(user_id):
    channels = get_user_channels(user_id)
    kb = []
    for ch in channels:
        status = "🟢" if ch.get("active") else "⚪"
        topic_set = "✏️" if ch.get("topic") else "❓"
        kb.append([InlineKeyboardButton(f"{status}{topic_set} {ch['title']}", callback_data=f"channel:{ch['id']}")])
    kb.append([InlineKeyboardButton("➕ Add Channel", callback_da
