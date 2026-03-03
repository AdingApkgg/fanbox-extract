import os
import re
import sys
import threading
import asyncio
import hmac
import secrets
from urllib.parse import quote
from nicegui import ui, app
from dotenv import load_dotenv
from starlette.requests import Request
from starlette.responses import RedirectResponse
from fanbox_extractor.downloader import FanboxDownloader
from fanbox_extractor.patreon_downloader import PatreonDownloader

# Global state
downloader_instance = None
creators_list = []
selected_creator_id = None
is_running = False
load_dotenv()
WEB_UI_PASSWORD = os.environ.get("WEB_UI_PASSWORD", "").strip()
AUTH_COOKIE_NAME = "fanbox_ui_auth"
AUTH_COOKIE_VALUE = secrets.token_urlsafe(32)

def auth_enabled():
    return bool(WEB_UI_PASSWORD)

def is_authenticated(request: Request):
    if not auth_enabled():
        return True
    return request.cookies.get(AUTH_COOKIE_NAME) == AUTH_COOKIE_VALUE

def requires_auth(path: str):
    if path == "/":
        return True
    return path.startswith("/downloads")

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    if not auth_enabled():
        return await call_next(request)
    path = request.url.path
    if path == "/login":
        return await call_next(request)
    if requires_auth(path) and not is_authenticated(request):
        return RedirectResponse(url="/login", status_code=303)
    return await call_next(request)

def init_downloader(sessid):
    global downloader_instance
    try:
        downloader_instance = FanboxDownloader(sessid)
        return True
    except Exception as e:
        ui.notify(f"Error initializing downloader: {e}", type='negative')
        return False

def init_patreon_downloader(rss_url, creator_id):
    global downloader_instance
    try:
        downloader_instance = PatreonDownloader(rss_url=rss_url, creator_id=creator_id or "patreon")
        return True
    except Exception as e:
        ui.notify(f"Error initializing Patreon downloader: {e}", type='negative')
        return False

def fetch_creators():
    global creators_list, downloader_instance
    if not downloader_instance: return []
    
    try:
        creators = downloader_instance.fetch_supporting_creators()
        # NiceGUI select options can be a list of strings OR a dictionary {value: label}
        # A list of dicts [{'label':..., 'value':...}] is for Quasar, but NiceGUI wrapper handles dicts better
        # Let's return a dictionary for options
        options = {}
        for c in creators:
            label = f"{c.get('title', 'No Title')} ({c.get('creatorId')})"
            value = c.get('creatorId')
            options[value] = label
        return options
    except Exception as e:
        ui.notify(f"Error fetching creators: {e}", type='negative')
        return {}

