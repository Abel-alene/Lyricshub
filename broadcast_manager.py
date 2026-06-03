import os
import json
import asyncio
import time as time_module
import logging
from threading import Thread
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from config import BROADCAST_FILE
from database import get_all_users
from deletion_manager import DeletionManager
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode


logger = logging.getLogger(__name__)

deletion_manager = None

def set_deletion_manager(dm):
    global deletion_manager
    deletion_manager = dm

class BroadcastManager:
    def __init__(self, bot):
        self.bot = bot
        self.scheduled_broadcasts = []
        self.load_broadcasts()
        self.start_scheduler()

    def load_broadcasts(self):
        try:
            if os.path.exists(BROADCAST_FILE):
                with open(BROADCAST_FILE, 'r') as f:
                    self.scheduled_broadcasts = json.load(f)
                logger.info(f"Loaded {len(self.scheduled_broadcasts)} scheduled broadcasts")
        except Exception as e:
            logger.error(f"Error loading broadcasts: {e}")

    def save_broadcasts(self):
        try:
            with open(BROADCAST_FILE, 'w') as f:
                json.dump(self.scheduled_broadcasts, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving broadcasts: {e}")

    def start_scheduler(self):
        def check_schedule():
            while True:
                try:
                    now = time_module.time()
                    for bc in self.scheduled_broadcasts[:]:
                        if bc['time'] <= now:
                            asyncio.run_coroutine_threadsafe(
                                self.send_broadcast(bc),
                                asyncio.get_event_loop()
                            )
                            self.scheduled_broadcasts.remove(bc)
                            self.save_broadcasts()
                    time_module.sleep(30)
                except Exception as e:
                    logger.error(f"Scheduler error: {e}")
                    time_module.sleep(60)
        thread = Thread(target=check_schedule, daemon=True)
        thread.start()

    async def send_broadcast(self, broadcast):
        users = get_all_users()
        if not users:
            return
        for user_id in users:
            try:
                if broadcast['type'] == 'text':
                    msg = await self.bot.send_message(
                        chat_id=int(user_id),
                        text=broadcast['message'],
                        parse_mode=ParseMode.HTML
                    )
                    if broadcast.get('duration_sec'):
                        deletion_manager.add_deletion(user_id, msg.message_id, time_module.time() + broadcast['duration_sec'])
                elif broadcast['type'] == 'photo':
                    keyboard = None
                    if broadcast.get('button_text') and broadcast.get('button_url'):
                        keyboard = InlineKeyboardMarkup([[
                            InlineKeyboardButton(broadcast['button_text'], url=broadcast['button_url'])
                        ]])
                    sent = await self.bot.send_photo(
                        chat_id=int(user_id),
                        photo=broadcast['photo_id'],
                        caption=broadcast['caption'],
                        reply_markup=keyboard,
                        parse_mode=ParseMode.HTML
                    )
                    if broadcast.get('duration_sec'):
                        deletion_manager.add_deletion(user_id, sent.message_id, time_module.time() + broadcast['duration_sec'])
                await asyncio.sleep(0.05)
            except Exception as e:
                logger.error(f"Failed to send to {user_id}: {e}")

    def add_scheduled(self, broadcast_data):
        broadcast_data['id'] = int(time_module.time())
        self.scheduled_broadcasts.append(broadcast_data)
        self.save_broadcasts()
        return broadcast_data['id']

    def remove_scheduled(self, broadcast_id):
        for bc in self.scheduled_broadcasts[:]:
            if bc['id'] == broadcast_id:
                self.scheduled_broadcasts.remove(bc)
                self.save_broadcasts()
                return True
        return False

    def list_scheduled(self):
        return self.scheduled_broadcasts
