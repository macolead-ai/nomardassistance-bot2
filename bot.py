import logging
import os
import json
import asyncio
from aiohttp import web
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
    MessageHandler,
    ChatMemberHandler,
    filters,
)

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get('BOT_TOKEN')
STATE_FILE = os.environ.get('STATE_FILE', 'channels.json')

# Modes
MODE_WAIT_MESSAGE = "wait_message"

# In-memory state: {user_id: [{"id": channel_id, "title": str}]}
state = {}


# ---------- State helpers ----------

def load_state():
    global state
    try:
        with open(STATE_FILE, 'r') as f:
            raw = json.load(f)
            state = {int(k): v for k, v in raw.items()}
        logger.info(f"Loaded {len(state)} user(s) from state.")
    except (FileNotFoundError, json.JSONDecodeError):
        state = {}


def save_state():
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump({str(k): v for k, v in state.items()}, f, indent=2)
    except Exception as e:
        logger.error(f"Save state failed: {e}")


def get_user_channels(user_id: int):
    return state.get(user_id, [])


def add_channel(user_id: int, channel_id: int, title: str):
    chans = state.setdefault(user_id, [])
    chans = [c for c in chans if c["id"] != channel_id]
    chans.append({"id": channel_id, "title": title})
    state[user_id] = chans
    save_state()


def remove_channel(user_id: int, channel_id: int):
    chans = state.get(user_id, [])
    state[user_id] = [c for c in chans if c["id"] != channel_id]
    save_state()


# ---------- Helpers ----------

def main_menu_markup() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("📝 Post to Channel", callback_data="menu_post")],
        [InlineKeyboardButton("📋 My Channels", callback_data="menu_channels")],
        [InlineKeyboardButton("ℹ️ Help", callback_data="menu_help")],
    ]
    return InlineKeyboardMarkup(keyboard)


def channels_markup(user_id: int, prefix: str = "pick") -> InlineKeyboardMarkup:
    """Show user's channels as buttons. prefix: 'pick' for post, 'rm' for remove."""
    chans = get_user_channels(user_id)
    rows = []
    for c in chans:
        rows.append([InlineKeyboardButton(f"📢 {c['title']}", callback_data=f"{prefix}_{c['id']}")])
    rows.append([InlineKeyboardButton("🏠 Main Menu", callback_data="menu_home")])
    return InlineKeyboardMarkup(rows)


def reset_user_state(context: ContextTypes.DEFAULT_TYPE) -> None:
    for key in ('mode', 'selected_channel', 'selected_title'):
        context.user_data.pop(key, None)


# ---------- Commands ----------

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info(f"User {user.id} started the bot")
    reset_user_state(context)

    welcome = (
        "👋 *Welcome to Channel Auto-Poster Bot!*\n\n"
        "I let you post to your Telegram channels — no channel IDs needed.\n\n"
        "🛠 *How it works:*\n"
        "1. Add me to your channel as *admin* with *Post Messages* permission\n"
        "2. I'll auto-detect the channel and link it to your account\n"
        "3. Come back here and use *Post to Channel*\n\n"
        "Tap below to begin:"
    )
    await update.message.reply_text(welcome, reply_markup=main_menu_markup(), parse_mode='Markdown')


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "ℹ️ *How to use*\n\n"
        "*Step 1 — Add me to a channel:*\n"
        "• Open your channel → Manage → Administrators\n"
        "• Add me as admin with *Post Messages* permission\n"
        "• I'll send you a confirmation DM ✅\n\n"
        "*Step 2 — Post:*\n"
        "• Tap 📝 *Post to Channel*\n"
        "• Pick the target channel\n"
        "• Send your message (text, photo, video, document, etc.)\n"
        "• Done! 🚀\n\n"
        "Use /channels to manage linked channels.\n"
        "Use /cancel anytime to reset."
    )
    if update.message:
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=main_menu_markup())
    else:
        await update.callback_query.edit_message_text(
            text, parse_mode='Markdown', reply_markup=main_menu_markup()
        )


async def channels_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chans = get_user_channels(user_id)
    if not chans:
        await update.message.reply_text(
            "📭 You haven't linked any channels yet.\n\n"
            "Add me as admin in a channel to get started.",
            reply_markup=main_menu_markup(),
        )
        return

    text = "📋 *Your linked channels:*\n\n" + "\n".join(
        f"• {c['title']} (`{c['id']}`)" for c in chans
    ) + "\n\nTap a channel to *remove* it:"

    await update.message.reply_text(
        text, reply_markup=channels_markup(user_id, prefix="rm"), parse_mode='Markdown'
    )


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reset_user_state(context)
    await update.message.reply_text(
        "❌ Cancelled. Use /start to begin again.",
        reply_markup=main_menu_markup(),
    )


