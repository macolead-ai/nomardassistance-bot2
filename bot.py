"""
NomardDesk Bot V3.5 — with /importusers recovery, broadcast, and Render health server.
"""

import os
import logging
import psycopg2
import random
import string
import json
import asyncio
from aiohttp import web
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes
)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_USER_ID", "0"))
DATABASE_URL = os.getenv("DATABASE_URL")

# ===== DATABASE =====
def get_db_connection():
    return psycopg2.connect(DATABASE_URL, sslmode='require')

def init_db():
    try:
        conn = get_db_connection(); cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS users (user_id BIGINT PRIMARY KEY, username TEXT);")
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS order_id TEXT;")
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'No Active Order';")
        conn.commit(); cur.close(); conn.close()
        logging.info("DB initialized.")
    except Exception as e:
        logging.error(f"DB Init Error: {e}")

def generate_order_id():
    return '#' + ''.join(random.choices(string.digits, k=4))

# ===== IMPORT RECOVERED USERS =====
async def import_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not update.message.document:
        await update.message.reply_text("Attach users_backup.json with caption /importusers")
        return
    try:
        file = await context.bot.get_file(update.message.document.file_id)
        data_bytes = await file.download_as_bytearray()
        users = json.loads(data_bytes.decode())
        conn = get_db_connection(); cur = conn.cursor()
        count = 0
        for u in users:
            cur.execute("""
                INSERT INTO users (user_id, username, order_id, status)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE SET status = EXCLUDED.status;
            """, (u["user_id"], u.get("username"), u.get("order_id"), u.get("status") or "Recovered"))
            count += 1
        conn.commit(); cur.close(); conn.close()
        await update.message.reply_text(f"✅ Imported {count} users into the database.")
    except Exception as e:
        await update.message.reply_text(f"❌ Import failed: {e}")

# ===== SERVICE DATA =====
SVC_DATA = {
    'botdev': ("🤖 Bot Development", "Custom Telegram, Discord, and trading bots built for speed and reliability."),
    'n8n': ("⚡ n8n Automation", "Professional business automation to connect your apps and scale your workflow."),
    'fbmon': ("💰 FB Monetization", "Get your Facebook pages ready for revenue and scale your earnings."),
    'smm': ("📱 Social Media Mgmt", "Full-scale management and content strategy for your brand's social presence."),
    'audit': ("📝 Token/Solidity Audit", "High-security smart contract audits to ensure safety and investor trust."),
    'tokendev': ("🪙 Token Development", "Creation of custom tokens on Ethereum, Solana, BSC, and more."),
    'seogeo': ("🚀 SEO and Geo", "Search engine optimization and local geo-targeting to boost visibility."),
    'mkt': ("🔥 Token/Presale Marketing", "Strategic marketing campaigns to hype and sell out your presale."),
    'web': ("🌐 Website Dev/Design", "Modern, responsive websites and high-converting landing pages."),
    'pump': ("📊 Token Ranking/Pump", "Trending services for DexTools, CMC, and token visibility boosts."),
    'tgad': ("📢 Telegram Ad Fix/Mgmt", "Fixing ad account issues and professional Telegram ad management."),
    'mini': ("📱 Mini App Dev", "Interactive Telegram Mini Apps (TWA) with custom functionality."),
    'custom': ("✨ Custom Service", "A specialized request tailored to your unique business needs.")
}

# ===== HANDLERS =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    try:
        conn = get_db_connection(); cur = conn.cursor()
        cur.execute("INSERT INTO users (user_id, username) VALUES (%s, %s) ON CONFLICT (user_id) DO UPDATE SET username = EXCLUDED.username;", (user_id, username))
        conn.commit(); cur.close(); conn.close()
        kb = [
            [InlineKeyboardButton("🚀 EXPLORE SERVICES", callback_data='view_cats')],
            [InlineKeyboardButton("🛠 WORK UPDATE (What's the current status of my order?)", callback_data='request_update')]
        ]
        await update.message.reply_text(
            f"Welcome to **NomardDesk** @{username}!\n\nHow can we help your business grow today?\n\nUse the menu below to explore our services or check your project status.",
            reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown'
        )
    except Exception as e: logging.error(f"Start Error: {e}")

