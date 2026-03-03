import re


def sanitize_filename(value: str, max_length: int = 150) -> str:
    text = (value or "").strip()
    if not text:
        return "untitled"
    text = re.sub(r"[\\/:*?\"<>|\r\n\t]+", "_", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_length:
        text = text[:max_length].rstrip()
    return text or "untitled"
