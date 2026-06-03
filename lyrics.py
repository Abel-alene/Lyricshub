import aiohttp
import asyncio
import math
import random
import re
import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from config import CHANNEL_LINK, ITEMS_PER_PAGE
from database import add_user

logger = logging.getLogger(__name__)

# LRCLIB API endpoints
LRCLIB_SEARCH = "https://lrclib.net/api/search"
LRCLIB_GET = "https://lrclib.net/api/get"

# Global stores
user_sessions = {}
user_last_search = {}

def clean_text(text):
    if not text:
        return ""
    text = text.replace('\x00', '')
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    return text

def remove_timestamps(lyrics):
    if not lyrics:
        return ""
    lyrics = re.sub(r'\[\d{2}:\d{2}\.\d{2}\]', '', lyrics)
    lyrics = re.sub(r'\n\s*\n', '\n', lyrics)
    return lyrics.strip()

def escape_markdown(text):
    if not text:
        return ""
    special_chars = r'_*[]()~`>#+-=|{}.!'
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text

async def start(update: Update, context):
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    add_user(user_id)
    await update.message.reply_text(
        f"<b>🎵 Welcome to Lyrics Hub Bot, {escape_markdown(user_name)}!</b>\n\n"
        f"Send me a song name and I'll find the lyrics!\n\n"
        f"<b>📝 Examples:</b>\n"
        f"• <code>Blinding Lights</code>\n"
        f"• <code>Shape of You Ed Sheeran</code>\n"
        f"• <code>Bohemian Rhapsody</code>\n\n"
        f"<b>📢 Join our channel:</b> {CHANNEL_LINK}",
        parse_mode=ParseMode.HTML
    )

async def search_songs(update: Update, context):
    user_id = update.effective_user.id
    query = update.message.text.strip()
    add_user(user_id)

    if not query:
        return

    now = datetime.now()
    if user_id in user_last_search and (now - user_last_search[user_id]) < timedelta(seconds=2):
        await update.message.reply_text("⏰ Please wait a moment before searching again.")
        return
    user_last_search[user_id] = now

    status_msg = await update.message.reply_text(f"🔍 Searching for: {query}...")

    try:
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            params = {'q': query}
            async with session.get(LRCLIB_SEARCH, params=params) as resp:
                if resp.status == 200:
                    results = await resp.json()
                else:
                    results = []

        if not results:
            await status_msg.edit_text(f"❌ No results found for: {query}\n\n💡 Try adding the artist name.")
            return

        user_sessions[user_id] = {
            'results': results,
            'page': 0,
            'query': query
        }
        await show_results_page(update, context, user_id, 0)
        await status_msg.delete()

    except asyncio.TimeoutError:
        await status_msg.edit_text("❌ Request timed out. Please try again.")
    except Exception as e:
        logger.error(f"Search error: {e}")
        await status_msg.edit_text("❌ An error occurred. Please try again.")

async def show_results_page(update, context, user_id, page):
    session = user_sessions.get(user_id)
    if not session:
        return

    results = session['results']
    total_pages = math.ceil(len(results) / ITEMS_PER_PAGE)
    start = page * ITEMS_PER_PAGE
    end = min(start + ITEMS_PER_PAGE, len(results))
    page_results = results[start:end]

    keyboard = []
    for song in page_results:
        track = song.get('trackName', 'Unknown')[:35]
        artist = song.get('artistName', 'Unknown')[:25]
        keyboard.append([InlineKeyboardButton(f"{track} - {artist}", callback_data=f"lyric_{song['id']}")])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️ Previous", callback_data=f"page_{page-1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("Next ▶️", callback_data=f"page_{page+1}"))
    if nav:
        keyboard.append(nav)
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel_search")])

    text = f"🎵 Songs matching: {session['query']}\n\n📄 Page {page+1} of {total_pages}\n\nSelect a song:"

    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_callback(update: Update, context):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    data = query.data

    if data == "cancel_search":
        await query.edit_message_text("❌ Search cancelled. Send a new song name.")
        user_sessions.pop(user_id, None)
        return

    if data.startswith("page_"):
        page = int(data.split("_")[1])
        await show_results_page(update, context, user_id, page)
        return

    if data.startswith("lyric_"):
        song_id = data.split("_")[1]
        await get_lyrics(update, context, song_id)

async def get_lyrics(update, context, song_id):
    query = update.callback_query
    user_id = update.effective_user.id

    await query.edit_message_text("📝 Fetching lyrics...")

    try:
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(f"{LRCLIB_GET}/{song_id}") as resp:
                if resp.status != 200:
                    await query.edit_message_text("❌ Failed to fetch lyrics. Try another song.")
                    return
                song_data = await resp.json()

        raw = song_data.get('syncedLyrics') or song_data.get('plainLyrics')
        if not raw:
            await query.edit_message_text("❌ No lyrics available for this song.")
            return

        lyrics = remove_timestamps(raw)
        lyrics = clean_text(lyrics)
        if len(lyrics) > 3500:
            lyrics = lyrics[:3500] + "\n\n... (truncated)"

        title = clean_text(song_data.get('trackName', 'Unknown'))
        artist = clean_text(song_data.get('artistName', 'Unknown'))
        album = clean_text(song_data.get('albumName', ''))

        msg = f"<b>🎤 {title}</b>\n<b>👤 Artist:</b> {artist}\n"
        if album:
            msg += f"<b>💿 Album:</b> {album}\n"
        msg += f"\n<b>📝 Lyrics:</b>\n\n<code>{lyrics}</code>\n\n━━━━━━━━━━━━━━━━━━━━━\n📢 {CHANNEL_LINK}"

        cover = song_data.get('coverArt')
        if cover and cover.startswith('http'):
            try:
                await context.bot.send_photo(
                    chat_id=update.effective_chat.id,
                    photo=cover,
                    caption=msg[:1024],
                    parse_mode=ParseMode.HTML
                )
                await query.delete_message()
            except:
                await send_long_message(context, update.effective_chat.id, msg, query)
        else:
            await send_long_message(context, update.effective_chat.id, msg, query)

        user_sessions.pop(user_id, None)

        if random.random() < 0.1:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"📢 Join our channel for more lyrics!\n{CHANNEL_LINK}"
            )

    except asyncio.TimeoutError:
        await query.edit_message_text("❌ Request timed out. Please try again.")
    except Exception as e:
        logger.error(f"Lyrics error: {e}")
        await query.edit_message_text("❌ An error occurred. Please try again.")

async def send_long_message(context, chat_id, message, query=None):
    if len(message) > 4096:
        if query:
            await query.delete_message()
        for i in range(0, len(message), 4000):
            await context.bot.send_message(chat_id=chat_id, text=message[i:i+4000], parse_mode=ParseMode.HTML)
    else:
        if query:
            await query.edit_message_text(message, parse_mode=ParseMode.HTML)
        else:
            await context.bot.send_message(chat_id=chat_id, text=message, parse_mode=ParseMode.HTML)

async def help_command(update: Update, context):
    await update.message.reply_text(
        f"🎵 Lyrics Hub Bot\n\nSend a song name to get lyrics!\n\n📢 Channel: {CHANNEL_LINK}"
    )