@ui.page('/')
def main_page():
    if auth_enabled():
        with ui.row().classes('w-full justify-end max-w-2xl mx-auto pt-4'):
            ui.button(
                'Logout',
                icon='logout',
                color='grey',
                on_click=lambda: ui.run_javascript(
                    f"document.cookie = '{AUTH_COOKIE_NAME}=; Max-Age=0; path=/; SameSite=Lax'; window.location.href='/login';"
                ),
            ).props('outline')
    
    # UI Elements
    with ui.tabs().classes('w-full') as tabs:
        ui.tab('Download', icon='download')
        ui.tab('Manage', icon='folder')

    with ui.tab_panels(tabs, value='Download').classes('w-full'):
        
        # --- Download Tab ---
        with ui.tab_panel('Download'):
            with ui.card().classes('w-full max-w-2xl mx-auto p-4 gap-4'):
                ui.label('Creator Extractor').classes('text-2xl font-bold mb-4')
                
                # Connection Section
                platform_select = ui.select(
                    options={"fanbox": "FANBOX", "patreon": "Patreon"},
                    value="fanbox",
                    label="Platform",
                ).classes('w-full')
                with ui.row().classes('w-full items-center gap-2'):
                    sessid_input = ui.input(label='FANBOXSESSID', password=True).classes('flex-grow')
                    default_sessid = os.environ.get("FANBOXSESSID", "")
                    if default_sessid:
                        sessid_input.value = default_sessid
                    connect_btn = ui.button('Connect', on_click=lambda: on_connect())
                with ui.column().classes('w-full hidden') as patreon_inputs:
                    patreon_rss_input = ui.input(
                        label='Patreon RSS URL',
                        placeholder='https://www.patreon.com/rss?...'
                    ).classes('w-full')
                    default_patreon_rss = os.environ.get("PATREON_RSS_URL", "")
                    if default_patreon_rss:
                        patreon_rss_input.value = default_patreon_rss
                    patreon_creator_input = ui.input(
                        label='Creator ID',
                        value='patreon'
                    ).classes('w-full')
                
                # Creator Section
                creator_select = ui.select(options={}, label='Select Creator').classes('w-full hidden')
                
                # Options Section
                with ui.expansion('Advanced Options').classes('w-full hidden') as advanced_options:
                    with ui.column().classes('w-full gap-2'):
                        skip_existing = ui.checkbox('Skip existing files', value=True)
                        extract_archives = ui.checkbox('Extract links from archives', value=True)
                        parallel_downloads = ui.slider(min=1, max=10, value=5, step=1).props('label-always')
                        ui.label('Parallel Downloads').classes('text-xs text-gray-500')

                # Control Section
                control_row = ui.row().classes('w-full gap-2 hidden')
                with control_row:
                    start_btn = ui.button('Start Download', on_click=lambda: start_download()).classes('flex-grow')
                    stop_btn = ui.button('Stop', color='red', on_click=lambda: stop_download()).classes('w-24')
                    stop_btn.disable()
                
                # Status Section
                progress_bar = ui.linear_progress(value=0).classes('w-full hidden')
                status_label = ui.label('').classes('text-sm text-gray-500 hidden')
                
                # Logs
                log_expansion = ui.expansion('Logs', value=True).classes('w-full hidden')
                with log_expansion:
                    log_area = ui.log().classes('w-full h-64 bg-gray-100 p-2 rounded text-xs font-mono')

        # --- Manage Tab ---
        with ui.tab_panel('Manage'):
             with ui.row().classes('w-full h-[calc(100vh-150px)] gap-0'):
                # Left Sidebar: File Tree
                with ui.column().classes('w-1/3 h-full border-r p-2 overflow-auto'):
                    ui.label('Downloaded Posts').classes('font-bold mb-2')
                    with ui.row().classes('w-full gap-2 mb-2'):
                        ui.button('Refresh', icon='refresh', on_click=lambda: refresh_file_tree()).classes('flex-grow')
                        ui.button('Collapse', icon='unfold_less', on_click=lambda: file_tree.collapse()).classes('w-auto')
                    
                    file_tree = ui.tree([], label_key='label', on_select=lambda e: on_file_select(e)).classes('w-full')
                
                # Right Content: Preview
                with ui.column().classes('w-2/3 h-full p-4 overflow-auto bg-gray-50'):
                    preview_container = ui.column().classes('w-full')
                    with preview_container:
                        ui.label('Select a file to preview').classes('text-gray-400 italic')

    # --- Logic for Download Tab ---
    def show_download_controls():
        control_row.classes(remove='hidden')
        advanced_options.classes(remove='hidden')
        progress_bar.classes(remove='hidden')
        status_label.classes(remove='hidden')
        log_expansion.classes(remove='hidden')

    def on_platform_change(e):
        is_fanbox = e.value == "fanbox"
        if is_fanbox:
            sessid_input.classes(remove='hidden')
            if creator_select.options:
                creator_select.classes(remove='hidden')
            else:
                creator_select.classes(add='hidden')
            patreon_inputs.classes(add='hidden')
        else:
            sessid_input.classes(add='hidden')
            creator_select.classes(add='hidden')
            patreon_inputs.classes(remove='hidden')

    platform_select.on_value_change(on_platform_change)
    on_platform_change(type("Event", (), {"value": platform_select.value})())

    def on_connect():
        if platform_select.value == "patreon":
            rss_url = (patreon_rss_input.value or "").strip()
            creator_id = (patreon_creator_input.value or "patreon").strip()
            if not rss_url:
                ui.notify("Please enter Patreon RSS URL", type='warning')
                return
            if init_patreon_downloader(rss_url, creator_id):
                show_download_controls()
                ui.notify("Connected to Patreon RSS.", type='positive')
                refresh_file_tree()
            return

        sessid = sessid_input.value
        if not sessid:
            ui.notify("Please enter FANBOXSESSID", type='warning')
            return
        if init_downloader(sessid):
            creators = fetch_creators()
            if creators:
                creator_select.options = creators
                creator_select.update()
                creator_select.classes(remove='hidden')
                ui.notify("Connected! Please select a creator.", type='positive')

                def on_creator_change(e):
                    if e.value and downloader_instance:
                        downloader_instance.set_creator(e.value)
                        show_download_controls()
                        refresh_file_tree()

                creator_select.on_value_change(on_creator_change)
            else:
                ui.notify("Connected, but no supporting creators found.", type='warning')

    async def start_download():
        global is_running
        if is_running: return
        if not downloader_instance:
            ui.notify("Please connect first", type='warning')
            return
        dl = downloader_instance
        is_running = True
        start_btn.disable()
        stop_btn.enable()
        connect_btn.disable()
        if platform_select.value == "fanbox":
            creator_select.disable()
        else:
            patreon_rss_input.disable()
            patreon_creator_input.disable()
        
        progress_bar.value = 0
        log_area.clear()
        
        def update_progress(val):
            progress_bar.value = val
            
        def update_status(msg):
            status_label.text = msg
            log_area.push(msg)
            
        try:
            workers = int(parallel_downloads.value)
            skip_existing_enabled = bool(skip_existing.value)
            extract_archives_enabled = bool(extract_archives.value)
            dl.clear_stop()
            await asyncio.to_thread(
                dl.run, 
                progress_callback=update_progress, 
                status_callback=update_status,
                max_workers=workers,
                skip_existing=skip_existing_enabled,
                extract_archives=extract_archives_enabled,
            )
            ui.notify("Download Finished!", type='positive')
            refresh_file_tree()
        except Exception as e:
            ui.notify(f"Download Error: {e}", type='negative')
            log_area.push(f"Error: {e}")
        finally:
            is_running = False
            start_btn.enable()
            stop_btn.disable()
            connect_btn.enable()
            if platform_select.value == "fanbox":
                creator_select.enable()
            else:
                patreon_rss_input.enable()
                patreon_creator_input.enable()

    def stop_download():
        if downloader_instance:
            downloader_instance.request_stop()
            ui.notify("Stopping download...", type='warning')

    # --- Logic for Manage Tab ---
    def get_download_path():
        if downloader_instance and downloader_instance.base_dir:
            return downloader_instance.base_dir
        # Fallback to default downloads dir if no creator selected yet
        # But usually we want to see downloads for current creator
        return None

    def refresh_file_tree():
        base_path = get_download_path()
        
        # If no creator selected, try to show the root downloads folder
        if not base_path:
             base_path = os.path.join(os.getcwd(), 'downloads')
             
        if not os.path.exists(base_path):
            file_tree._props['nodes'] = []
            file_tree.update()
            ui.notify(f"Directory not found: {base_path}", type='warning')
            return

        def build_nodes(path, depth=0):
            # if depth > 2: return [] # Limit depth if needed, but let's try without
            try:
                nodes = []
                # Check if path exists and is a directory
                if not os.path.isdir(path): return []
                
                items = sorted(os.listdir(path))
                # Sort: folders first, then files
                items.sort(key=lambda x: (not os.path.isdir(os.path.join(path, x)), x))
                
                for item in items:
                    if item.startswith('.'): continue
                    full_path = os.path.join(path, item)
                    is_dir = os.path.isdir(full_path)
                    
                    # IMPORTANT: Tree node ID must be unique. Using full path is good.
                    node = {'id': full_path, 'label': item}
                    
                    if is_dir:
                        node['icon'] = 'folder'
                        # Recursively build children
                        node['children'] = build_nodes(full_path, depth + 1)
                    else:
                        node['icon'] = 'description' if item.lower().endswith('.md') else 'insert_drive_file'
                        if item.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
                            node['icon'] = 'image'
                            
                    nodes.append(node)
                return nodes
            except OSError as e:
                print(f"Error reading {path}: {e}")
                return []

        # Clear existing nodes first
        file_tree.clear()
        nodes = build_nodes(base_path)
        file_tree._props['nodes'] = nodes
        file_tree.update()
        # ui.notify(f"Loaded {len(nodes)} items from {base_path}")

    def build_download_url(target_path):
        abs_downloads_path = os.path.abspath(os.path.join(os.getcwd(), 'downloads'))
        abs_target_path = os.path.abspath(target_path)
        if not abs_target_path.startswith(abs_downloads_path + os.sep) and abs_target_path != abs_downloads_path:
            return None
        rel_path = os.path.relpath(abs_target_path, abs_downloads_path).replace(os.sep, '/')
        return f"/downloads/{quote(rel_path, safe='/')}"

    def rewrite_markdown_links(content, markdown_path):
        base_dir = os.path.dirname(markdown_path)
        pattern = re.compile(r'(!?\[[^\]]*\]\()([^)]+)(\))')

        def replace_link(match):
            raw_target = match.group(2).strip()
            if raw_target.startswith('<') and raw_target.endswith('>'):
                raw_target = raw_target[1:-1]
            if raw_target.startswith(('http://', 'https://', 'data:', 'mailto:', '#', '/')):
                return match.group(0)
            local_path = os.path.normpath(os.path.join(base_dir, raw_target))
            download_url = build_download_url(local_path)
            if not download_url:
                return match.group(0)
            return f'{match.group(1)}{download_url}{match.group(3)}'

        return pattern.sub(replace_link, content)

    def on_file_select(e):
        # e.value is the node id (which is our path now)
        filepath = e.value
        if not filepath: return
        
        # If it's a directory, maybe toggle expansion? Tree does this automatically.
        if os.path.isdir(filepath): return
        
        preview_container.clear()
        
        filename = os.path.basename(filepath)
        with preview_container:
            with ui.row().classes('w-full items-center justify-between mb-4'):
                ui.label(f"Preview: {filename}").classes('font-bold text-gray-600')
                # Add Download Button for the selected file
                # Use ui.download(url) which triggers browser download
                # We need to serve the file via a route or use the static path
                # Since we mapped /downloads, we can use that
                download_url = build_download_url(filepath)
                if download_url:
                    ui.button('Download File', icon='download', on_click=lambda _, url=download_url: ui.download(url)).props('outline')
                else:
                    ui.label("File outside download root").classes('text-xs text-red-400')

            ui.separator().classes('mb-4')
            
            if filepath.lower().endswith('.md'):
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                    content = rewrite_markdown_links(content, filepath)
                    ui.markdown(content).classes('w-full bg-white p-4 rounded shadow')
                except Exception as e:
                    ui.label(f"Error reading file: {e}").classes('text-red-500')
                    
            elif filepath.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
                try:
                    image_url = build_download_url(filepath)
                    if image_url:
                        ui.image(image_url).classes('max-w-full rounded shadow')
                    else:
                        ui.label("Image path outside downloads folder").classes('text-red-500')
                except Exception as e:
                     ui.label(f"Error loading image: {e}").classes('text-red-500')
            else:
                # Generic file preview or placeholder
                with ui.column().classes('w-full items-center justify-center p-8 bg-white rounded border border-gray-200'):
                    ui.icon('insert_drive_file', size='4em').classes('text-gray-400 mb-2')
                    ui.label(filename).classes('text-lg font-bold text-gray-600')
                    
                    try:
                        size_bytes = os.path.getsize(filepath)
                        # Convert to readable size
                        unit = 'B'
                        for unit in ['B', 'KB', 'MB', 'GB']:
                            if size_bytes < 1024:
                                break
                            size_bytes /= 1024
                        ui.label(f"Size: {size_bytes:.2f} {unit}").classes('text-sm text-gray-500')
                    except: pass
                    
                    # Also add a big download button here for non-previewable files
                    download_url = build_download_url(filepath)
                    if download_url:
                        ui.button('Download', icon='download', on_click=lambda _, url=download_url: ui.download(url)).classes('mt-4')

