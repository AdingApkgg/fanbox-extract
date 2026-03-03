import os
import sys
import threading
import asyncio
from nicegui import ui, app
from fanbox_extractor.downloader import FanboxDownloader

# Global state
downloader_instance = None
creators_list = []
selected_creator_id = None
is_running = False

def init_downloader(sessid):
    global downloader_instance
    try:
        downloader_instance = FanboxDownloader(sessid)
        return True
    except Exception as e:
        ui.notify(f"Error initializing downloader: {e}", type='negative')
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
    
    # UI Elements
    with ui.card().classes('w-full max-w-2xl mx-auto p-4 gap-4'):
        ui.label('Fanbox Extractor').classes('text-2xl font-bold mb-4')
        
        # Connection Section
        with ui.row().classes('w-full items-center gap-2'):
            sessid_input = ui.input(label='FANBOXSESSID', password=True).classes('flex-grow')
            default_sessid = os.environ.get("FANBOXSESSID", "")
            if default_sessid:
                sessid_input.value = default_sessid
            connect_btn = ui.button('Connect', on_click=lambda: on_connect())
        
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

    def on_connect():
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
                
                # Show creator selection callback
                def on_creator_change(e):
                    if e.value:
                        downloader_instance.set_creator(e.value)
                        control_row.classes(remove='hidden')
                        advanced_options.classes(remove='hidden')
                        progress_bar.classes(remove='hidden')
                        status_label.classes(remove='hidden')
                        log_expansion.classes(remove='hidden')
                        
                creator_select.on_value_change(on_creator_change)
                
            else:
                ui.notify("Connected, but no supporting creators found.", type='warning')

    async def start_download():
        global is_running
        if is_running: return
        is_running = True
        start_btn.disable()
        stop_btn.enable()
        connect_btn.disable()
        creator_select.disable()
        
        progress_bar.value = 0
        log_area.clear()
        
        # Callbacks for nicegui updates (must use ui.run_javascript or similar context if updating from thread)
        # But here we use asyncio.to_thread, so we are in async context, updates should work
        
        def update_progress(val):
            progress_bar.value = val
            
        def update_status(msg):
            status_label.text = msg
            log_area.push(msg)
            
        try:
            # Pass options to downloader run method
            workers = int(parallel_downloads.value)
            await asyncio.to_thread(
                downloader_instance.run, 
                progress_callback=update_progress, 
                status_callback=update_status,
                max_workers=workers
            )
            ui.notify("Download Finished!", type='positive')
        except Exception as e:
            ui.notify(f"Download Error: {e}", type='negative')
            log_area.push(f"Error: {e}")
        finally:
            is_running = False
            start_btn.enable()
            stop_btn.disable()
            connect_btn.enable()
            creator_select.enable()

    def stop_download():
        # This is tricky with ThreadPoolExecutor without a stop flag in the downloader class
        # Ideally we should add a stop method to FanboxDownloader
        ui.notify("Stop not fully implemented yet (requires downloader update)", type='warning')


ui.run(title="Fanbox Extractor", port=8082, reload=False, storage_secret='fanbox_secret')
