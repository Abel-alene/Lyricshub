#!/usr/bin/env python
"""
Lyrics Hub Bot - Entry Point
Validates configuration then starts the bot.
"""

import sys
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.config import config
from src.bot import LyricsBot

def main():
    """Main entry point"""
    print("\n" + "=" * 50)
    print("🎵 Lyrics Hub Bot")
    print("=" * 50)
    
    # Validate configuration
    valid, message = config.validate()
    
    if not valid:
        print(f"\n❌ {message}")
        print("\n💡 Setup Instructions:")
        print("1. Create a .env file with your BOT_TOKEN")
        print("2. Or run: python setup.py to set up automatically")
        print("=" * 50)
        sys.exit(1)
    
    print(f"\n✅ {message}")
    print("🚀 Starting bot...")
    print("=" * 50 + "\n")
    
    # Create and run bot
    bot = LyricsBot()
    bot.run()

if __name__ == "__main__":
    main()
