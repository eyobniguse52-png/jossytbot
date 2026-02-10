import os
import logging
import tempfile
import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, CallbackQueryHandler, Filters, CallbackContext

# ===== CONFIG =====
TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TOKEN:
    raise RuntimeError("❌ Missing TELEGRAM_TOKEN")

# ===== SETUP =====
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
user_context = {}

# ===== HANDLERS =====
def start(update: Update, context: CallbackContext):
    update.message.reply_text(
        "👋 Welcome to YouTube Downloader!\n\n"
        "🔗 Send any YouTube link",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🚀 Start", callback_data='start')
        ]])
    )

def handle_link(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    if "youtube.com" not in text and "youtu.be" not in text:
        update.message.reply_text("⚠️ Send a valid YouTube link")
        return
    
    update.message.reply_text("🔍 Fetching formats...")
    
    try:
        # Get video info
        ydl_opts = {'quiet': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(text, download=False)
        
        user_context[user_id] = {'link': text, 'title': info['title']}
        
        # Build CLEAN format buttons (like your screenshot)
        formats = []
        seen_resolutions = set()
        
        for f in info.get('formats', []):
            # Only include real video/audio formats
            if f.get('vcodec') == 'none' and f.get('acodec') != 'none':
                # Audio only
                if 'mp3' in f.get('ext', '') or 'm4a' in f.get('ext', ''):
                    formats.append(('🎵 Audio (MP3)', 'bestaudio[ext=m4a]/bestaudio'))
                    break  # Only add MP3 once
            elif f.get('vcodec') != 'none' and f.get('height'):
                res = f.get('height')
                if res not in seen_resolutions:
                    seen_resolutions.add(res)
                    label = f"{res}p"
                    formats.append((label, f'bestvideo[height={res}]+bestaudio/best[height={res}]'))
        
        # Add 1080p/720p/480p/360p explicitly if missing
        default_res = [1080, 720, 480, 360]
        for res in default_res:
            if res not in seen_resolutions:
                formats.append((f"{res}p", f'bestvideo[height={res}]+bestaudio/best[height={res}]'))
        
        # Create 2-column layout (like your screenshot)
        keyboard = []
        for i in range(0, len(formats), 2):
            row = []
            for j in range(i, min(i+2, len(formats))):
                label, fmt_id = formats[j]
                row.append(InlineKeyboardButton(label, callback_data=fmt_id))
            keyboard.append(row)
        
        update.message.reply_text(
            f"✅ {info['title']}\n\n"
            "🎯 Select format:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    except Exception as e:
        update.message.reply_text(f"❌ Error: {str(e)[:50]}")

def download_format(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = query.from_user.id
    
    if user_id not in user_context:
        query.answer("⚠️ Send link first!")
        return
    
    fmt_id = query.data
    query.message.edit_text("⏳ Downloading...")
    
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            ydl_opts = {
                'format': fmt_id,
                'outtmpl': os.path.join(tmpdir, '%(id)s.%(ext)s'),
                'quiet': True,
                'no_warnings': True
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(user_context[user_id]['link'], download=True)
                file_path = ydl.prepare_filename(info)
            
            # Send file
            if file_path.endswith(('.mp3', '.m4a')):
                query.message.reply_audio(open(file_path, 'rb'), title=info['title'])
            else:
                query.message.reply_video(open(file_path, 'rb'), caption=info['title'])
        
        del user_context[user_id]
        query.message.edit_text("✅ Done!")
        
    except Exception as e:
        query.message.edit_text(f"❌ Failed: {str(e)[:60]}")

def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher
    
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_link))
    dp.add_handler(CallbackQueryHandler(download_format))
    
    logger.info("✅ Bot ready")
    updater.start_polling(drop_pending_updates=True)
    updater.idle()

if __name__ == '__main__':
    main()
