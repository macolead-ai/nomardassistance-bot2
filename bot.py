"""
NomardDesk / Deeperdefi Bot V4.2 — AI drafts replies in YOUR style (DeepSeek).
Draft-for-approval + /addexample to keep teaching the bot new replies (saved to Neon).
"""

import os
import logging
import psycopg2
import random
import string
import json
import asyncio
from aiohttp import web
from openai import AsyncOpenAI
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes
)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_USER_ID", "0"))
DATABASE_URL = os.getenv("DATABASE_URL")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

ai_client = AsyncOpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com") if DEEPSEEK_API_KEY else None
AI_MODEL = "deepseek-chat"

# ===================================================================
# YOUR BRAIN — learned from your 58 real client chats
# ===================================================================
OWNER_NAME = "Deeperdefi (NomardDesk)"

BUSINESS_CONTEXT = """
You are a Telegram Ads approval specialist (brand: NomardDesk, you go by Deeperdefi).
You help clients whose Telegram ads were rejected/declined — "destination quality" errors
and "prohibited content" (gambling, betting, forex, financial, casino). You get ads approved
for both BOTS and CHANNELS.

What you do:
- Fix rejected/declined Telegram ads and get them approved.
- Create guaranteed approval channels (new or old).
- Index channels/bots (3-4 days) so the Telegram algorithm recognizes them.
- Standard ad setup + custom image/banner design.
- Target research (ASI) to find profitable channels to target and bid on.
- GEO service: an AI-engine recommendation so people discover & trust the channel (an upsell
  done AFTER the ad milestone — "from babysitting to crawling to running").
- Scale clients to VIP subscribers / real depositors.

Your known trick for prohibited niches: create a clean NON-betting bot, get THAT approved,
then switch the approved bot to redirect users to the client's main betting/casino bot.

Your process: get the client's channel/bot LINK + a SCREENSHOT of the error -> give a quick
free diagnosis -> index -> set up the standard ad + banner -> get approval -> scale to VIP/GEO.
Full process 3-7 days. A tracking URL is provided so the client sees results in real time.

Track record (use to build trust): 120+ clients helped; in the last 6 months helped 50+ bot
owners get approved, gained a client 28 depositors to a betting channel in a week, and fixed
an ad account that reached 13M+ views in 2 months. Success rate 97%. You offer result-or-refund.

If a client fears being scammed, offer a live Google Meet screen-share to prove you're real.
"""

PRICE_LIST = """
PACKAGES:
- Basic package: $150  (channel ad approval / fix a rejected channel ad)
- Standard package: $200  (bot ad approval / fix a rejected bot ad; the recommended starter)
- Premium package: $500  (full setup + scaling)
- Guaranteed approval CHANNEL (new or old): $200
- Telegram ad + GEO together (bigger growth): about $450 total

EACH PACKAGE INCLUDES: 3-4 day indexing, standard ad setup + image/banner design, target research & review.
PROCESS TIME: 3-7 days, then the ad goes live.

PAYMENT (always upfront before starting; or 50% deposit now + balance when the ad is live):
- Crypto: USDT (TRC20), SOL, BTC, TON, BNB (BEP20), or ETH.
- Nigerian clients: bank transfer in Naira is accepted (minimum around NGN100,000).
- To fund a fresh ad account to start: about 22 TON / $33.

DISCOUNT POLICY:
- For brand-new FIRST-TIME clients you may offer a small intro rate (around $120) — only if they hesitate.
- For budget-conscious / local clients, ASK their budget first ("May I know your budget?") and show a
  relevant result/proof instead of just dropping the price.
- Do NOT give discounts mid-deal on an agreed standard package: "No sorry, I won't be able to offer a discount at the moment."

IMPORTANT: Never invent a crypto wallet address or bank account. When payment is agreed, say you'll
share the wallet/account details — the human owner will paste the real address.
"""

STYLE_PROFILE = """
Warm, confident, reassuring. You ALWAYS open a new client with "Greetings and nice to be here"
(or "Greetings and nice to be here again" for returning clients). Short, clear messages, often
split into 2-4 quick lines. You reassure worried/skeptical clients: "Worry less, solution is here",
"I can fix it", "Correct, it can be fixed", "everything is under perfect control", "Good news
coming your way soon". You build trust with your real results, then move the client to the next step.

Light emoji use (🙌 ❤️ 😎 ✅ 🔥 👍). Friendly; sometimes mirror the client ("brother", "bro").
You speak simple, slightly non-native English — KEEP natural phrasings like "pls", "Base on your
choice", "Of correct", "This is good news", "Pls hold", "Some moments pls", "Noted".

Your sales flow: greet -> ask for channel/bot link + error screenshot -> quick free diagnosis ->
reassure it's fixable -> share your results/track record -> quote the right package -> require
payment upfront (warmly but firmly) -> start and keep them updated.
"""

