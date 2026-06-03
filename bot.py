import os
import logging
from datetime import datetime
from threading import Thread
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler
from telegram.request import HTTPXRequest

from config import BOT_TOKEN, LOGS_DIR
from database import load_users
from deletion_manager import DeletionManager
from broadcast_manager import BroadcastManager, set_deletion_manager as bm_set_deletion
from lyrics import start, search_songs, handle_callback, help_command
from admin import (
    admin_panel, admin_callback,
    simple_text_received, simple_duration_received, simple_confirm_callback,
    full_image_received, full_caption_received, full_button_text_received,
    full_button_url_received, full_duration_received, full_confirm_callback,
    cancel_conversation, set_managers,
    SIMPLE_TEXT, SIMPLE_DURATION, SIMPLE_CONFIRM,
    FULL_IMAGE, FULL_CAPTION, FULL_BUTTON_TEXT, FULL_BUTTON_URL, FULL_DURATION, FULL_CONFIRM
)

# Create Flask app for health checks
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "🤖 Lyrics Hub Bot is running!"

@flask_app.route('/health')
def health():
    return "OK", 200

def run_web_server():
    """Run Flask web server for Render health checks"""
    port = int(os.environ.get('PORT', 8080))
    flask_app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# Setup logging
log_file = os.path.join(LOGS_DIR, f'bot_{datetime.now().strftime("%Y%m%d")}.log')
os.makedirs(LOGS_DIR, exist_ok=True)
os.makedirs("data", exist_ok=True)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

async def post_init(application):
    """Run after application is initialized"""
    global deletion_manager
    if deletion_manager:
        await deletion_manager.start_cleaner()
    logger.info("Post-initialization complete")

def main():
    global deletion_manager, broadcast_manager
    
    # Load users
    load_users()
    
    # Create application
    request = HTTPXRequest(
        connect_timeout=20.0,
        read_timeout=20.0,
        write_timeout=20.0,
        pool_timeout=20.0,
        http_version="1.1"
    )
    app = Application.builder().token(BOT_TOKEN).request(request).post_init(post_init).build()
    
    # Initialize managers
    deletion_manager = DeletionManager(app.bot)
    broadcast_manager = BroadcastManager(app.bot)
    
    # Set managers for admin module
    set_managers(broadcast_manager, deletion_manager)
    bm_set_deletion(deletion_manager)
    
    # Simple broadcast conversation
    simple_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_callback, pattern="^admin_simple$")],
        states={
            SIMPLE_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, simple_text_received)],
            SIMPLE_DURATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, simple_duration_received)],
            SIMPLE_CONFIRM: [CallbackQueryHandler(simple_confirm_callback, pattern="^(simple_send|simple_cancel)$")],
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
        per_message=False,
        per_chat=True,
    )
    
    # Full broadcast conversation
    full_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_callback, pattern="^admin_full$")],
        states={
            FULL_IMAGE: [MessageHandler(filters.PHOTO, full_image_received)],
            FULL_CAPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, full_caption_received)],
            FULL_BUTTON_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, full_button_text_received)],
            FULL_BUTTON_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, full_button_url_received)],
            FULL_DURATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, full_duration_received)],
            FULL_CONFIRM: [CallbackQueryHandler(full_confirm_callback, pattern="^(full_send|full_cancel)$")],
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
        per_message=False,
        per_chat=True,
    )
    
    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(simple_conv)
    app.add_handler(full_conv)
    app.add_handler(CallbackQueryHandler(admin_callback, pattern="^(admin_stats|admin_scheduled|admin_close)$"))
    app.add_handler(CallbackQueryHandler(handle_callback, pattern="^(page_|lyric_|cancel_search)"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_songs))
    
    # Start web server in background thread (for Render)
    web_thread = Thread(target=run_web_server, daemon=True)
    web_thread.start()
    logger.info("Web server started on port " + os.environ.get('PORT', '8080'))
    
    logger.info("="*50)
    logger.info("🤖 Lyrics Hub Bot Started Successfully!")
    logger.info("="*50)
    
    # Start polling (this blocks)
    app.run_polling(allowed_updates=Update.ALL_TYPES, poll_interval=1.0)

if __name__ == "__main__":
    main()
