import re

def clean_text(text: str) -> str:
    """Remove problematic characters from text"""
    if not text:
        return ""
    text = text.replace('\x00', '')
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    return text

def remove_timestamps(lyrics: str) -> str:
    """Remove timestamp markers like [00:13.42] from lyrics"""
    if not lyrics:
        return ""
    # Remove timestamps like [00:13.42]
    lyrics = re.sub(r'\[\d{2}:\d{2}\.\d{2}\]', '', lyrics)
    # Remove empty lines
    lyrics = re.sub(r'\n\s*\n', '\n', lyrics)
    return lyrics.strip()

def escape_markdown(text: str) -> str:
    """Escape special characters for Markdown"""
    if not text:
        return ""
    special_chars = r'_*[]()~`>#+-=|{}.!'
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text