async def handle_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    msg = update.message
    if not msg: return
    if user_id == ADMIN_ID:
        target = context.user_data.get('reply_to_user')
        if target:
            try:
                if msg.text: await context.bot.send_message(chat_id=target, text=msg.text)
                elif msg.photo: await context.bot.send_photo(chat_id=target, photo=msg.photo[-1].file_id, caption=msg.caption)
                elif msg.document: await context.bot.send_document(chat_id=target, document=msg.document.file_id, caption=msg.caption)
                await msg.reply_text(f"✅ NomardDesk: Sent to user {target}.")
                context.user_data['reply_to_user'] = None
                return
            except: context.user_data['reply_to_user'] = None
        m_type = "text" if msg.text else "photo" if msg.photo else "document" if msg.document else None
        if m_type:
            context.user_data['pending_bc'] = {'t': m_type, 'c': msg.text or (msg.photo[-1].file_id if msg.photo else msg.document.file_id), 'cap': msg.caption or ""}
            kb = [[InlineKeyboardButton("🚀 Confirm Broadcast", callback_data='confirm_bc')], [InlineKeyboardButton("❌ Cancel", callback_data='cancel_bc')]]
            await msg.reply_text(f"⚠️ **BROADCAST PREVIEW ({m_type.upper()})**", reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
    else:
        un = update.effective_user.username or update.effective_user.first_name
        kb = [[InlineKeyboardButton(f"💬 Reply to @{un}", callback_data=f"rep_{user_id}")]]
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"📥 **Message from @{un}** (`{user_id}`):")
        if msg.text: await context.bot.send_message(chat_id=ADMIN_ID, text=msg.text, reply_markup=InlineKeyboardMarkup(kb))
        elif msg.photo: await context.bot.send_photo(chat_id=ADMIN_ID, photo=msg.photo[-1].file_id, caption=msg.caption, reply_markup=InlineKeyboardMarkup(kb))
        elif msg.document: await context.bot.send_document(chat_id=ADMIN_ID, document=msg.document.file_id, caption=msg.caption, reply_markup=InlineKeyboardMarkup(kb))

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = update.effective_user.id
    un = update.effective_user.username or update.effective_user.first_name
    await query.answer()
    if query.data == 'view_cats':
        kb = [
            [InlineKeyboardButton("💻 Development", callback_data='cat_dev'), InlineKeyboardButton("⚙ Automation/Ads", callback_data='cat_ops')],
            [InlineKeyboardButton("📈 Marketing & SEO", callback_data='cat_mkt'), InlineKeyboardButton("🪙 Web3 & Token", callback_data='cat_web3')],
            [InlineKeyboardButton("✨ Custom Service", callback_data='s_custom')],
            [InlineKeyboardButton("🔙 Back Home", callback_data='home')]
        ]
        await query.edit_message_text("💎 **NomardDesk Service Categories**", reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
    elif query.data == 'cat_dev':
        kb = [[InlineKeyboardButton("🤖 Bot Dev", callback_data='s_botdev'), InlineKeyboardButton("🌐 Website Dev", callback_data='s_web')],
              [InlineKeyboardButton("📱 Mini App Dev", callback_data='s_mini'), InlineKeyboardButton("🔙 Back", callback_data='view_cats')]]
        await query.edit_message_text("💻 **Development Services**", reply_markup=InlineKeyboardMarkup(kb))
    elif query.data == 'cat_ops':
        kb = [[InlineKeyboardButton("⚡ n8n Automation", callback_data='s_n8n'), InlineKeyboardButton("💰 FB Monetization", callback_data='s_fbmon')],
              [InlineKeyboardButton("📢 Telegram Ad Mgmt", callback_data='s_tgad'), InlineKeyboardButton("🔙 Back", callback_data='view_cats')]]
        await query.edit_message_text("⚙ **Automation & Management**", reply_markup=InlineKeyboardMarkup(kb))
    elif query.data == 'cat_mkt':
        kb = [[InlineKeyboardButton("🚀 SEO and Geo", callback_data='s_seogeo'), InlineKeyboardButton("📱 Social Media Mgmt", callback_data='s_smm')],
              [InlineKeyboardButton("📊 Ranking/Pump", callback_data='s_pump'), InlineKeyboardButton("🔙 Back", callback_data='view_cats')]]
        await query.edit_message_text("📈 **Marketing & SEO**", reply_markup=InlineKeyboardMarkup(kb))
    elif query.data == 'cat_web3':
        kb = [[InlineKeyboardButton("🪙 Token Dev", callback_data='s_tokendev'), InlineKeyboardButton("📝 Security Audit", callback_data='s_audit')],
              [InlineKeyboardButton("🔥 Presale Marketing", callback_data='s_mkt'), InlineKeyboardButton("🔙 Back", callback_data='view_cats')]]
        await query.edit_message_text("🪙 **Web3 & Token Services**", reply_markup=InlineKeyboardMarkup(kb))
    elif query.data.startswith('s_'):
        key = query.data.split('_')[1]
        title, desc = SVC_DATA.get(key, ("Service", "Details..."))
        kb = [[InlineKeyboardButton(f"🤝 Book {title.split(' ')[1]}", callback_data=f"bk_{key}")], [InlineKeyboardButton("🔙 Back", callback_data='view_cats')]]
        await query.edit_message_text(f"{title}\n\n{desc}", reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
    elif query.data.startswith('bk_'):
        key = query.data.split('_')[1]
        title = SVC_DATA[key][0]
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"🚨 **NEW LEAD: {title}**\nClient: @{un}\nID: `{uid}`", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💬 Chat", callback_data=f"rep_{uid}")]]))
        await query.edit_message_text(f"✅ NomardDesk has received your interest in **{title}**. We will contact you shortly!", parse_mode='Markdown')
    elif query.data.startswith('rep_'):
        context.user_data['reply_to_user'] = int(query.data.split('_')[1])
        await query.edit_message_text(f"📥 **Reply Mode Active**\nSend message for user `{query.data.split('_')[1]}`.")
    elif query.data == 'confirm_bc':
        data = context.user_data.get('pending_bc')
        if not data: return
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
            [InlineKeyboardButton("🛠 WORK UPDATE (What's the current status of my order?)", callback_data='request_update')]
        ]
        await query.edit_message_text(f"Welcome to **NomardDesk** @{un}!\n\nHow can we help you today?", reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
    elif query.data == 'request_update':
        try:
            conn = get_db_connection(); cur = conn.cursor()
            cur.execute("SELECT order_id, status FROM users WHERE user_id = %s;", (uid,))
            res = cur.fetchone(); cur.close(); conn.close()
            status_text = "❌ No active NomardDesk order found."
            if res and res[0]:
                status_text = f"📦 **NomardDesk Order Tracking**\nOrder ID: `{res[0]}`\nStatus: **{res[1]}**"
            kb = [[InlineKeyboardButton("🔔 REQUEST LIVE UPDATE", callback_data='notify_admin_update')], [InlineKeyboardButton("🔙 Back Home", callback_data='home')]]
            await query.edit_message_text(f"{status_text}\n\n_If you need more details, click 'Request Live Update' and NomardDesk will message you._", reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
        except Exception as e:
            logging.error(f"Update Button Error: {e}")
            await query.edit_message_text("⚠️ An error occurred. Please try again later.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back Home", callback_data='home')]]))
    elif query.data == 'notify_admin_update':
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"🔔 **LIVE UPDATE REQUEST**\nFrom: @{un} (`{uid}`)", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💬 Manage", callback_data=f"adm_menu_{uid}")]]))
        await query.edit_message_text("✅ Your request for a live update has been sent. Please stay tuned!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back Home", callback_data='home')]]))
    elif query.data.startswith('adm_menu_'):
        cid = query.data.split('_')[-1]
        kb = [[InlineKeyboardButton("⏳ WIP", callback_data=f"st_wip_{cid}"), InlineKeyboardButton("⚠️ Complex", callback_data=f"st_diff_{cid}")],
              [InlineKeyboardButton("✅ Done", callback_data=f"st_done_{cid}"), InlineKeyboardButton("🆔 New ID", callback_data=f"as_{cid}")]]
        await query.edit_message_text(f"Manage Client `{cid}`:", reply_markup=InlineKeyboardMarkup(kb))
    elif query.data.startswith('as_'):
        cid, nid = int(query.data.split('_')[-1]), generate_order_id()
        conn = get_db_connection(); cur = conn.cursor(); cur.execute("UPDATE users SET order_id = %s, status = 'Started' WHERE user_id = %s;", (nid, cid)); conn.commit(); cur.close(); conn.close()
        await context.bot.send_message(chat_id=cid, text=f"🎉 **NomardDesk:** Project started! ID: `{nid}`")
        await query.edit_message_text(f"✅ Assigned ID `{nid}`.")
    elif query.data.startswith('st_'):
        p = query.data.split('_'); s_type, cid = p[1], int(p[2])
        s_map = {'wip': "⏳ Work in progress.", 'diff': "⚠️ The work is taking time and patience is required, it's a bit complex.", 'done': "🎉 Congratulations, your order is completed, go into the world and make profits!"}
        db_s = {'wip': 'In Progress', 'diff': 'Complex', 'done': 'Completed'}
        conn = get_db_connection(); cur = conn.cursor(); cur.execute("UPDATE users SET status = %s WHERE user_id = %s;", (db_s[s_type], cid)); conn.commit(); cur.close(); conn.close()
        await context.bot.send_message(chat_id=cid, text=s_map[s_type]); await query.edit_message_text(f"✅ Updated client {cid}.")

# ===== HEALTH SERVER (keeps Render Web Service alive) =====
async def health(request):
    return web.Response(text="NomardDesk Bot is alive")

async def post_init(application):
    web_app = web.Application()
    web_app.router.add_get("/", health)
    runner = web.AppRunner(web_app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logging.info(f"Health server running on port {port}")

# ===== MAIN =====
if __name__ == '__main__':
    if not TOKEN or not DATABASE_URL:
        logging.error("Missing TELEGRAM_BOT_TOKEN or DATABASE_URL")
        exit(1)
    init_db()
    app = ApplicationBuilder().token(TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("importusers", import_users))
    app.add_handler(MessageHandler(filters.Document.ALL & filters.CaptionRegex(r"^/importusers"), import_users))
    app.add_handler(MessageHandler((filters.TEXT | filters.PHOTO | filters.Document.ALL) & (~filters.COMMAND), handle_messages))
    app.add_handler(CallbackQueryHandler(handle_callback))
    logging.info("NomardDesk Bot V3.5 Active.")
    app.run_polling()
