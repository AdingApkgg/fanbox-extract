import os
import asyncio
import hmac
import secrets
from dataclasses import dataclass
from typing import Callable, Any
from dotenv import load_dotenv
from nicegui import ui, app
from starlette.requests import Request
from starlette.responses import RedirectResponse
from fanbox_extractor.downloader import FanboxDownloader
from fanbox_extractor.patreon_downloader import PatreonDownloader
from fanbox_extractor.web_ui_core import (
    auth_enabled as core_auth_enabled,
    requires_auth as core_requires_auth,
    is_authenticated as core_is_authenticated,
    resolve_download_root,
    build_download_url,
    rewrite_markdown_links,
    format_size,
    build_tree_nodes,
)

load_dotenv()
WEB_UI_PASSWORD = os.environ.get("WEB_UI_PASSWORD", "").strip()
AUTH_COOKIE_NAME = "fanbox_ui_auth"
AUTH_COOKIE_VALUE = secrets.token_urlsafe(32)
DOWNLOADS_ROOT = resolve_download_root(os.getcwd())
_initialized = False


@dataclass
class AppState:
    downloader: Any = None
    running: bool = False
    current_view: str = "dashboard"  # dashboard, files, settings, logs


class Theme:
    bg = "#0f172a"  # slate-900
    sidebar = "#1e293b"  # slate-800
    content = "#0f172a"  # slate-900
    card = "#1e293b"  # slate-800
    text = "#f8fafc"  # slate-50
    text_muted = "#94a3b8"  # slate-400
    primary = "#3b82f6"  # blue-500
    primary_hover = "#2563eb"  # blue-600
    danger = "#ef4444"  # red-500
    success = "#22c55e"  # green-500
    border = "#334155"  # slate-700


def auth_enabled():
    return core_auth_enabled(WEB_UI_PASSWORD)


def is_authenticated(request: Request):
    if not auth_enabled():
        return True
    return core_is_authenticated(request.cookies, AUTH_COOKIE_NAME, AUTH_COOKIE_VALUE)


def requires_auth(path: str):
    return core_requires_auth(path)


