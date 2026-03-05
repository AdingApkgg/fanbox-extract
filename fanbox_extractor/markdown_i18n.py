import os
import re

import requests


_TRANSLATE_URL = "https://translate.googleapis.com/translate_a/single"
_PROTECTED_PATTERN = re.compile(
    r"`[^`]*`|!\[[^\]]*\]\([^)]+\)|\[[^\]]*\]\([^)]+\)|https?://\S+"
)


def _translate_text(session: requests.Session, text: str, timeout: int) -> str:
    response = session.get(
        _TRANSLATE_URL,
        params={
            "client": "gtx",
            "sl": "auto",
            "tl": "zh-CN",
            "dt": "t",
            "q": text,
        },
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, list) or not data:
        return text
    chunks = data[0]
    if not isinstance(chunks, list):
        return text
    return "".join(item[0] for item in chunks if isinstance(item, list) and item and item[0])


def _protect_segments(text: str) -> tuple[str, dict[str, str]]:
    placeholders: dict[str, str] = {}
    cursor = 0
    parts: list[str] = []
    for idx, match in enumerate(_PROTECTED_PATTERN.finditer(text)):
        start, end = match.span()
        token = f"__PH_{idx}__"
        parts.append(text[cursor:start])
        parts.append(token)
        placeholders[token] = match.group(0)
        cursor = end
    parts.append(text[cursor:])
    return "".join(parts), placeholders


def _restore_segments(text: str, placeholders: dict[str, str]) -> str:
    restored = text
    for token, value in placeholders.items():
        restored = restored.replace(token, value)
    return restored


def translate_markdown_to_zh(markdown_text: str, request_timeout: int = 20) -> str:
    lines = markdown_text.splitlines()
    translated_lines: list[str] = []
    in_fence = False
    with requests.Session() as session:
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("```"):
                in_fence = not in_fence
                translated_lines.append(line)
                continue
            if in_fence or not stripped:
                translated_lines.append(line)
                continue
            protected, placeholders = _protect_segments(line)
            translated = _translate_text(session, protected, request_timeout)
            translated_lines.append(_restore_segments(translated, placeholders))
    return "\n".join(translated_lines)


def write_bilingual_readmes(
    post_dir: str,
    markdown_text: str,
    callback=None,
    request_timeout: int = 20,
) -> None:
    readme_path = os.path.join(post_dir, "README.md")
    with open(readme_path, "w", encoding="utf-8") as readme_file:
        readme_file.write(markdown_text)

    readme_zh_path = os.path.join(post_dir, "README.zh.md")
    try:
        translated = translate_markdown_to_zh(markdown_text, request_timeout=request_timeout)
    except Exception as error:
        translated = markdown_text
        message = f"Translation failed for {post_dir}: {error}"
        if callback:
            callback(message)
        else:
            print(message)
    with open(readme_zh_path, "w", encoding="utf-8") as readme_zh_file:
        readme_zh_file.write(translated)
