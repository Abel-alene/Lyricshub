import json
import logging
from pathlib import Path
from typing import List, Set

logger = logging.getLogger(__name__)

class UserDatabase:
    """Simple JSON-based user database"""
    
    def __init__(self, data_dir: Path):
        self._users: Set[int] = set()
        self._file_path = data_dir / 'users.json'
        self._load()
    
    def _load(self):
        """Load users from file"""
        try:
            if self._file_path.exists():
                with open(self._file_path, 'r') as f:
                    data = json.load(f)
                    self._users = set(data)
                logger.info(f"Loaded {len(self._users)} users")
        except Exception as e:
            logger.error(f"Error loading users: {e}")
            self._users = set()
    
    def _save(self):
        """Save users to file"""
        try:
            with open(self._file_path, 'w') as f:
                json.dump(list(self._users), f)
        except Exception as e:
            logger.error(f"Error saving users: {e}")
    
    def add(self, user_id: int):
        """Add a user to the database"""
        self._users.add(user_id)
        self._save()
    
    def get_all(self) -> List[int]:
        """Get all users"""
        return list(self._users)
    
    def count(self) -> int:
        """Get total user count"""
        return len(self._users)
