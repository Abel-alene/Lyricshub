import os
import json
import logging
from config import USERS_FILE

logger = logging.getLogger(__name__)

# Global stores
user_database = set()

def load_users():
    global user_database
    try:
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, 'r') as f:
                data = json.load(f)
                user_database = set(data)
                logger.info(f"Loaded {len(user_database)} users")
    except Exception as e:
        logger.error(f"Error loading users: {e}")

def save_users():
    try:
        with open(USERS_FILE, 'w') as f:
            json.dump(list(user_database), f)
    except Exception as e:
        logger.error(f"Error saving users: {e}")

def add_user(user_id):
    user_database.add(user_id)
    save_users()

def get_all_users():
    return list(user_database)
