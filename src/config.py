import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Base directory
BASE_DIR = Path(__file__).resolve().parent.parent

class Config:
    """Application configuration"""
    
    # Telegram
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    
    # App settings
    ITEMS_PER_PAGE = 10
    
    # Directories
    DATA_DIR = BASE_DIR / 'data'
    LOGS_DIR = BASE_DIR / 'logs'
    
    @classmethod
    def validate(cls):
        """Check if all required configuration is present"""
        if not cls.BOT_TOKEN:
            return False, "❌ BOT_TOKEN is missing!\n   Get one from @BotFather on Telegram"
        return True, "✅ Configuration looks good!"
    
    @classmethod
    def setup_directories(cls):
        """Create required directories"""
        for directory in [cls.DATA_DIR, cls.LOGS_DIR]:
            directory.mkdir(parents=True, exist_ok=True)

# Create config instance
config = Config()