# ---------- Menu callbacks ----------

async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if data == "menu_home":
        reset_user_state(context)
        await query.edit_message_text(
            "🏠 *Main Menu*\nChoose an option below:",
            reply_markup=main_menu_markup(),
            parse_mode='Markdown',
        )

    elif data == "menu_help":
        await help_command(update, context)

    elif data == "menu_post":
        chans = get_user_channels(user_id)
        if not chans:
            await query.edit_message_text(
                "📭 You haven't linked any channels yet.\n\n"
                "👉 *To link a channel:*\n"
                "1. Open your channel → Manage → Administrators\n"
                "2. Add me as admin with *Post Messages* permission\n"
                "3. Come back here and tap *Post to Channel* again",
                parse_mode='Markdown',
                reply_markup=main_menu_markup(),
            )
            return

        await query.edit_message_text(
            "📝 *Pick the channel to post in:*",
            reply_markup=channels_markup(user_id, prefix="pick"),
            parse_mode='Markdown',
        )

    elif data == "menu_channels":
        chans = get_user_channels(user_id)
        if not chans:
            await query.edit_message_text(
                "📭 You haven't linked any channels yet.",
                reply_markup=main_menu_markup(),
            )
            return
        text = "📋 *Your linked channels:*\n\n" + "\n".join(
            f"• {c['title']}" for c in chans
        ) + "\n\nTap a channel to *remove* it:"
        await query.edit_message_text(
            text,
            reply_markup=channels_markup(user_id, prefix="rm"),
            parse_mode='Markdown',
        )

    elif data.startswith("pick_"):
        channel_id = int(data.split("_", 1)[1])
        chan = next((c for c in get_user_channels(user_id) if c["id"] == channel_id), None)
        if not chan:
            await query.edit_message_text(
                "⚠️ Channel not found. Start again.",
                reply_markup=main_menu_markup(),
            )
            return
        context.user_data['selected_channel'] = channel_id
        context.user_data['selected_title'] = chan["title"]
        context.user_data['mode'] = MODE_WAIT_MESSAGE
        await query.edit_message_text(
            f"✏️ Posting to *{chan['title']}*.\n\n"
            "Send the message you want to post.\n"
            "Supports: *text, photos, videos, documents, voice, polls, etc.*\n\n"
            "Use /cancel to abort.",
            parse_mode='Markdown',
        )

    elif data.startswith("rm_"):
        channel_id = int(data.split("_", 1)[1])
        chan = next((c for c in get_user_channels(user_id) if c["id"] == channel_id), None)
        if not chan:
            await query.edit_message_text(
                "⚠️ Channel not found.", reply_markup=main_menu_markup()
            )
            return
        remove_channel(user_id, channel_id)
        await query.edit_message_text(
            f"🗑 Removed *{chan['title']}* from your linked channels.\n\n"
            "_Note: You can re-link by adding me back as admin._",
            parse_mode='Markdown',
            reply_markup=main_menu_markup(),
        )


# ---------- Channel detection (my_chat_member) ----------