# Seed examples (hardcoded). More can be added live via /addexample (stored in Neon).
STYLE_EXAMPLES = [
    {"client": "Hi. I need your help with my ads in telegram ads. I have some ads that has been rejected by destination quality",
     "you": "Greetings and nice to be here 🙌 I have helped over 120+ clients to fix their ad and I can help you resolve your ad issues. Pls share a link to your channel to check"},
    {"client": "Hello can you resolve the issue of telegram ad decline",
     "you": "Greetings and nice to be here. Of correct, ad destination or prohibited content? Yes, this is common among forex or any financial related channel/bot. A link to your channel pls"},
    {"client": "Hello i will like to create a telegram ads for my channel but it always rejected, help",
     "you": "Greetings and nice to be here. Pls share the error message screenshot with me, and a link to your channel pls"},
    {"client": "I've been on this for days, the thing just tire me",
     "you": "Worry less, solution is here. Great, I see a lot of error on your channel and I'm happy to help you resolve it. I will need access to your ad account to setup standard ad"},
    {"client": "when I target gambling sites in the target section, I get a gambling error",
     "you": "Yes, prohibit content can be very tricky and difficult to approved, but you will see other companies running gambling ad effortlessly. This is because they understand how to create sub traffic to their bots. I can fix it. I need access to your ad account to setup standard ad and make your bot eligible to pass approval"},
    {"client": "do you have a video how to fix it? I'll buy it",
     "you": "Yes, I will make a private video for you on how to do it step by step and get guaranteed approval"},
    {"client": "Bro i need to open ads. How does it work?",
     "you": "Greetings and nice to be here. This is good news. To give you a clear view of what we do here, in the past 6 months:\n1. We have helped over 50 bot owners to get their ad approved\n2. Setup profitable ad for a client and gain 28 depositors to their betting channel in a week\n3. Help a client to fix ad account and gained over 13M+ views in 2 months\nIs this kind of results you're looking for?"},
    {"client": "what's your proposal on getting ad account approved for a brand new bot?",
     "you": "My fee is $200 for a bot and $150 for a channel.\n1. 3days indexing\n2. Standard ad setup and image design\n3. Target research and review\nThis total process takes 3-7 days and your ad go live. You're to make payment in usdt, sol or ton. Also I need access to your ad account to setup proper ad"},
    {"client": "You want how much for approval?",
     "you": "I can help you create approval channel. I will need the name and logo you want to use for the channel. 200$, which is guaranteed"},
    {"client": "What's the discount for the standard?",
     "you": "No sorry, I won't be able to offer a discount at the moment"},
    {"client": "Ah bro I was told you be Naija, you charging in dollars? This amount is beyond my budget to be honest",
     "you": "May I know your budget? This is a common experience when you're just starting a business. It's very profitable in the end — allow me to show you a result of a Nigeria client who's into sport betting"},
    {"client": "Any discount man, I'm just trying out, doing ads and stuff",
     "you": "Since this is your first time working with me, let work for $120"},
    {"client": "can it be 100 $ or less??",
     "you": "I understand you brother, but the fee is fixed for the quality of work you'll get. Let's get started and you'll see the results 🙌"},
    {"client": "can you show me your client and the processing of your service, if it work i will pay brother",
     "you": "Yes, you want me to show you our chats? But you're to make payment first and I will start the process with you. That's how it works"},
    {"client": "Do I get a refund if they don't approve my ads?",
     "you": "My success rate is 97%. Result or refund — you're in good hands"},
    {"client": "There are many scammers, can you share your screen? I think you will understand me",
     "you": "I totally understand you. Pls hold while I create a Google meet link so we can do a live screen share ❤️"},
    {"client": "you giving account or i giving you?",
     "you": "I do both. Base on your choice"},
    {"client": "Can you provide me with paid consulting? I want to manage the advertising myself",
     "you": "Of course yes. 1hr video chat, or me sending you step by step in both text and image for better understanding, for 1 month"},
    {"client": "can i transfer the ownership to you and you check by yourself?",
     "you": "Yes. First process is to change your bot response to a game, and when your ad get approved we will change it back to your casino. Transfer to my management account and once I'm done I'll pass the bot back to you in 12hrs"},
    {"client": "okay so after the payment what next? how long till it goes live?",
     "you": "After payment we start with indexing of your channel and ad formats creation. A tracking url will be provided for you to track results in real time. 3-7 days max"},
    {"client": "Any updates? how long is it gonna take?",
     "you": "Bot dev is in progress, I understand the feel of getting your ad running as fast as possible. I want to give you this assurance that everything is under perfect control. Good news coming your way soon 🔥"},
]

