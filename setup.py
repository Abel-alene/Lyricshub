#!/usr/bin/env python
"""
Lyrics Hub Bot - Setup Script
Guides users through installation and configuration.
"""

import os
import sys
import subprocess
import platform
from pathlib import Path

def print_header(text):
    """Print a formatted header"""
    print("\n" + "=" * 50)
    print(f" {text}")
    print("=" * 50)

def print_success(text):
    """Print success message"""
    print(f"✅ {text}")

def print_error(text):
    """Print error message"""
    print(f"❌ {text}")

def print_info(text):
    """Print info message"""
    print(f"📋 {text}")

def check_python():
    """Check if Python 3.8+ is installed"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print_error(f"Python 3.8+ required. You have {version.major}.{version.minor}")
        print_info("Download from: https://python.org/downloads/")
        return False
    print_success(f"Python {version.major}.{version.minor}.{version.micro} found")
    return True

def check_pip():
    """Check if pip is installed"""
    try:
        subprocess.run([sys.executable, "-m", "pip", "--version"], 
                      capture_output=True, check=True)
        print_success("pip found")
        return True
    except:
        print_error("pip not found")
        print_info("Install pip: https://pip.pypa.io/en/stable/installation/")
        return False

def install_requirements():
    """Install required packages"""
    print_info("Installing dependencies...")
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], 
                      check=True)
        print_success("All dependencies installed")
        return True
    except subprocess.CalledProcessError as e:
        print_error(f"Failed to install dependencies: {e}")
        return False

def get_bot_token():
    """Get BOT_TOKEN from user"""
    print("\n" + "=" * 50)
    print(" 🔑 Bot Token Required")
    print("=" * 50)
    print("Get your bot token from @BotFather on Telegram.")
    print("1. Open Telegram")
    print("2. Search for @BotFather")
    print("3. Send /newbot")
    print("4. Follow instructions to create a bot")
    print("5. Copy the token (looks like: 123456:ABC-DEF-GHI)")
    print("=" * 50)
    
    while True:
        token = input("\n🤖 Enter your bot token: ").strip()
        if token:
            return token
        print_error("Token cannot be empty. Please try again.")

def create_env_file(token):
    """Create .env file with the token"""
    env_content = f"""# Telegram Bot Configuration
BOT_TOKEN={token}
"""
    try:
        with open(".env", "w") as f:
            f.write(env_content)
        print_success(".env file created")
        return True
    except Exception as e:
        print_error(f"Failed to create .env: {e}")
        return False

def test_bot():
    """Ask user if they want to start the bot"""
    print("\n" + "=" * 50)
    print(" ✅ Setup Complete!")
    print("=" * 50)
    print("Your bot is ready to run!")
    print("\nTo start the bot, run:")
    print("  python run.py")
    
    while True:
        response = input("\n🚀 Start bot now? (y/n): ").strip().lower()
        if response in ['y', 'yes']:
            return True
        elif response in ['n', 'no']:
            return False
        print("Please enter 'y' or 'n'")

def run_bot():
    """Start the bot"""
    print("\n" + "=" * 50)
    print(" 🚀 Starting Bot...")
    print("=" * 50)
    print("Press Ctrl+C to stop\n")
    
    try:
        subprocess.run([sys.executable, "run.py"], check=True)
    except KeyboardInterrupt:
        print("\n\n👋 Bot stopped.")
    except Exception as e:
        print_error(f"Error running bot: {e}")

def main():
    """Main setup function"""
    print_header("🎵 Lyrics Hub Bot - Setup")
    
    # Step 1: Check Python
    if not check_python():
        sys.exit(1)
    
    # Step 2: Check pip
    if not check_pip():
        sys.exit(1)
    
    # Step 3: Install requirements
    if not install_requirements():
        sys.exit(1)
    
    # Step 4: Get bot token
    token = get_bot_token()
    
    # Step 5: Create .env file
    if not create_env_file(token):
        sys.exit(1)
    
    # Step 6: Ask to start bot
    if test_bot():
        run_bot()
    else:
        print("\n✅ Setup complete! Run 'python run.py' to start your bot.")

if __name__ == "__main__":
    main()