async def my_chat_member_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Detect when the bot is added/removed/promoted in a channel."""
    cmu = update.my_chat_member
    if not cmu:
        return

    chat = cmu.chat
    if chat.type != "channel":
        return  # only handle channels

    new_status = cmu.new_chat_member.status
    actor = cmu.from_user
    if not actor:
        return

    actor_id = actor.id
    title = chat.title or f"Channel {chat.id}"

    if new_status == "administrator":
        add_channel(actor_id, chat.id, title)
        logger.info(f"Bot promoted to admin in channel {chat.id} ({title}) by user {actor_id}")
        try:
            await context.bot.send_message(
                actor_id,
                f"✅ *Channel linked!*\n\n"
                f"📢 *{title}*\n\n"
                "I'm now ready to post here. Use /post or tap *Post to Channel* to begin.",
                parse_mode='Markdown',
                reply_markup=main_menu_markup(),
            )
        except Exception as e:
            logger.warning(f"Could not DM user {actor_id}: {e}")

    elif new_status in ("left", "kicked", "restricted"):
        remove_channel(actor_id, chat.id)
        logger.info(f"Bot removed from channel {chat.id} by user {actor_id}")
        try:
            await context.bot.send_message(
                actor_id,
                f"❌ I was removed from *{title}*. Channel unlinked.",
                parse_mode='Markdown',
            )
        except Exception:
            pass

    elif new_status == "member":
        # Added but not admin yet — needs admin rights to post
        try:
            await context.bot.send_message(
                actor_id,
                f"👀 I was added to *{title}* but I need *admin rights* (with *Post Messages* permission) to post here.",
                parse_mode='Markdown',
            )
        except Exception:
            pass


# ---------- Message posting ----------

async def handle_post_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """When user sends any message after picking a channel, copy it to that channel."""
    if context.user_data.get('mode') != MODE_WAIT_MESSAGE:
        return

    channel_id = context.user_data.get('selected_channel')
    channel_title = context.user_data.get('selected_title', 'channel')
    if not channel_id:
        await update.message.reply_text(
            "⚠️ No channel selected. Start again.",
            reply_markup=main_menu_markup(),
        )
        reset_user_state(context)
        return

    user_id = update.effective_user.id
    msg = update.message

    try:
        # copy_message handles all types: text, photo, video, document, audio, voice, poll, etc.
        await context.bot.copy_message(
            chat_id=channel_id,
            from_chat_id=user_id,
            message_id=msg.message_id,
        )
        await msg.reply_text(
            f"✅ *Posted to {channel_title}!*\n\nWant to post again?",
            parse_mode='Markdown',
            reply_markup=main_menu_markup(),
        )
    except Exception as e:
        logger.error(f"Failed to post to {channel_id}: {e}")
        err = str(e)
        hint = ""
        if "chat not found" in err.lower():
            hint = "\n\n💡 The channel may have been deleted or I was removed."
        elif "not enough rights" in err.lower() or "forbidden" in err.lower():
            hint = "\n\n💡 Make sure I'm an admin with *Post Messages* permission."
        await msg.reply_text(
            f"❌ Could not post: {err}{hint}",
            parse_mode='Markdown',
            reply_markup=main_menu_markup(),
        )
    finally:
        reset_user_state(context)


# ---------- Dummy web server (keeps Render Web Service alive) ----------

async def health(request):
    return web.Response(text="Bot is running")


async def run_web():
    port = int(os.environ.get("PORT", 10000))
    app = web.Application()
    app.router.add_get("/", health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Health server listening on port {port}")


# ---------- Runner ----------

async def run_bot():
    if not BOT_TOKEN:
        logger.critical("FATAL: BOT_TOKEN is missing!")
        return

    load_state()

    try:
        application = Application.builder().token(BOT_TOKEN).build()

        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("channels", channels_command))
        application.add_handler(CommandHandler("post", lambda u, c: menu_callback_synthetic(u, c, "menu_post")))
        application.add_handler(CommandHandler("cancel", cancel_command))
        application.add_handler(CallbackQueryHandler(menu_callback))

        # Channel admin/membership events
        application.add_handler(
            ChatMemberHandler(my_chat_member_handler, ChatMemberHandler.MY_CHAT_MEMBER)
        )

        # All messages in private chat (after channel selection)
        application.add_handler(
            MessageHandler(filters.ChatType.PRIVATE & ~filters.COMMAND, handle_post_message)
        )

        await run_web()

        logger.info("Bot is now polling...")
        await application.initialize()
        await application.start()
        # IMPORTANT: explicitly request my_chat_member updates
        await application.updater.start_polling(
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES,
        )

        stop_event = asyncio.Event()
        await stop_event.wait()

    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
    finally:
        if 'application' in locals():
            await application.stop()
            await application.shutdown()


async def menu_callback_synthetic(update, context, target):
    """Helper to invoke menu_callback from a /post command (no callback_query)."""
    if target == "menu_post":
        user_id = update.effective_user.id
        chans = get_user_channels(user_id)
        if not chans:
            await update.message.reply_text(
                "📭 You haven't linked any channels yet.\n\n"
                "👉 Add me as admin in your channel first.",
                reply_markup=main_menu_markup(),
            )
            return
        await update.message.reply_text(
            "📝 *Pick the channel to post in:*",
            reply_markup=channels_markup(user_id, prefix="pick"),
            parse_mode='Markdown',
        )


def main():
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
    except Exception as e:
        logger.error(f"Main loop error: {e}")


if __name__ == '__main__':
    main()
