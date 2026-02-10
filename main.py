import os
import logging
import tempfile
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

# ===== CONFIG =====
ADMIN_ID = None
TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TOKEN:
    raise RuntimeError("❌ Missing TELEGRAM_TOKEN environment variable!")

# ===== SETUP =====
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)
approved_users = set()

# ===== HANDLERS =====
def start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if user_id == ADMIN_ID:
        update.message.reply_text("✅ Admin mode active. Send /approve [user_id] to approve users.")
    elif user_id in approved_users:
        update.message.reply_text("✅ You're approved! Send any YouTube link to download.")
    else:
        update.message.reply_text(f"⚠️ Pending approval. Your ID: `{user_id}`\nContact admin to get access.", parse_mode='Markdown')

def approve(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID:
        update.message.reply_text("❌ Only admin can use this command.")
        return
    if not context.args:
        update.message.reply_text("UsageId: /approve 123456789")
        return
    try:
        user_id = int(context.args[0])
        approved_users.add(user_id)
        update.message.reply_text(f"✅ Approved user {user_id}")
    except ValueError:
        update.message.reply_text("❌ Invalid user ID (must be numbers only)")

def handle_message(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID and user_id not in approved_users:
        update.message.reply_text("❌ You need admin approval first. Contact the bot owner.")
        return
    
    text = update.message.text.strip()
    if "youtube.com" not in text and "youtu.be" not in text:
        update.message.reply_text("⚠️ Please send a valid YouTube link (youtube.com or youtu.be)")
        return
    
    update.message.reply_text("⏳ Downloading video... (this may take 10-30 seconds)")
    try:
        # Create temp directory for downloads
        with tempfile.TemporaryDirectory() as tmpdir:
            # yt-dlp will be added in NEXT STEP (safe placeholder for now)
            update.message.reply_text("✅ Bot is working! YouTube download feature will be activated in the next update.")
    except Exception as e:
        logger.error(f"Download error: {str(e)}")
        update.message.reply_text(f"❌ Download failed: {str(e)[:100]}")

def main():
    global ADMIN_ID
    admin_env = os.getenv("ADMIN_ID")
    if not admin_env:
        raise RuntimeError("❌ Missing ADMIN_ID environment variable!")
    try:
        ADMIN_ID = int(admin_env)
    except ValueError:
        raise RuntimeError("❌ ADMIN_ID must be a number (your Telegram ID)")
    
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("approve", approve))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    
    logger.info(f"✅ Bot started successfully | Admin ID: {ADMIN_ID}")
    updater.start_polling(drop_pending_updates=True)
    updater.idle()

if __name__ == '__main__':
    main()