from src.utils.helpers import remove_timestamps, clean_text

def format_lyrics(raw_lyrics: str) -> str:
    """Clean and format lyrics for display"""
    if not raw_lyrics:
        return "❌ No lyrics available."
    
    # Remove timestamps
    lyrics = remove_timestamps(raw_lyrics)
    
    # Clean text
    lyrics = clean_text(lyrics)
    
    # Truncate if too long (Telegram limit is 4096)
    if len(lyrics) > 3500:
        lyrics = lyrics[:3500] + "\n\n... (lyrics truncated)"
    
    return lyrics
