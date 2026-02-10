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
    """🔥 Professional welcome message"""
    update.message.reply_text(
        "👋 Hey it's *Joss!* \n\n"
        "📥 You want to download a YouTube link? \n"
        "👉 Just *drop it here* — I'll handle the rest! 🚀",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Start", callback_data='start')
        ]])
    )

def handle_link(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    if "youtube.com" not in text and "youtu.be" not in text:
        update.message.reply_text("⚠️ Please send a valid YouTube link (e.g., youtu.be/abc123)")
        return
    
    update.message.reply_text("🔍 Fetching formats...")
    
    try:
        # Use yt-dlp with safe options
        ydl_opts = {
            'quiet': True,
            'extract_flat': False,
            'no_warnings': True,
            'skip_download': True
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(text, download=False)
        
        user_context[user_id] = {'link': text, 'title': info.get('title', 'Video')}
        
        # Build CLEAN format list (only real ones)
        formats = []
        resolutions = {360, 480, 720, 1080}
        
        for f in info.get('formats', []):
            height = f.get('height')
            if height in resolutions and f.get('vcodec') != 'none':
                formats.append((f"{height}p", f'bestvideo[height={height}]+bestaudio'))
                resolutions.discard(height)
        
        # Add audio (MP3 only)
        formats.append(('🎵 Audio (MP3)', 'bestaudio[ext=m4a]/bestaudio'))
        
        # Create 2-column layout
        keyboard = []
        for i in range(0, len(formats), 2):
            row = []
            for j in range(i, min(i+2, len(formats))):
                label, fmt_id = formats[j]
                row.append(InlineKeyboardButton(label, callback_data=fmt_id))
            keyboard.append(row)
        
        update.message.reply_text(
            f"🎬 *{info['title']}*\n\n"
            "🎯 Choose format:",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    except Exception as e:
        logger.error(f"Format error: {e}")
        update.message.reply_text(f"❌ Error: {str(e)[:60]}")

def download_format(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = query.from_user.id
    
    if user_id not in user_context:
        query.answer("⚠️ Send link first!")
        return
    
    fmt_id = query.data
    query.message.edit_text("⏳ Downloading... (10-30 sec)")
    
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            ydl_opts = {
                'format': fmt_id,
                'outtmpl': os.path.join(tmpdir, '%(id)s.%(ext)s'),
                'quiet': True,
                'no_warnings': True,
                'noplaylist': True,
                'retries': 10,
                'fragment_retries': 10,
                'skip_unavailable_fragments': True
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(user_context[user_id]['link'], download=True)
                file_path = ydl.prepare_filename(info)
            
            # Fix file extension for Telegram
            if file_path.endswith('.webm'):
                new_path = file_path.replace('.webm', '.mp4')
                os.rename(file_path, new_path)
                file_path = new_path
            
            # Send file
            if file_path.endswith(('.mp3', '.m4a')):
                query.message.reply_audio(open(file_path, 'rb'), title=info['title'])
            else:
                query.message.reply_video(
                    open(file_path, 'rb'),
                    caption=f"✅ {info['title']}",
                    supports_streaming=True
                )
        
        del user_context[user_id]
        query.message.edit_text("🎉 Download complete!")
        
    except Exception as e:
        logger.error(f"Download error: {e}")
        query.message.edit_text(f"❌ Failed: {str(e)[:80]}")

def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher
    
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_link))
    dp.add_handler(CallbackQueryHandler(download_format))
    
    logger.info("✅ Joss Bot ready")
    updater.start_polling(drop_pending_updates=True)
    updater.idle()

if __name__ == '__main__':
    main()
