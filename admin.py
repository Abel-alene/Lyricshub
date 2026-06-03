import asyncio
import time as time_module
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from telegram.constants import ParseMode
from config import ADMIN_ID, CHANNEL_LINK
from database import get_all_users
from broadcast_manager import BroadcastManager
from deletion_manager import DeletionManager

logger = logging.getLogger(__name__)

# Conversation states
SIMPLE_TEXT, SIMPLE_DURATION, SIMPLE_CONFIRM = range(1, 4)
FULL_IMAGE, FULL_CAPTION, FULL_BUTTON_TEXT, FULL_BUTTON_URL, FULL_DURATION, FULL_CONFIRM = range(10, 16)

# Global stores
temp_broadcast = {}
broadcast_manager = None
deletion_manager = None

def set_managers(bm, dm):
    global broadcast_manager, deletion_manager
    broadcast_manager = bm
    deletion_manager = dm

def parse_duration(duration_str):
    """Convert human readable duration to seconds"""
    duration_str = duration_str.lower().strip()
    if duration_str.endswith('s'):
        duration_str = duration_str[:-1]
    if duration_str.endswith('m'):
        return int(duration_str[:-1]) * 60
    if duration_str.endswith('h'):
        return int(duration_str[:-1]) * 3600
    if duration_str.endswith('d'):
        return int(duration_str[:-1]) * 86400
    if duration_str.isdigit():
        return int(duration_str)
    raise ValueError(f"Invalid duration format: {duration_str}")

