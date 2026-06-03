import os
import json
import asyncio
import time as time_module
import logging
from config import DELETIONS_FILE

logger = logging.getLogger(__name__)

class DeletionManager:
    def __init__(self, bot):
        self.bot = bot
        self.pending = {}
        self.load_pending()
        # Don't start cleaner in __init__, wait for event loop

    def load_pending(self):
        try:
            if os.path.exists(DELETIONS_FILE):
                with open(DELETIONS_FILE, 'r') as f:
                    self.pending = json.load(f)
                    logger.info(f"Loaded {len(self.pending)} pending deletions")
        except Exception as e:
            logger.error(f"Error loading deletions: {e}")

    def save_pending(self):
        try:
            with open(DELETIONS_FILE, 'w') as f:
                json.dump(self.pending, f)
        except Exception as e:
            logger.error(f"Error saving deletions: {e}")

    def add_deletion(self, chat_id, message_id, delete_at_timestamp):
        key = f"{chat_id}:{message_id}"
        self.pending[key] = delete_at_timestamp
        self.save_pending()
        # Schedule deletion without asyncio.create_task (use asyncio.run_coroutine_threadsafe if needed)
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._schedule_delete(chat_id, message_id, delete_at_timestamp))
        except RuntimeError:
            # No running loop, schedule later
            asyncio.get_event_loop().create_task(self._schedule_delete(chat_id, message_id, delete_at_timestamp))

    async def _schedule_delete(self, chat_id, message_id, delete_at):
        now = time_module.time()
        delay = delete_at - now
        if delay > 0:
            await asyncio.sleep(delay)
        try:
            await self.bot.delete_message(chat_id=chat_id, message_id=message_id)
            logger.info(f"Deleted message {message_id} in chat {chat_id}")
        except Exception as e:
            logger.error(f"Failed to delete {message_id}: {e}")
        key = f"{chat_id}:{message_id}"
        if key in self.pending:
            del self.pending[key]
            self.save_pending()

    async def start_cleaner(self):
        """Start cleaner after event loop is running"""
        for key, ts in list(self.pending.items()):
            if ts > time_module.time():
                chat_id, message_id = key.split(':')
                asyncio.create_task(self._schedule_delete(int(chat_id), int(message_id), ts))