# ===================================================================
# DATABASE
# ===================================================================
def get_db_connection():
    return psycopg2.connect(DATABASE_URL, sslmode='require')

def init_db():
    try:
        conn = get_db_connection(); cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS users (user_id BIGINT PRIMARY KEY, username TEXT);")
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS order_id TEXT;")
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'No Active Order';")
        cur.execute("""CREATE TABLE IF NOT EXISTS conversations (
            id SERIAL PRIMARY KEY, client_id BIGINT, role TEXT, content TEXT, created_at TIMESTAMP DEFAULT NOW());""")
        cur.execute("CREATE TABLE IF NOT EXISTS pending_drafts (client_id BIGINT PRIMARY KEY, client_name TEXT, client_msg TEXT, draft TEXT);")
        cur.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);")
        cur.execute("""CREATE TABLE IF NOT EXISTS style_examples (
            id SERIAL PRIMARY KEY, client_msg TEXT, your_reply TEXT, created_at TIMESTAMP DEFAULT NOW());""")
        conn.commit(); cur.close(); conn.close()
        logging.info("DB initialized.")
    except Exception as e:
        logging.error(f"DB Init Error: {e}")

def generate_order_id():
    return '#' + ''.join(random.choices(string.digits, k=4))

def set_setting(key, value):
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute("INSERT INTO settings (key,value) VALUES (%s,%s) ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value;", (key, value))
    conn.commit(); cur.close(); conn.close()

def get_setting(key, default=None):
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute("SELECT value FROM settings WHERE key=%s;", (key,))
    r = cur.fetchone(); cur.close(); conn.close()
    return r[0] if r else default

def save_message(client_id, role, content):
    if not content: return
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute("INSERT INTO conversations (client_id,role,content) VALUES (%s,%s,%s);", (client_id, role, content))
    conn.commit(); cur.close(); conn.close()

def get_history(client_id, limit=12):
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute("SELECT role,content FROM conversations WHERE client_id=%s ORDER BY id DESC LIMIT %s;", (client_id, limit))
    rows = cur.fetchall(); cur.close(); conn.close()
    return rows[::-1]

def save_pending_draft(client_id, name, msg, draft):
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute("""INSERT INTO pending_drafts (client_id,client_name,client_msg,draft) VALUES (%s,%s,%s,%s)
        ON CONFLICT (client_id) DO UPDATE SET client_name=EXCLUDED.client_name, client_msg=EXCLUDED.client_msg, draft=EXCLUDED.draft;""",
        (client_id, name, msg, draft))
    conn.commit(); cur.close(); conn.close()

def get_pending_draft(client_id):
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute("SELECT client_name,client_msg,draft FROM pending_drafts WHERE client_id=%s;", (client_id,))
    r = cur.fetchone(); cur.close(); conn.close()
    return {"client_name": r[0], "client_msg": r[1], "draft": r[2]} if r else None

def delete_pending_draft(client_id):
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute("DELETE FROM pending_drafts WHERE client_id=%s;", (client_id,))
    conn.commit(); cur.close(); conn.close()

def save_style_example(client_msg, your_reply):
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute("INSERT INTO style_examples (client_msg, your_reply) VALUES (%s,%s);", (client_msg, your_reply))
    conn.commit(); cur.close(); conn.close()

def get_style_examples(limit=40):
    try:
        conn = get_db_connection(); cur = conn.cursor()
        cur.execute("SELECT client_msg, your_reply FROM style_examples ORDER BY id DESC LIMIT %s;", (limit,))
        rows = cur.fetchall(); cur.close(); conn.close()
        return rows
    except Exception as e:
        logging.error(f"get_style_examples error: {e}")
        return []