def format_duration(seconds):
    """Convert seconds to human readable format"""
    if seconds >= 86400:
        return f"{seconds//86400} day(s)"
    elif seconds >= 3600:
        return f"{seconds//3600} hour(s)"
    elif seconds >= 60:
        return f"{seconds//60} minute(s)"
    else:
        return f"{seconds} second(s)"

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show admin panel with broadcast options"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Unauthorized")
        return
    
    keyboard = [
        [InlineKeyboardButton("📝 Simple Broadcast (Text Only)", callback_data="admin_simple")],
        [InlineKeyboardButton("🎨 Full Broadcast (Image + Text + Button)", callback_data="admin_full")],
        [InlineKeyboardButton("📊 View Stats", callback_data="admin_stats")],
        [InlineKeyboardButton("⏰ Manage Scheduled", callback_data="admin_scheduled")],
        [InlineKeyboardButton("❌ Close", callback_data="admin_close")]
    ]
    
    await update.message.reply_text(
        "🔐 *Admin Broadcast Panel*\n\nChoose an option below:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin panel callbacks"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await query.edit_message_text("❌ Unauthorized")
        return ConversationHandler.END
    
    data = query.data
    
    if data == "admin_simple":
        await query.edit_message_text(
            "📝 *Simple Text Broadcast*\n\n"
            "Please send me the text message you want to broadcast to all users.\n\n"
            "Type /cancel to cancel.",
            parse_mode=ParseMode.MARKDOWN
        )
        return SIMPLE_TEXT
    
    elif data == "admin_full":
        await query.edit_message_text(
            "🎨 *Full Broadcast with Image*\n\n"
            "Please send me the IMAGE you want to broadcast (from gallery or as a file).\n\n"
            "Type /cancel to cancel.",
            parse_mode=ParseMode.MARKDOWN
        )
        return FULL_IMAGE
    
    elif data == "admin_stats":
        users_count = len(get_all_users())
        scheduled = len(broadcast_manager.list_scheduled()) if broadcast_manager else 0
        await query.edit_message_text(
            f"📊 *Broadcast Statistics*\n\n"
            f"👥 Users in database: {users_count}\n"
            f"⏰ Scheduled broadcasts: {scheduled}\n",
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END
    
    elif data == "admin_scheduled":
        if not broadcast_manager:
            await query.edit_message_text("❌ Broadcast manager not initialized.")
            return ConversationHandler.END
        lst = broadcast_manager.list_scheduled()
        if not lst:
            await query.edit_message_text("📭 No scheduled broadcasts.", parse_mode=ParseMode.MARKDOWN)
            return ConversationHandler.END
        msg = "📋 *Scheduled Broadcasts:*\n\n"
        for bc in lst:
            remaining = int(bc['time'] - time_module.time())
            if remaining < 0:
                continue
            time_str = format_duration(remaining)
            bc_type = "📝 Text" if bc['type'] == 'text' else "🖼️ Photo"
            msg += f"`{bc['id']}` - {bc_type} - in {time_str}\n"
        msg += "\nUse `/cancel ID` to remove a scheduled broadcast."
        await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END
    
    elif data == "admin_close":
        await query.edit_message_text("❌ Admin panel closed.", parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END
    
    return ConversationHandler.END

# ========== SIMPLE BROADCAST CONVERSATION ==========
async def simple_text_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive text for simple broadcast"""
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ Unauthorized")
        return ConversationHandler.END
    
    text = update.message.text
    if text == "/cancel":
        await update.message.reply_text("❌ Broadcast cancelled.")
        return ConversationHandler.END
    
    temp_broadcast[user_id] = {'type': 'simple', 'message': text}
    
    await update.message.reply_text(
        f"✅ *Message received:*\n\n{text}\n\n"
        f"Now, please send the *duration* this message should stay visible.\n\n"
        f"Examples: `30m`, `2h`, `1d`, `0` (0 = never delete)\n\n"
        f"Type /cancel to cancel.",
        parse_mode=ParseMode.MARKDOWN
    )
    return SIMPLE_DURATION

async def simple_duration_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive duration for simple broadcast"""
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ Unauthorized")
        return ConversationHandler.END
    
    duration_str = update.message.text.strip()
    if duration_str == "/cancel":
        await update.message.reply_text("❌ Broadcast cancelled.")
        temp_broadcast.pop(user_id, None)
        return ConversationHandler.END
    
    try:
        if duration_str == "0":
            duration_sec = 0
        else:
            duration_sec = parse_duration(duration_str)
    except Exception as e:
        await update.message.reply_text(f"❌ Invalid duration. Use examples: `30m`, `2h`, `1d`, `0`\nError: {e}")
        return SIMPLE_DURATION
    
    temp_broadcast[user_id]['duration'] = duration_sec
    duration_text = "Never delete" if duration_sec == 0 else f"Will be deleted after {format_duration(duration_sec)}"
    
    keyboard = [
        [InlineKeyboardButton("✅ SEND NOW", callback_data="simple_send")],
        [InlineKeyboardButton("❌ CANCEL", callback_data="simple_cancel")]
    ]
    
    await update.message.reply_text(
        f"📝 *Review your broadcast:*\n\n"
        f"Message: {temp_broadcast[user_id]['message']}\n\n"
        f"⏰ Duration: {duration_text}\n\n"
        f"Click SEND NOW to broadcast to all {len(get_all_users())} users.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )
    return SIMPLE_CONFIRM

async def simple_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Confirm and send simple broadcast"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await query.edit_message_text("❌ Unauthorized")
        return ConversationHandler.END
    
    data = query.data
    
    if data == "simple_cancel":
        await query.edit_message_text("❌ Broadcast cancelled.")
        temp_broadcast.pop(user_id, None)
        return ConversationHandler.END
    
    if data == "simple_send":
        broadcast_data = temp_broadcast.get(user_id)
        if not broadcast_data:
            await query.edit_message_text("❌ No broadcast data found. Please start over.")
            return ConversationHandler.END
        
        users = get_all_users()
        if not users:
            await query.edit_message_text("⚠️ No users found in database.")
            temp_broadcast.pop(user_id, None)
            return ConversationHandler.END
        
        # Send a new message instead of editing
        status_msg = await context.bot.send_message(
            chat_id=user_id,
            text=f"📢 Sending simple broadcast to {len(users)} users..."
        )
        
        sent = 0
        failed = 0
        for uid in users:
            try:
                msg = await context.bot.send_message(
                    chat_id=int(uid),
                    text=broadcast_data['message'],
                    parse_mode=ParseMode.HTML
                )
                if broadcast_data['duration'] > 0:
                    deletion_manager.add_deletion(uid, msg.message_id, time_module.time() + broadcast_data['duration'])
                sent += 1
                await asyncio.sleep(0.05)
            except Exception as e:
                logger.error(f"Failed to send to {uid}: {e}")
                failed += 1
        
        duration_text = format_duration(broadcast_data['duration']) if broadcast_data['duration'] > 0 else "never"
        
        # Delete the status message and send final result
        await status_msg.delete()
        await context.bot.send_message(
            chat_id=user_id,
            text=f"✅ *Simple Broadcast Complete!*\n\n"
                 f"📤 Sent: {sent}\n"
                 f"❌ Failed: {failed}\n"
                 f"⏰ Messages will {'never be deleted' if broadcast_data['duration'] == 0 else f'be deleted after {duration_text}'}",
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Delete the review message
        try:
            await query.message.delete()
        except:
            pass
        
        temp_broadcast.pop(user_id, None)
        return ConversationHandler.END

# ========== FULL BROADCAST CONVERSATION ==========
async def full_image_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive image for full broadcast"""
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ Unauthorized")
        return ConversationHandler.END
    
    if not update.message.photo:
        await update.message.reply_text("❌ Please send an image (photo from gallery).")
        return FULL_IMAGE
    
    file_id = update.message.photo[-1].file_id
    temp_broadcast[user_id] = {'type': 'full', 'photo_id': file_id}
    
    await update.message.reply_text(
        f"✅ *Image received!*\n\n"
        f"Now, please send the *caption* for this image.\n\n"
        f"You can use HTML formatting: <b>bold</b>, <i>italic</i>, etc.\n\n"
        f"Type /cancel to cancel.",
        parse_mode=ParseMode.MARKDOWN
    )
    return FULL_CAPTION

async def full_caption_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive caption for full broadcast"""
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ Unauthorized")
        return ConversationHandler.END
    
    caption = update.message.text
    if caption == "/cancel":
        await update.message.reply_text("❌ Broadcast cancelled.")
        temp_broadcast.pop(user_id, None)
        return ConversationHandler.END
    
    temp_broadcast[user_id]['caption'] = caption
    
    await update.message.reply_text(
        f"✅ *Caption received!*\n\n"
        f"Now, please send the *button text* (or send 'skip' for no button).\n\n"
        f"Example: `Shop Now`\n\n"
        f"Type /cancel to cancel.",
        parse_mode=ParseMode.MARKDOWN
    )
    return FULL_BUTTON_TEXT

async def full_button_text_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive button text for full broadcast"""
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ Unauthorized")
        return ConversationHandler.END
    
    button_text = update.message.text
    if button_text == "/cancel":
        await update.message.reply_text("❌ Broadcast cancelled.")
        temp_broadcast.pop(user_id, None)
        return ConversationHandler.END
    
    if button_text.lower() == 'skip':
        temp_broadcast[user_id]['button_text'] = None
        temp_broadcast[user_id]['button_url'] = None
        await update.message.reply_text(
            f"⏭️ *No button will be added.*\n\n"
            f"Now, please send the *duration* this message should stay visible.\n\n"
            f"Examples: `30m`, `2h`, `1d`, `0` (0 = never delete)\n\n"
            f"Type /cancel to cancel.",
            parse_mode=ParseMode.MARKDOWN
        )
        return FULL_DURATION
    else:
        temp_broadcast[user_id]['button_text'] = button_text
        await update.message.reply_text(
            f"✅ *Button text saved:* {button_text}\n\n"
            f"Now, please send the *button URL* (link when clicked).\n\n"
            f"Example: `https://t.me/yourchannel`\n\n"
            f"Type /cancel to cancel.",
            parse_mode=ParseMode.MARKDOWN
        )
        return FULL_BUTTON_URL

async def full_button_url_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive button URL for full broadcast"""
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ Unauthorized")
        return ConversationHandler.END
    
    button_url = update.message.text
    if button_url == "/cancel":
        await update.message.reply_text("❌ Broadcast cancelled.")
        temp_broadcast.pop(user_id, None)
        return ConversationHandler.END
    
    temp_broadcast[user_id]['button_url'] = button_url
    
    await update.message.reply_text(
        f"✅ *Button URL saved:* {button_url}\n\n"
        f"Now, please send the *duration* this message should stay visible.\n\n"
        f"Examples: `30m`, `2h`, `1d`, `0` (0 = never delete)\n\n"
        f"Type /cancel to cancel.",
        parse_mode=ParseMode.MARKDOWN
    )
    return FULL_DURATION

async def full_duration_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive duration for full broadcast"""
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ Unauthorized")
        return ConversationHandler.END
    
    duration_str = update.message.text.strip()
    if duration_str == "/cancel":
        await update.message.reply_text("❌ Broadcast cancelled.")
        temp_broadcast.pop(user_id, None)
        return ConversationHandler.END
    
    try:
        if duration_str == "0":
            duration_sec = 0
        else:
            duration_sec = parse_duration(duration_str)
    except Exception as e:
        await update.message.reply_text(f"❌ Invalid duration. Use examples: `30m`, `2h`, `1d`, `0`\nError: {e}")
        return FULL_DURATION
    
    temp_broadcast[user_id]['duration'] = duration_sec
    duration_text = "Never delete" if duration_sec == 0 else f"Will be deleted after {format_duration(duration_sec)}"
    
    # Build preview
    preview_text = f"🖼️ *Review your broadcast:*\n\n"
    preview_text += f"Caption: {temp_broadcast[user_id]['caption']}\n\n"
    if temp_broadcast[user_id].get('button_text'):
        preview_text += f"🔘 Button: {temp_broadcast[user_id]['button_text']} → {temp_broadcast[user_id]['button_url']}\n\n"
    else:
        preview_text += f"🔘 No button\n\n"
    preview_text += f"⏰ Duration: {duration_text}\n\n"
    preview_text += f"📊 Will be sent to {len(get_all_users())} users."
    
    keyboard = [
        [InlineKeyboardButton("✅ SEND NOW", callback_data="full_send")],
        [InlineKeyboardButton("❌ CANCEL", callback_data="full_cancel")]
    ]
    
    # Send preview with image (store message ID for later deletion)
    try:
        sent_msg = await update.message.reply_photo(
            photo=temp_broadcast[user_id]['photo_id'],
            caption=preview_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        temp_broadcast[user_id]['preview_message_id'] = sent_msg.message_id
    except Exception as e:
        sent_msg = await update.message.reply_text(
            preview_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        temp_broadcast[user_id]['preview_message_id'] = sent_msg.message_id
    
    return FULL_CONFIRM

async def full_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Confirm and send full broadcast"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await query.edit_message_text("❌ Unauthorized")
        return ConversationHandler.END
    
    data = query.data
    
    if data == "full_cancel":
        await query.edit_message_text("❌ Broadcast cancelled.")
        temp_broadcast.pop(user_id, None)
        return ConversationHandler.END
    
    if data == "full_send":
        broadcast_data = temp_broadcast.get(user_id)
        if not broadcast_data:
            await query.edit_message_text("❌ No broadcast data found. Please start over.")
            return ConversationHandler.END
        
        users = get_all_users()
        if not users:
            await query.edit_message_text("⚠️ No users found in database.")
            temp_broadcast.pop(user_id, None)
            return ConversationHandler.END
        
        # Send a new status message
        status_msg = await context.bot.send_message(
            chat_id=user_id,
            text=f"📢 Sending full broadcast to {len(users)} users..."
        )
        
        keyboard = None
        if broadcast_data.get('button_text') and broadcast_data.get('button_url'):
            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton(broadcast_data['button_text'], url=broadcast_data['button_url'])
            ]])
        
        sent = 0
        failed = 0
        for uid in users:
            try:
                sent_msg = await context.bot.send_photo(
                    chat_id=int(uid),
                    photo=broadcast_data['photo_id'],
                    caption=broadcast_data['caption'],
                    reply_markup=keyboard,
                    parse_mode=ParseMode.HTML
                )
                if broadcast_data['duration'] > 0:
                    deletion_manager.add_deletion(uid, sent_msg.message_id, time_module.time() + broadcast_data['duration'])
                sent += 1
                await asyncio.sleep(0.05)
            except Exception as e:
                logger.error(f"Failed to send to {uid}: {e}")
                failed += 1
        
        duration_text = format_duration(broadcast_data['duration']) if broadcast_data['duration'] > 0 else "never"
        
        # Delete status message
        await status_msg.delete()
        
        # Delete preview message
        try:
            await context.bot.delete_message(
                chat_id=user_id,
                message_id=broadcast_data['preview_message_id']
            )
        except:
            pass
        
        # Send final result
        await context.bot.send_message(
            chat_id=user_id,
            text=f"✅ *Full Broadcast Complete!*\n\n"
                 f"📤 Sent: {sent}\n"
                 f"❌ Failed: {failed}\n"
                 f"⏰ Messages will {'never be deleted' if broadcast_data['duration'] == 0 else f'be deleted after {duration_text}'}",
            parse_mode=ParseMode.MARKDOWN
        )
        
        temp_broadcast.pop(user_id, None)
        return ConversationHandler.END

async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel the conversation"""
    user_id = update.effective_user.id
    temp_broadcast.pop(user_id, None)
    await update.message.reply_text("❌ Operation cancelled.")
    return ConversationHandler.END




