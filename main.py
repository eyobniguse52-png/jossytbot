import os
import logging
import tempfile
import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, CallbackQueryHandler, Filters, CallbackContext

# ===== CONFIG =====
TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TOKEN:
    raise RuntimeError("❌ Missing TELEGRAM_TOKEN environment variable!")

# ===== SETUP =====
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)
user_context = {}  # Tracks user's current download session

# ===== HANDLERS =====
def start(update: Update, context: CallbackContext):
    """Send welcome message with animated emoji"""
    update.message.reply_text(
        "👋 Welcome to YouTube Downloader Bot!\n\n"
        "👉 *Send any YouTube link* to start\n\n"
        "⚡ *Works with all formats*: Video, Audio (MP3), 1080p, 4K & more",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🚀 Get Started", callback_data='start')]
        ])
    )

def format_selected(update: Update, context: CallbackContext):
    """Handle format selection"""
    query = update.callback_query
    user_id = query.from_user.id
    format_id = query.data
    
    # Check if user has active session
    if user_id not in user_context:
        query.answer("⚠️ Please send a YouTube link first!")
        return
    
    # Update UI
    query.message.edit_text("⏳ Downloading your file... (this may take 10-60 seconds)")
    
    try:
        # Download selected format
        with tempfile.TemporaryDirectory() as tmpdir:
            ydl_opts = {
                'format': format_id,
                'outtmpl': os.path.join(tmpdir, '%(id)s.%(ext)s'),
                'quiet': True,
                'no_warnings': True,
                'progress_hooks': [lambda d: query.message.edit_text(
                    f"⏳ Downloading... {d.get('downloaded_bytes', 0) / d.get('total_bytes', 1):.1%}"
                ) if d['status'] == 'downloading' else None]
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(user_context[user_id]['link'], download=True)
                file_path = ydl.prepare_filename(info)
            
            # Send appropriate file type
            if file_path.endswith(('.mp3', '.m4a', '.opus', '.webm')):
                query.message.reply_audio(
                    open(file_path, 'rb'),
                    title=info['title'],
                    performer=info['uploader']
                )
            else:
                query.message.reply_video(
                    open(file_path, 'rb'),
                    caption=f"✅ {info['title']}",
                    supports_streaming=True
                )
        
        # Cleanup
        del user_context[user_id]
        query.message.edit_text("✅ Download complete! (You can send another link)")
        
    except Exception as e:
        logger.error(f"Download error: {str(e)}")
        query.message.edit_text(f"❌ Failed: {str(e)[:100]}")

def handle_youtube_link(update: Update, context: CallbackContext):
    """Process YouTube links and show format options"""
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    # Validate YouTube link
    if not ("youtube.com" in text or "youtu.be" in text):
        update.message.reply_text("⚠️ Please send a valid YouTube link (youtube.com or youtu.be)")
        return
    
    # Update UI
    update.message.reply_text("🔍 Analyzing video formats... (10-30 seconds)")
    
    try:
        # Get available formats
        ydl_opts = {'quiet': True, 'extract_flat': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(text, download=False)
        
        # Store context
        user_context[user_id] = {'link': text, 'info': info}
        
        # Prepare format options
        formats = []
        for f in info.get('formats', []):
            # Skip invalid formats
            if not f.get('format_id') or not f.get('ext'):
                continue
            
            # Format label (video: resolution, audio: quality)
            if f.get('vcodec') != 'none':
                label = f"🎬 {f.get('format_note', 'Unknown')} ({f['ext']})"
            else:
                label = f"🔊 {f.get('format_note', 'Audio')} ({f['ext']})"
            
            formats.append((label, f['format_id']))
        
        # Show format selection
        keyboard = [
            [InlineKeyboardButton(label, callback_data=format_id)]
            for label, format_id in formats[:15]  # Limit to 15 options
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        update.message.reply_text(
            f"✅ *{info['title']}*\n\n"
            "🎯 *Select your format:*",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        
    except Exception as e:
        logger.error(f"Format error: {str(e)}")
        update.message.reply_text(f"❌ Failed to get formats: {str(e)[:100]}")

def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher
    
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CallbackQueryHandler(format_selected))
    dp.add_handler(MessageHandler(
        Filters.text & ~Filters.command & (Filters.entity('url') | Filters.entity('text_link')),
        handle_youtube_link
    ))
    
    logger.info("✅ Bot started successfully")
    updater.start_polling(drop_pending_updates=True)
    updater.idle()

if __name__ == '__main__':
    main()
