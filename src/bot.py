import logging
import math
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode
from telegram.request import HTTPXRequest

from src.config import config
from src.database import UserDatabase
from src.lyrics import search_songs, get_lyrics_by_id
from src.lyrics.format import format_lyrics

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Global stores
user_sessions = {}
user_last_search = {}

class LyricsBot:
    """Main bot class"""
    
    def __init__(self):
        self.config = config
        self.config.setup_directories()
        self.db = UserDatabase(self.config.DATA_DIR)
        self.app = None
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user_id = update.effective_user.id
        user_name = update.effective_user.first_name
        
        # Save user to database
        self.db.add(user_id)
        
        await update.message.reply_text(
            f"🎵 *Welcome to Lyrics Hub Bot, {user_name}!*\n\n"
            f"Send me a song name and I'll find the lyrics!\n\n"
            f"📝 *Examples:*\n"
            f"• `Blinding Lights`\n"
            f"• `Shape of You Ed Sheeran`\n"
            f"• `Bohemian Rhapsody`\n\n"
            f"🎤 Just type and send!",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        await update.message.reply_text(
            "🎵 *Lyrics Hub Bot - Help*\n\n"
            "*How to use:*\n"
            "Simply send a song name or 'song name artist name'\n\n"
            "*Examples:*\n"
            "• `Blinding Lights`\n"
            "• `Shape of You Ed Sheeran`\n"
            "• `Bohemian Rhapsody`\n\n"
            "*Commands:*\n"
            "/start - Restart the bot\n"
            "/help - Show this help message",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def search_songs(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Search for songs when user sends a message"""
        user_id = update.effective_user.id
        query = update.message.text.strip()
        
        # Save user
        self.db.add(user_id)
        
        if not query:
            return
        
        # Rate limiting (prevent spam)
        now = datetime.now()
        if user_id in user_last_search:
            if now - user_last_search[user_id] < timedelta(seconds=2):
                await update.message.reply_text("⏰ Please wait a moment before searching again.")
                return
        user_last_search[user_id] = now
        
        # Send searching message
        status_msg = await update.message.reply_text(f"🔍 *Searching for:* `{query}`...", parse_mode=ParseMode.MARKDOWN)
        
        # Search for songs
        results = await search_songs(query)
        
        if not results or len(results) == 0:
            await status_msg.edit_text(
                f"❌ *No results found for:* `{query}`\n\n"
                f"💡 Try adding the artist name (e.g., 'Shape of You Ed Sheeran')",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Store results
        user_sessions[user_id] = {
            'results': results,
            'page': 0,
            'query': query
        }
        
        await self.show_results_page(update, context, user_id, 0)
        await status_msg.delete()
    
    async def show_results_page(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, page: int):
        """Show paginated song results"""
        session = user_sessions.get(user_id)
        if not session:
            return
        
        results = session['results']
        total_pages = math.ceil(len(results) / self.config.ITEMS_PER_PAGE)
        start_idx = page * self.config.ITEMS_PER_PAGE
        end_idx = min(start_idx + self.config.ITEMS_PER_PAGE, len(results))
        page_results = results[start_idx:end_idx]
        
        # Build keyboard
        keyboard = []
        for song in page_results:
            track_name = song.get('trackName', 'Unknown')[:35]
            artist_name = song.get('artistName', 'Unknown')[:25]
            button_text = f"{track_name} - {artist_name}"
            callback_data = f"lyric_{song['id']}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
        
        # Navigation buttons
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("◀️ Previous", callback_data=f"page_{page-1}"))
        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton("Next ▶️", callback_data=f"page_{page+1}"))
        
        if nav_buttons:
            keyboard.append(nav_buttons)
        
        # Cancel button
        keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel_search")])
        
        message_text = f"🎵 *Songs matching:* `{session['query']}`\n\n📄 Page {page+1} of {total_pages}\n\nSelect a song:"
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                message_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text(
                message_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        data = query.data
        
        if data == "cancel_search":
            await query.edit_message_text("❌ *Search cancelled.* Send a new song name to try again.", parse_mode=ParseMode.MARKDOWN)
            if user_id in user_sessions:
                del user_sessions[user_id]
            return
        
        if data.startswith("page_"):
            page = int(data.split("_")[1])
            await self.show_results_page(update, context, user_id, page)
            return
        
        if data.startswith("lyric_"):
            song_id = data.split("_")[1]
            await self.get_lyrics(update, context, song_id)
    
    async def get_lyrics(self, update: Update, context: ContextTypes.DEFAULT_TYPE, song_id: str):
        """Fetch and display lyrics"""
        query = update.callback_query
        user_id = update.effective_user.id
        
        await query.edit_message_text("📝 *Fetching lyrics...*", parse_mode=ParseMode.MARKDOWN)
        
        # Fetch lyrics
        song_data = await get_lyrics_by_id(song_id)
        
        if not song_data:
            await query.edit_message_text(
                "❌ *Failed to fetch lyrics.*\n\n"
                "Try another song!",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Get raw lyrics
        raw_lyrics = song_data.get('syncedLyrics') or song_data.get('plainLyrics')
        
        if not raw_lyrics:
            await query.edit_message_text(
                "❌ *No lyrics available for this song.*\n\n"
                "Try another song! 🎵",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Format lyrics
        lyrics = format_lyrics(raw_lyrics)
        
        # Get song details
        song_name = song_data.get('trackName', 'Unknown')
        artist_name = song_data.get('artistName', 'Unknown')
        album_name = song_data.get('albumName', '')
        
        # Build message
        message = f"🎤 *{song_name}*\n"
        message += f"👤 *Artist:* {artist_name}\n"
        if album_name:
            message += f"💿 *Album:* {album_name}\n"
        message += f"\n📝 *Lyrics:*\n\n{lyrics}"
        
        # Try to send with album art if available
        cover_art = song_data.get('coverArt')
        if cover_art and cover_art.startswith('http'):
            try:
                await context.bot.send_photo(
                    chat_id=update.effective_chat.id,
                    photo=cover_art,
                    caption=message[:1024],  # Photo caption limit
                    parse_mode=ParseMode.MARKDOWN
                )
                await query.delete_message()  # Delete the "fetching" message
            except Exception as e:
                logger.error(f"Failed to send photo: {e}")
                await query.edit_message_text(message, parse_mode=ParseMode.MARKDOWN)
        else:
            await query.edit_message_text(message, parse_mode=ParseMode.MARKDOWN)
        
        # Clear session
        if user_id in user_sessions:
            del user_sessions[user_id]
    
    def run(self):
        """Start the bot"""
        # Create application
        request = HTTPXRequest(
            connect_timeout=20.0,
            read_timeout=20.0,
            write_timeout=20.0,
            pool_timeout=20.0,
            http_version="1.1"
        )
        
        self.app = Application.builder().token(self.config.BOT_TOKEN).request(request).build()
        
        # Add handlers
        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(CommandHandler("help", self.help_command))
        self.app.add_handler(CallbackQueryHandler(self.handle_callback, pattern="^(page_|lyric_|cancel_search)"))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.search_songs))
        
        logger.info("=" * 50)
        logger.info("🤖 Lyrics Hub Bot Started Successfully!")
        logger.info(f"👥 Users in database: {self.db.count()}")
        logger.info("=" * 50)
        
        # Start polling
        self.app.run_polling(allowed_updates=Update.ALL_TYPES, poll_interval=1.0)