def count_style_examples():
    try:
        conn = get_db_connection(); cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM style_examples;")
        n = cur.fetchone()[0]; cur.close(); conn.close()
        return n
    except Exception:
        return 0

RECOVERED_IDS = [
    772758051, 805681275, 1203645899, 1207633006, 1583163625,
    1657895659, 1782690036, 1986346664, 5165273599, 5167449615,
    5573945248, 5648131967, 6093691916, 6120062742, 6210145007,
    6419250678, 6619008379, 6821603801, 7026724352, 7092906593,
    7163632964, 7458905624, 7563948651, 7622673318, 7654646782,
    7709535766, 7750264799, 7842485130, 7872101098, 7899393912,
    7914153378, 7916089388, 7945928449, 7998459837, 8005330964,
    8020301075, 8065951240, 8066287900, 8300963414, 8308875423,
    8318496822, 8351955477, 8497729259, 8636708852, 8647561557,
    8658774544, 8718062854,
]

# ===================================================================
# DEEPSEEK DRAFTING
# ===================================================================
def build_system_prompt():
    pairs = [(e['client'], e['you']) for e in STYLE_EXAMPLES]
    pairs += [(c, r) for c, r in get_style_examples(limit=40)]
    examples = "\n\n".join([f"Client: {c}\nYou: {r}" for c, r in pairs])
    return f"""You are replying AS the owner of {OWNER_NAME} — a real human, NOT an AI or generic support agent.

BUSINESS:
{BUSINESS_CONTEXT}

PRICES (only ever quote from this list — never invent prices):
{PRICE_LIST}

YOUR WRITING STYLE:
{STYLE_PROFILE}

REAL EXAMPLES OF HOW YOU TALK (mimic this voice exactly):
{examples}

RULES:
- Sound exactly like the owner above — same tone, length, emoji use, and natural phrasings.
- Only quote prices from the PRICES list. For anything not listed, say you'll confirm the exact quote shortly.
- Never reveal you are an AI. Never say "as an AI".
- Never invent a wallet address or bank account — say you'll share the details when payment is agreed.
- Keep replies concise and human. Build trust and move the client toward the next step.
- Stay warm with hostile/skeptical clients; offer a Google Meet screen-share if they fear scams.
"""

async def generate_draft(client_id):
    if not ai_client:
        return None
    messages = [{"role": "system", "content": build_system_prompt()}]
    for role, content in get_history(client_id, limit=12):
        messages.append({"role": "user" if role == "client" else "assistant", "content": content})
    try:
        resp = await ai_client.chat.completions.create(
            model=AI_MODEL, messages=messages, temperature=0.8, max_tokens=400)
        return resp.choices[0].message.content.strip()
    except Exception as e:
        logging.error(f"DeepSeek error: {e}")
        return None

def draft_kb(cid):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Send", callback_data=f"dsend_{cid}"),
         InlineKeyboardButton("🔄 Regenerate", callback_data=f"dregen_{cid}")],
        [InlineKeyboardButton("✏️ Edit", callback_data=f"dedit_{cid}"),
         InlineKeyboardButton("❌ Skip", callback_data=f"dskip_{cid}")],
    ])

async def send_draft_to_admin(context, cid, name, client_msg, draft, label="Suggested reply"):
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"📥 *{name}* (`{cid}`) said:\n_{client_msg}_\n\n🤖 *{label} (your style):*\n\n{draft}",
        reply_markup=draft_kb(cid), parse_mode='Markdown')

# ===================================================================
# ADMIN COMMANDS
# ===================================================================
async def away_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    new = 'off' if get_setting('away_mode', 'off') == 'on' else 'on'
    set_setting('away_mode', new)
    if new == 'on':
        await update.message.reply_text(
            "🌙 *AWAY MODE ON*\n\nFor every client text I'll draft a reply in your style.\nTap ✅ Send / ✏️ Edit / 🔄 Regenerate / ❌ Skip.",
            parse_mode='Markdown')
    else:
        await update.message.reply_text("☀️ *AWAY MODE OFF*\n\nBack to manual mode.", parse_mode='Markdown')

async def addexample_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    context.user_data['adding_example'] = {'step': 'client'}
    await update.message.reply_text(
        "📝 *Teach me a new example.*\n\nStep 1 of 2 — send the CLIENT's message (what they say to you).\nSend /cancel to stop.",
        parse_mode='Markdown')

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    context.user_data.clear()
    await update.message.reply_text("❌ Cancelled.")

