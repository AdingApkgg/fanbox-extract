import re
import os

def sanitize_filename(name):
    """Sanitize filename to be safe for filesystem."""
    if not name:
        return "untitled"
    # Replace illegal characters
    name = re.sub(r'[\\/*?:"<>|]', '_', name)
    # Remove control characters
    name = "".join(c for c in name if c.isprintable())
    return name.strip()[:100]  # Limit length

def extract_links_from_text(text):
    """Helper to find URLs in text."""
    if not text:
        return []
    found = re.findall(r'https?://[^\s<>"]+|www\.[^\s<>"]+', text)
    cleaned = []
    for link in found:
        if link.endswith('.'): link = link[:-1]
        if link.endswith(')'): link = link[:-1]
        cleaned.append(link)
    return cleaned