def setup():
    global _initialized
    if _initialized:
        return
    _initialized = True

    # Add custom styles for the dashboard layout
    ui.add_head_html(
        f"""
        <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
        <style>
            :root {{
                --q-primary: {Theme.primary};
                --q-dark: {Theme.bg};
            }}
            body {{
                background-color: {Theme.bg};
                color: {Theme.text};
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            }}
            .sidebar-item {{
                color: {Theme.text_muted};
                border-radius: 0.5rem;
                transition: all 0.2s;
            }}
            .sidebar-item:hover, .sidebar-item.active {{
                background-color: {Theme.primary};
                color: white;
            }}
            .dashboard-card {{
                background-color: {Theme.card};
                border: 1px solid {Theme.border};
                border-radius: 1rem;
            }}
            .custom-input .q-field__control {{
                background-color: {Theme.bg} !important;
                border: 1px solid {Theme.border};
                border-radius: 0.5rem;
            }}
            .custom-input .q-field__native {{
                color: {Theme.text};
            }}
            /* Scrollbar styling */
            ::-webkit-scrollbar {{
                width: 8px;
                height: 8px;
            }}
            ::-webkit-scrollbar-track {{
                background: {Theme.bg};
            }}
            ::-webkit-scrollbar-thumb {{
                background: {Theme.border};
                border-radius: 4px;
            }}
            ::-webkit-scrollbar-thumb:hover {{
                background: {Theme.text_muted};
            }}
        </style>
        """,
        shared=True,
    )

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

    @ui.page("/")
    def main_page():
        state = AppState()
        refs = {}  # References to UI elements for updates

        # --- Logic Helpers ---

        def set_view(view_name):
            state.current_view = view_name
            # Update sidebar active state
            for name, btn in refs.get("sidebar_btns", {}).items():
                if name == view_name:
                    btn.classes("active")
                else:
                    btn.classes(remove="active")
            
            # Show/Hide content areas
            for name, container in refs.get("views", {}).items():
                if name == view_name:
                    container.set_visibility(True)
                else:
                    container.set_visibility(False)
            
            # Refresh specific views if needed
            if view_name == "files":
                refresh_file_tree()

        async def connect_platform(platform_name):
            if state.running:
                ui.notify("Cannot connect while download is running", type="warning")
                return

            try:
                if platform_name == "fanbox":
                    sessid = refs["fanbox_sessid"].value.strip()
                    if not sessid:
                        ui.notify("Please enter FANBOXSESSID", type="warning")
                        return
                    state.downloader = FanboxDownloader(sessid)
                    
                    # Fetch creators immediately
                    creators = state.downloader.fetch_supporting_creators()
                    options = {c.get("creatorId"): f"{c.get('title', 'No Title')}" for c in creators if c.get("creatorId")}
                    refs["fanbox_creator_select"].options = options
                    refs["fanbox_creator_select"].update()
                    if options:
                        ui.notify(f"Connected! Found {len(options)} creators.", type="positive")
                        refs["fanbox_creator_section"].set_visibility(True)
                    else:
                        ui.notify("Connected, but no creators found.", type="warning")

                elif platform_name == "patreon":
                    rss = refs["patreon_rss"].value.strip()
                    cid = refs["patreon_id"].value.strip() or "patreon"
                    if not rss:
                        ui.notify("Please enter RSS URL", type="warning")
                        return
                    state.downloader = PatreonDownloader(rss_url=rss, creator_id=cid)
                    ui.notify("Patreon RSS Connected!", type="positive")
                    # Auto-select creator for patreon since it's 1-to-1 usually
                    refs["current_status"].text = f"Connected: Patreon ({cid})"
                    
            except Exception as e:
                ui.notify(f"Connection failed: {str(e)}", type="negative")

        def select_creator(creator_id):
            if not state.downloader:
                return
            state.downloader.set_creator(creator_id)
            refs["current_status"].text = f"Connected: Fanbox ({creator_id})"
            ui.notify(f"Selected creator: {creator_id}", type="positive")

        async def toggle_download():
            if state.running:
                # Stop
                if state.downloader:
                    state.downloader.request_stop()
                    ui.notify("Stopping download...", type="warning")
                return

            # Start
            if not state.downloader:
                ui.notify("Not connected to any platform", type="warning")
                return
            
            state.running = True
            update_ui_state()
            
            # Reset progress
            refs["progress_bar"].value = 0
            refs["progress_label"].text = "Starting..."
            refs["log_container"].clear()

            loop = asyncio.get_running_loop()

            def progress_cb(val):
                loop.call_soon_threadsafe(lambda: setattr(refs["progress_bar"], "value", val))

            def status_cb(msg):
                def _update():
                    refs["progress_label"].text = msg
                    refs["log_container"].push(msg)
                loop.call_soon_threadsafe(_update)

            try:
                state.downloader.clear_stop()
                # Get options
                skip = refs["opt_skip"].value
                extract = refs["opt_extract"].value
                auto_extract = refs["opt_auto_extract"].value
                parallel = int(refs["opt_parallel"].value)

                await asyncio.to_thread(
                    state.downloader.run,
                    progress_callback=progress_cb,
                    status_callback=status_cb,
                    max_workers=parallel,
                    skip_existing=skip,
                    extract_archives=extract,
                    auto_extract_archives=auto_extract
                )
                ui.notify("Download completed!", type="positive")
                refresh_file_tree()
            except Exception as e:
                ui.notify(f"Error: {str(e)}", type="negative")
                refs["log_container"].push(f"CRITICAL ERROR: {str(e)}")
            finally:
                state.running = False
                update_ui_state()

        def update_ui_state():
            # Toggle buttons based on running state
            if state.running:
                refs["start_btn"].set_visibility(False)
                refs["stop_btn"].set_visibility(True)
                refs["spinner"].set_visibility(True)
            else:
                refs["start_btn"].set_visibility(True)
                refs["stop_btn"].set_visibility(False)
                refs["spinner"].set_visibility(False)

        # --- File Management Helpers ---
        
        def get_current_path():
            if state.downloader and getattr(state.downloader, "base_dir", None):
                return state.downloader.base_dir
            return DOWNLOADS_ROOT

        def refresh_file_tree():
            path = get_current_path()
            if not os.path.exists(path):
                refs["file_tree"].clear()
                with refs["file_tree"]:
                    ui.label("No downloads found yet.").classes("text-slate-500 italic")
                return
            
            nodes = build_tree_nodes(path)
            refs["file_tree"].clear()
            with refs["file_tree"]:
                ui.tree(nodes, label_key="label", on_select=on_file_select).classes("text-slate-200")

        def on_file_select(e):
            filepath = e.value
            if not filepath or os.path.isdir(filepath):
                return
            
            # Preview
            refs["preview_area"].clear()
            filename = os.path.basename(filepath)
            safe_url = build_download_url(filepath, DOWNLOADS_ROOT)
            
            with refs["preview_area"]:
                with ui.row().classes("w-full items-center justify-between mb-4"):
                    ui.label(filename).classes("text-lg font-bold text-slate-200")
                    if safe_url:
                        ui.button("Download", icon="download", on_click=lambda: ui.download(safe_url)).props("flat color=primary")
                
                if not safe_url:
                    ui.label("File outside download root").classes("text-red-400")
                    return

                if filepath.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
                    ui.image(safe_url).classes("max-w-full rounded-lg border border-slate-700")
                elif filepath.lower().endswith('.md'):
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            content = f.read()
                        # Rewrite links
                        content = rewrite_markdown_links(content, filepath, DOWNLOADS_ROOT)
                        ui.markdown(content).classes("prose prose-invert max-w-none")
                    except:
                        ui.label("Error reading markdown").classes("text-red-400")
                else:
                    ui.icon("description", size="64px").classes("text-slate-600 mb-4")
                    try:
                        size = format_size(os.path.getsize(filepath))
                        ui.label(f"Size: {size}").classes("text-slate-400")
                    except: pass

        # --- UI Layout ---

        with ui.row().classes("w-full h-screen gap-0"):
            # Sidebar
            with ui.column().classes(f"w-64 h-full p-4 flex flex-col gap-2 border-r border-slate-800").style(f"background-color: {Theme.sidebar}"):
                # Header
                with ui.row().classes("items-center gap-3 px-2 mb-6"):
                    ui.icon("downloading", size="32px").classes("text-blue-500")
                    ui.label("Fanbox DL").classes("text-xl font-bold text-slate-100")
                
                # Navigation
                refs["sidebar_btns"] = {}
                nav_items = [
                    ("dashboard", "Dashboard", "dashboard"),
                    ("files", "Files", "folder"),
                    ("settings", "Settings", "settings"),
                    ("logs", "Logs", "terminal"),
                ]
                
                for key, label, icon in nav_items:
                    with ui.row().classes("sidebar-item w-full px-4 py-3 cursor-pointer items-center gap-3") as btn:
                        ui.icon(icon, size="20px")
                        ui.label(label).classes("font-medium")
                        btn.on("click", lambda k=key: set_view(k))
                        refs["sidebar_btns"][key] = btn
                
                ui.space()
                
                # Status Footer
                with ui.column().classes("w-full p-3 bg-slate-900/50 rounded-lg border border-slate-700/50"):
                    ui.label("Status").classes("text-xs text-slate-500 font-bold uppercase")
                    refs["current_status"] = ui.label("Not Connected").classes("text-sm text-slate-300 truncate w-full")
                    refs["spinner"] = ui.spinner(size="20px").classes("text-blue-500 mt-2").set_visibility(False)

            # Main Content
            with ui.column().classes("flex-1 h-full relative overflow-hidden"):
                refs["views"] = {}

                # --- VIEW: DASHBOARD ---
                with ui.column().classes("w-full h-full p-8 overflow-y-auto gap-6") as dash_view:
                    refs["views"]["dashboard"] = dash_view
                    ui.label("Dashboard").classes("text-2xl font-bold text-white mb-2")
                    
                    # Connection Cards
                    with ui.row().classes("w-full gap-6"):
                        # Fanbox Card
                        with ui.column().classes("dashboard-card flex-1 p-6 gap-4"):
                            with ui.row().classes("items-center gap-2"):
                                ui.icon("account_circle", size="24px").classes("text-yellow-400")
                                ui.label("Pixiv Fanbox").classes("text-lg font-bold")
                            
                            refs["fanbox_sessid"] = ui.input(label="FANBOXSESSID", password=True).classes("w-full custom-input").props("outlined dense dark")
                            if os.environ.get("FANBOXSESSID"):
                                refs["fanbox_sessid"].value = os.environ.get("FANBOXSESSID")
                                
                            ui.button("Connect Fanbox", icon="link", on_click=lambda: connect_platform("fanbox")).props("no-caps color=primary w-full")
                            
                            with ui.column().classes("w-full pt-2") as fb_creator_sect:
                                fb_creator_sect.set_visibility(False)
                                refs["fanbox_creator_section"] = fb_creator_sect
                                refs["fanbox_creator_select"] = ui.select(options={}, label="Select Creator", on_change=lambda e: select_creator(e.value)).classes("w-full custom-input").props("outlined dense dark")

                        # Patreon Card
                        with ui.column().classes("dashboard-card flex-1 p-6 gap-4"):
                            with ui.row().classes("items-center gap-2"):
                                ui.icon("monetization_on", size="24px").classes("text-red-400")
                                ui.label("Patreon").classes("text-lg font-bold")
                            
                            refs["patreon_rss"] = ui.input(label="RSS URL").classes("w-full custom-input").props("outlined dense dark")
                            refs["patreon_id"] = ui.input(label="Creator ID (Optional)").classes("w-full custom-input").props("outlined dense dark")
                            
                            if os.environ.get("PATREON_RSS_URL"):
                                refs["patreon_rss"].value = os.environ.get("PATREON_RSS_URL")
                            
                            ui.button("Connect Patreon", icon="rss_feed", on_click=lambda: connect_platform("patreon")).props("no-caps color=deep-orange w-full")

                    # Quick Actions & Progress
                    with ui.column().classes("dashboard-card w-full p-6 mt-4"):
                        ui.label("Active Task").classes("text-lg font-bold mb-4")
                        
                        with ui.row().classes("w-full items-center gap-4 mb-4"):
                            refs["start_btn"] = ui.button("Start Download", icon="play_arrow", on_click=toggle_download).props("color=positive no-caps")
                            refs["stop_btn"] = ui.button("Stop Download", icon="stop", on_click=toggle_download).props("color=negative no-caps").set_visibility(False)
                            refs["progress_label"] = ui.label("Ready").classes("text-slate-400")
                        
                        refs["progress_bar"] = ui.linear_progress(value=0, show_value=False).props("color=primary track-color=grey-8 rounded")

                # --- VIEW: FILES ---
                with ui.row().classes("w-full h-full hidden") as files_view:
                    refs["views"]["files"] = files_view
                    # Left Tree
                    with ui.column().classes(f"w-1/3 h-full border-r border-slate-800 p-4 overflow-y-auto"):
                        with ui.row().classes("w-full items-center justify-between mb-4"):
                            ui.label("Downloads").classes("text-xl font-bold")
                            ui.button(icon="refresh", on_click=refresh_file_tree).props("flat round dense color=primary")
                        refs["file_tree"] = ui.column().classes("w-full")
                    
                    # Right Preview
                    with ui.column().classes("w-2/3 h-full p-6 overflow-y-auto bg-slate-900/50"):
                        refs["preview_area"] = ui.column().classes("w-full")
                        with refs["preview_area"]:
                            ui.label("Select a file to preview").classes("text-slate-500 italic text-lg")

                # --- VIEW: SETTINGS ---
                with ui.column().classes("w-full h-full p-8 hidden") as settings_view:
                    refs["views"]["settings"] = settings_view
                    ui.label("Settings").classes("text-2xl font-bold mb-6")
                    
                    with ui.column().classes("dashboard-card w-full max-w-2xl p-6 gap-4"):
                        ui.label("Download Options").classes("text-lg font-semibold text-blue-400")
                        
                        refs["opt_skip"] = ui.checkbox("Skip existing files", value=True).props("dark")
                        refs["opt_extract"] = ui.checkbox("Extract links from archives", value=True).props("dark")
                        refs["opt_auto_extract"] = ui.checkbox("Auto-extract downloaded archives", value=True).props("dark")
                        
                        ui.separator().classes("bg-slate-700")
                        
                        ui.label("Performance").classes("text-lg font-semibold text-blue-400")
                        with ui.row().classes("items-center gap-4"):
                            ui.label("Parallel Downloads:")
                            refs["opt_parallel"] = ui.slider(min=1, max=10, value=5, step=1).props("label-always dark").classes("w-64")

                # --- VIEW: LOGS ---
                with ui.column().classes("w-full h-full p-4 hidden") as logs_view:
                    refs["views"]["logs"] = logs_view
                    ui.label("System Logs").classes("text-xl font-bold mb-4 px-2")
                    refs["log_container"] = ui.log().classes("w-full h-full bg-slate-950 rounded-lg p-4 font-mono text-xs border border-slate-800")

        # Initialize
        set_view("dashboard")

    @ui.page("/login")
    def login_page():
        if not auth_enabled():
            ui.navigate.to("/")
            return
        
        with ui.column().classes("w-full h-screen items-center justify-center").style(f"background-color: {Theme.bg}"):
            with ui.card().classes("w-full max-w-sm p-8 items-center gap-6").style(f"background-color: {Theme.card}; border: 1px solid {Theme.border}"):
                ui.icon("lock", size="48px").classes("text-blue-500")
                ui.label("Access Required").classes("text-xl font-bold text-white")
                
                pwd = ui.input(label="Password", password=True).classes("w-full custom-input").props("outlined dark")
                err = ui.label().classes("text-red-400 text-sm")
                
                def try_login():
                    if hmac.compare_digest(pwd.value.strip(), WEB_UI_PASSWORD):
                        ui.run_javascript(f"document.cookie = '{AUTH_COOKIE_NAME}={AUTH_COOKIE_VALUE}; path=/; SameSite=Lax'; window.location.href='/'")
                    else:
                        err.text = "Invalid password"
                        
                pwd.on("keydown.enter", try_login)
                ui.button("Login", on_click=try_login).props("color=primary w-full no-caps")

    app.add_static_files("/downloads", DOWNLOADS_ROOT)