@ui.page('/login')
def login_page():
    if not auth_enabled():
        ui.navigate.to('/')
        return
    with ui.column().classes('w-full h-screen items-center justify-center'):
        with ui.card().classes('w-full max-w-sm p-6 gap-4'):
            ui.label('Web UI Login').classes('text-xl font-bold')
            password_input = ui.input(
                label='Password',
                password=True,
                password_toggle_button=True,
            ).classes('w-full')
            error_label = ui.label('').classes('text-red-500 text-sm')
            def do_login():
                entered = (password_input.value or '').strip()
                if hmac.compare_digest(entered, WEB_UI_PASSWORD):
                    ui.run_javascript(
                        f"document.cookie = '{AUTH_COOKIE_NAME}={AUTH_COOKIE_VALUE}; path=/; SameSite=Lax'; window.location.href='/';"
                    )
                    return
                error_label.set_text('密码错误')
            password_input.on('keydown.enter', lambda _: do_login())
            ui.button('Login', on_click=do_login).classes('w-full')

# Register static files for images
# Map '/downloads' to the local 'downloads' directory
app.add_static_files('/downloads', os.path.join(os.getcwd(), 'downloads'))

if __name__ in {"__main__", "__mp_main__"}:
    ui.run(title="Fanbox Extractor", port=8086, reload=False, storage_secret='fanbox_secret')
