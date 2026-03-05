from nicegui import ui, app
from fanbox_extractor.web_ui_v2 import setup

setup()

if __name__ in {"__main__", "__mp_main__"}:
    ui.run(title="Fanbox Extractor", port=8086, reload=False, storage_secret="fanbox_secret")
