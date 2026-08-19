import re
import unicodedata

def sanitize_input(text: str) -> str:
    """
    Clean user input of invisible characters, homoglyphs,
    and control characters. Run this BEFORE injection detection.
    """
    # 1. Remove zero-width / invisible characters
    INVISIBLE = '\u200b\u200c\u200d\u2060\ufeff\u00ad\u200e\u200f'
    for char in INVISIBLE:
        text = text.replace(char, '')

    # 2. Normalize unicode (Cyrillic 'а' → Latin 'a', etc.)
    text = unicodedata.normalize('NFKC', text)

    # 3. Remove control characters (keep newline, tab, carriage return)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)

    # 4. Collapse excessive whitespace
    text = re.sub(r' {10,}', ' ', text)      # 10+ spaces → 1
    text = re.sub(r'\n{5,}', '\n\n', text)   # 5+ newlines → 2

    return text.strip()


def contains_encoding_attack(text: str) -> bool:
    """
    Detect base64 or hex-encoded payloads that might hide injection.
    """
    # Base64 blocks (40+ alphanumeric chars with optional padding)
    if re.search(r'[A-Za-z0-9+/]{40,}={0,2}', text):
        return True
    # Hex-encoded strings
    if re.search(r'(?:0x[0-9a-fA-F]{2}\s*){10,}', text):
        return True
    return False