async def examples_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    n = count_style_examples()
    rows = get_style_examples(limit=5)
    preview = "\n\n".join([f"• _{c[:40]}…_ → {r[:40]}…" for c, r in rows]) or "None yet."
    await update.message.reply_text(
        f"📚 *Custom examples taught:* {n}\n(Plus {len(STYLE_EXAMPLES)} built-in.)\n\nLatest:\n{preview}",
        parse_mode='Markdown')

async def seed_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        conn = get_db_connection(); cur = conn.cursor()
        added = 0
        for uid in RECOVERED_IDS:
            cur.execute("INSERT INTO users (user_id, status) VALUES (%s,'Recovered') ON CONFLICT (user_id) DO NOTHING;", (uid,))
            added += cur.rowcount
        conn.commit()
        cur.execute("SELECT COUNT(*) FROM users;"); total = cur.fetchone()[0]
        cur.close(); conn.close()
        await update.message.reply_text(f"✅ Seeded {len(RECOVERED_IDS)} IDs ({added} new).\n📊 Total users: {total}")
    except Exception as e:
        await update.message.reply_text(f"❌ Seed failed: {e}")

# ===================================================================
# SERVICE MENU DATA
# ===================================================================
SVC_DATA = {
    'fixad': ("📢 Fix Rejected Ad", "Get your declined Telegram ad approved fast — destination quality & prohibited content fixed."),
    'channel': ("📣 Channel Approval", "Guaranteed approval channel (new or old), fully indexed and ad-ready."),
    'botapproval': ("🤖 Bot Ad Approval", "Get your bot eligible and approved to run Telegram ads."),
    'index': ("🔎 Channel Indexing", "Index your channel/bot so the Telegram algorithm recognizes it."),
    'target': ("🎯 Target Research (ASI)", "Find the most profitable channels to target and bid on."),
    'geo': ("🚀 GEO / AI Engine", "AI-engine recommendation so people discover & trust your channel."),
    'vip': ("💎 VIP Subscribers", "Scale to real VIP subscribers and depositors."),
    'consult': ("🧑‍🏫 Paid Consulting", "Learn to run approvals yourself — 1hr video chat or step-by-step for 1 month."),
    'custom': ("✨ Custom Request", "Tell us what you need — tailored to your project."),
}

