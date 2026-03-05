import os
import re
from urllib.parse import quote


def auth_enabled(password: str) -> bool:
    return bool((password or "").strip())


def requires_auth(path: str) -> bool:
    return path == "/" or path.startswith("/downloads")


def is_authenticated(cookies: dict, cookie_name: str, cookie_value: str) -> bool:
    return cookies.get(cookie_name) == cookie_value


def resolve_download_root(cwd: str) -> str:
    return os.path.abspath(os.path.join(cwd, "downloads"))


def build_download_url(target_path: str, downloads_root: str) -> str | None:
    abs_downloads_path = os.path.abspath(downloads_root)
    abs_target_path = os.path.abspath(target_path)
    if not abs_target_path.startswith(abs_downloads_path + os.sep) and abs_target_path != abs_downloads_path:
        return None
    rel_path = os.path.relpath(abs_target_path, abs_downloads_path).replace(os.sep, "/")
    return f"/downloads/{quote(rel_path, safe='/')}"


def rewrite_markdown_links(content: str, markdown_path: str, downloads_root: str) -> str:
    base_dir = os.path.dirname(markdown_path)
    pattern = re.compile(r"(!?\[[^\]]*\]\()([^)]+)(\))")

    def replace_link(match):
        raw_target = match.group(2).strip()
        if raw_target.startswith("<") and raw_target.endswith(">"):
            raw_target = raw_target[1:-1]
        if raw_target.startswith(("http://", "https://", "data:", "mailto:", "#", "/")):
            return match.group(0)
        local_path = os.path.normpath(os.path.join(base_dir, raw_target))
        download_url = build_download_url(local_path, downloads_root)
        if not download_url:
            return match.group(0)
        return f"{match.group(1)}{download_url}{match.group(3)}"

    return pattern.sub(replace_link, content)


def format_size(size_bytes: int) -> str:
    value = float(size_bytes)
    unit = "B"
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if value < 1024:
            break
        value /= 1024
    return f"{value:.2f} {unit}"


def build_tree_nodes(path: str, root_path: str = None) -> list[dict]:
    try:
        if not os.path.isdir(path):
            return []
            
        if root_path is None:
            root_path = path

        items = sorted(os.listdir(path))
        items.sort(key=lambda x: (not os.path.isdir(os.path.join(path, x)), x))
        nodes = []
        for item in items:
            if item.startswith("."):
                continue
            full_path = os.path.join(path, item)
            
            # Use relative path from the initial root call for ID
            # If we are in a subdir, root_path should be preserved from top level call?
            # No, bridge.py calls this with target_path as path.
            # If we want ID to be relative to DOWNLOADS root, we need to pass downloads root.
            # But bridge.py passes target_path which is root+path.
            
            # Actually, let's make it simple: ID is the filename if in root, or path/filename.
            # But here we don't know the global root if not passed.
            # Let's rely on bridge.py passing the correct root context or just return basename if we want relative?
            # No, frontend needs path to call API again.
            
            # Let's assume the caller (bridge.py) handles the root resolution for us?
            # bridge.py calls build_tree_nodes(target_path).
            # If we want IDs to be usable for next API call, they should be relative to Downloads root.
            # But build_tree_nodes doesn't know Downloads root.
            
            # Let's change signature to accept base_rel_path?
            
            is_dir = os.path.isdir(full_path)
            node = {"id": item, "label": item} # ID is just name for now, we will construct path in frontend?
            # Or we construct relative path here.
            
            if is_dir:
                node["icon"] = "folder"
                node["children"] = [] # Empty list to signify it's a folder for frontend check
            else:
                if item.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")):
                    node["icon"] = "image"
                elif item.lower().endswith(".md"):
                    node["icon"] = "description"
                else:
                    node["icon"] = "insert_drive_file"
            nodes.append(node)
        return nodes
    except OSError:
        return []