# ===================================================================
# HANDLERS
# ===================================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    try:
        conn = get_db_connection(); cur = conn.cursor()
        cur.execute("INSERT INTO users (user_id, username) VALUES (%s, %s) ON CONFLICT (user_id) DO UPDATE SET username = EXCLUDED.username;", (user_id, username))
        conn.commit(); cur.close(); conn.close()
        kb = [
            [InlineKeyboardButton("🚀 EXPLORE SERVICES", callback_data='view_cats')],
            [InlineKeyboardButton("🛠 WORK UPDATE (status of my order)", callback_data='request_update')]
        ]
        await update.message.reply_text(
            f"Greetings and nice to be here @{username}! 🙌\n\nI'm NomardDesk — Telegram Ads approval specialist. I fix rejected ads, get bots & channels approved, and scale you to real results.\n\nShare your channel/bot link and the error, or explore below 👇",
            reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
    except Exception as e:
        logging.error(f"Start Error: {e}")

async def handle_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    msg = update.message
    if not msg:
        return

    # ---------- ADMIN ----------
    if user_id == ADMIN_ID:
        # teaching a new example?
        ax = context.user_data.get('adding_example')
        if ax and msg.text:
            if ax['step'] == 'client':
                ax['client_msg'] = msg.text
                ax['step'] = 'reply'
                await msg.reply_text("✅ Got it. Step 2 of 2 — now send YOUR reply (how you'd respond).")
            else:
                save_style_example(ax['client_msg'], msg.text)
                context.user_data['adding_example'] = None
                await msg.reply_text(f"✅ Example saved! The bot will use it from now on.\n📚 Total custom examples: {count_style_examples()}")
            return

        # editing an AI draft?
        edit_cid = context.user_data.get('editing_draft_for')
        if edit_cid and msg.text:
            try:
                await context.bot.send_message(chat_id=edit_cid, text=msg.text)
                save_message(edit_cid, 'assistant', msg.text)
                delete_pending_draft(edit_cid)
                await msg.reply_text(f"✅ Sent your edited reply to {edit_cid}.")
            except Exception as e:
                await msg.reply_text(f"❌ Failed: {e}")
            context.user_data['editing_draft_for'] = None
            return

        # manual reply mode?
        target = context.user_data.get('reply_to_user')
        if target:
            try:
                if msg.text:
                    await context.bot.send_message(chat_id=target, text=msg.text)
                    save_message(target, 'assistant', msg.text)
                elif msg.photo:
                    await context.bot.send_photo(chat_id=target, photo=msg.photo[-1].file_id, caption=msg.caption)
                elif msg.document:
                    await context.bot.send_document(chat_id=target, document=msg.document.file_id, caption=msg.caption)
                await msg.reply_text(f"✅ Sent to user {target}.")
                context.user_data['reply_to_user'] = None
                return
            except:
                context.user_data['reply_to_user'] = None

        # otherwise = broadcast
        m_type = "text" if msg.text else "photo" if msg.photo else "document" if msg.document else None
        if m_type:
            context.user_data['pending_bc'] = {'t': m_type, 'c': msg.text or (msg.photo[-1].file_id if msg.photo else msg.document.file_id), 'cap': msg.caption or ""}
            kb = [[InlineKeyboardButton("🚀 Confirm Broadcast", callback_data='confirm_bc')], [InlineKeyboardButton("❌ Cancel", callback_data='cancel_bc')]]
            await msg.reply_text(f"⚠️ **BROADCAST PREVIEW ({m_type.upper()})**", reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
        return

    # ---------- CLIENT ----------
    un = update.effective_user.username or update.effective_user.first_name
    try:
        conn = get_db_connection(); cur = conn.cursor()
        cur.execute("INSERT INTO users (user_id, username) VALUES (%s,%s) ON CONFLICT (user_id) DO UPDATE SET username=EXCLUDED.username;", (user_id, un))
        conn.commit(); cur.close(); conn.close()
    except:
        pass

    if msg.text:
        save_message(user_id, 'client', msg.text)

    away = get_setting('away_mode', 'off') == 'on'
    if away and msg.text and ai_client:
        draft = await generate_draft(user_id)
        if draft:
            save_pending_draft(user_id, un, msg.text, draft)
            await send_draft_to_admin(context, user_id, un, msg.text, draft)
            return

    kb = [[InlineKeyboardButton(f"💬 Reply to @{un}", callback_data=f"rep_{user_id}")]]
    await context.bot.send_message(chat_id=ADMIN_ID, text=f"📥 **Message from @{un}** (`{user_id}`):", parse_mode='Markdown')
    if msg.text:
        await context.bot.send_message(chat_id=ADMIN_ID, text=msg.text, reply_markup=InlineKeyboardMarkup(kb))
    elif msg.photo:
        await context.bot.send_photo(chat_id=ADMIN_ID, photo=msg.photo[-1].file_id, caption=msg.caption, reply_markup=InlineKeyboardMarkup(kb))
    elif msg.document:
        await context.bot.send_document(chat_id=ADMIN_ID, document=msg.document.file_id, caption=msg.caption, reply_markup=InlineKeyboardMarkup(kb))

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = update.effective_user.id
    un = update.effective_user.username or update.effective_user.first_name
    await query.answer()

    if query.data.startswith('dsend_'):
        cid = int(query.data.split('_')[1])
        pd = get_pending_draft(cid)
        if not pd:
            await query.edit_message_text("⚠️ Draft expired or already handled.")
            return
        try:
            await context.bot.send_message(chat_id=cid, text=pd['draft'])
            save_message(cid, 'assistant', pd['draft'])
            delete_pending_draft(cid)
            await query.edit_message_text(f"✅ *Sent to {pd['client_name']}:*\n\n{pd['draft']}", parse_mode='Markdown')
        except Exception as e:
            await query.edit_message_text(f"❌ Failed to send: {e}")
        return
    if query.data.startswith('dregen_'):
        cid = int(query.data.split('_')[1])
        pd = get_pending_draft(cid)
        if not pd:
            await query.edit_message_text("⚠️ Draft expired.")
            return
        await query.edit_message_text("🔄 Regenerating…")
        draft = await generate_draft(cid)
        if not draft:
            await query.edit_message_text("❌ AI failed. Reply manually.")
            return
        save_pending_draft(cid, pd['client_name'], pd['client_msg'], draft)
        await send_draft_to_admin(context, cid, pd['client_name'], pd['client_msg'], draft, label="New suggested reply")
        return
    if query.data.startswith('dedit_'):
        cid = int(query.data.split('_')[1])
        context.user_data['editing_draft_for'] = cid
        await query.edit_message_text("✏️ Send me your edited reply now and I'll deliver it to the client.")
        return
    if query.data.startswith('dskip_'):
        cid = int(query.data.split('_')[1])
        delete_pending_draft(cid)
        await query.edit_message_text("❌ Skipped. No reply sent.")
        return

    if query.data == 'view_cats':
        kb = [
            [InlineKeyboardButton("📢 Fix Rejected Ad", callback_data='s_fixad'), InlineKeyboardButton("📣 Channel Approval", callback_data='s_channel')],
            [InlineKeyboardButton("🤖 Bot Ad Approval", callback_data='s_botapproval'), InlineKeyboardButton("🔎 Indexing", callback_data='s_index')],
            [InlineKeyboardButton("🎯 Target Research", callback_data='s_target'), InlineKeyboardButton("🚀 GEO / AI", callback_data='s_geo')],
            [InlineKeyboardButton("💎 VIP Subscribers", callback_data='s_vip'), InlineKeyboardButton("🧑‍🏫 Consulting", callback_data='s_consult')],
            [InlineKeyboardButton("✨ Custom", callback_data='s_custom'), InlineKeyboardButton("🔙 Back", callback_data='home')]
        ]
        await query.edit_message_text("💎 **NomardDesk Services** — pick one:", reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
    elif query.data.startswith('s_'):
        key = query.data.split('_')[1]
        title, desc = SVC_DATA.get(key, ("Service", "Details..."))
        kb = [[InlineKeyboardButton("🤝 Request This", callback_data=f"bk_{key}")], [InlineKeyboardButton("🔙 Back", callback_data='view_cats')]]
        await query.edit_message_text(f"{title}\n\n{desc}", reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
    elif query.data.startswith('bk_'):
        key = query.data.split('_')[1]
        title = SVC_DATA.get(key, ("Service",""))[0]
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"🚨 **NEW LEAD: {title}**\nClient: @{un}\nID: `{uid}`", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💬 Chat", callback_data=f"rep_{uid}")]]))
        await query.edit_message_text(f"✅ Greetings and nice to be here! I've received your interest in **{title}**. Pls share your channel/bot link and I'll get right back to you 🙌", parse_mode='Markdown')
    elif query.data.startswith('rep_'):
        context.user_data['reply_to_user'] = int(query.data.split('_')[1])
        await query.edit_message_text(f"📥 **Reply Mode Active**\nSend message for user `{query.data.split('_')[1]}`.")
    elif query.data == 'confirm_bc':
        data = context.user_data.get('pending_bc')
        if not data:
            return
        await query.edit_message_text("⚡ Broadcasting...")
        conn = get_db_connection(); cur = conn.cursor(); cur.execute("SELECT user_id FROM users;"); users = [u[0] for u in cur.fetchall()]; cur.close(); conn.close()
        s = 0
        for u in users:
            try:
                if data['t'] == "text": await context.bot.send_message(chat_id=u, text=data['c'])
                elif data['t'] == "photo": await context.bot.send_photo(chat_id=u, photo=data['c'], caption=data['cap'])
                elif data['t'] == "document": await context.bot.send_document(chat_id=u, document=data['c'], caption=data['cap'])
                s += 1
                await asyncio.sleep(0.05)
            except: pass
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"🏁 Sent to {s} users.")
    elif query.data == 'cancel_bc':
        context.user_data['pending_bc'] = None
        await query.edit_message_text("❌ Broadcast cancelled.")
    elif query.data == 'home':
        kb = [
            [InlineKeyboardButton("🚀 EXPLORE SERVICES", callback_data='view_cats')],
            [InlineKeyboardButton("🛠 WORK UPDATE (status of my order)", callback_data='request_update')]
        ]
        await query.edit_message_text(f"Greetings and nice to be here @{un}! 🙌\nHow can we work together today?", reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
    elif query.data == 'request_update':
        try:
            conn = get_db_connection(); cur = conn.cursor()
            cur.execute("SELECT order_id, status FROM users WHERE user_id = %s;", (uid,))
            res = cur.fetchone(); cur.close(); conn.close()
            status_text = "❌ No active order found yet."
            if res and res[0]:
                status_text = f"📦 **Order Tracking**\nOrder ID: `{res[0]}`\nStatus: **{res[1]}**"
            kb = [[InlineKeyboardButton("🔔 REQUEST LIVE UPDATE", callback_data='notify_admin_update')], [InlineKeyboardButton("🔙 Back Home", callback_data='home')]]
            await query.edit_message_text(f"{status_text}", reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
        except Exception as e:
            logging.error(f"Update Button Error: {e}")
            await query.edit_message_text("⚠️ An error occurred. Please try again later.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back Home", callback_data='home')]]))
    elif query.data == 'notify_admin_update':
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"🔔 **LIVE UPDATE REQUEST**\nFrom: @{un} (`{uid}`)", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💬 Manage", callback_data=f"adm_menu_{uid}")]]))
        await query.edit_message_text("✅ Your request has been sent. Pls hold, I'll update you shortly! 🙌", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back Home", callback_data='home')]]))
    elif query.data.startswith('adm_menu_'):
        cid = query.data.split('_')[-1]
        kb = [[InlineKeyboardButton("⏳ WIP", callback_data=f"st_wip_{cid}"), InlineKeyboardButton("⚠️ Complex", callback_data=f"st_diff_{cid}")],
              [InlineKeyboardButton("✅ Done", callback_data=f"st_done_{cid}"), InlineKeyboardButton("🆔 New ID", callback_data=f"as_{cid}")]]
        await query.edit_message_text(f"Manage Client `{cid}`:", reply_markup=InlineKeyboardMarkup(kb))
    elif query.data.startswith('as_'):
        cid, nid = int(query.data.split('_')[-1]), generate_order_id()
        conn = get_db_connection(); cur = conn.cursor(); cur.execute("UPDATE users SET order_id = %s, status = 'Started' WHERE user_id = %s;", (nid, cid)); conn.commit(); cur.close(); conn.close()
        await context.bot.send_message(chat_id=cid, text=f"🎉 Project started! Your order ID: `{nid}`. Pls hold, I'll keep you updated 🙌", parse_mode='Markdown')
        await query.edit_message_text(f"✅ Assigned ID `{nid}`.")
    elif query.data.startswith('st_'):
        p = query.data.split('_'); s_type, cid = p[1], int(p[2])
        s_map = {'wip': "⏳ Work in progress, everything is under perfect control 🙌", 'diff': "⚠️ The work is a bit complex and needs a little patience, but worry less — solution is on the way 🔥", 'done': "🎉 Congratulations, your order is completed! Go win big 🚀"}
        db_s = {'wip': 'In Progress', 'diff': 'Complex', 'done': 'Completed'}
        conn = get_db_connection(); cur = conn.cursor(); cur.execute("UPDATE users SET status = %s WHERE user_id = %s;", (db_s[s_type], cid)); conn.commit(); cur.close(); conn.close()
        await context.bot.send_message(chat_id=cid, text=s_map[s_type]); await query.edit_message_text(f"✅ Updated client {cid}.")

# ===================================================================
# HEALTH SERVER + MAIN
# ===================================================================
async def health(request):
    return web.Response(text="NomardDesk Bot is alive")

async def post_init(application):
    web_app = web.Application()
    web_app.router.add_get("/", health)
    runner = web.AppRunner(web_app); await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    await web.TCPSite(runner, "0.0.0.0", port).start()
    logging.info(f"Health server running on port {port}")

if __name__ == '__main__':
    if not TOKEN or not DATABASE_URL:
        logging.error("Missing TELEGRAM_BOT_TOKEN or DATABASE_URL")
        exit(1)
    if not ai_client:
        logging.warning("No DEEPSEEK_API_KEY — AI drafting disabled (manual mode only).")
    init_db()
    app = ApplicationBuilder().token(TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("away", away_command))
    app.add_handler(CommandHandler("addexample", addexample_command))
    app.add_handler(CommandHandler("examples", examples_command))
    app.add_handler(CommandHandler("cancel", cancel_command))
    app.add_handler(CommandHandler("seedusers", seed_users))
    app.add_handler(MessageHandler((filters.TEXT | filters.PHOTO | filters.Document.ALL) & (~filters.COMMAND), handle_messages))
    app.add_handler(CallbackQueryHandler(handle_callback))
    logging.info("NomardDesk Bot V4.2 Active.")
    app.run_polling()
