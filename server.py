import os
import asyncio
import secrets
import threading
from typing import List, Optional, Dict
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from fanbox_extractor.downloader import FanboxDownloader
from fanbox_extractor.patreon_downloader import PatreonDownloader
from fanbox_extractor.web_ui_core import resolve_download_root, build_tree_nodes, build_download_url

app = FastAPI(title="Fanbox Extractor API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all for local dev, restrict in prod if needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global State
class AppState:
    downloader: Optional[FanboxDownloader | PatreonDownloader] = None
    running: bool = False
    progress: float = 0.0
    status_msg: str = ""
    logs: List[str] = []
    
state = AppState()
DOWNLOADS_ROOT = resolve_download_root(os.getcwd())

# WebSocket Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass

manager = ConnectionManager()

# Pydantic Models
class ConnectRequest(BaseModel):
    platform: str
    sessid: Optional[str] = None
    rss_url: Optional[str] = None
    creator_id: Optional[str] = None

class DownloadOptions(BaseModel):
    skip_existing: bool = True
    extract_archives: bool = True
    auto_extract_archives: bool = True
    parallel_downloads: int = 5
    creator_id: Optional[str] = None

class CreatorInfo(BaseModel):
    id: str
    title: str

# Helper Functions
async def notify_state():
    await manager.broadcast({
        "type": "state",
        "running": state.running,
        "progress": state.progress,
        "status": state.status_msg
    })

async def notify_log(msg: str):
    state.logs.append(msg)
    if len(state.logs) > 1000:
        state.logs = state.logs[-1000:]
    await manager.broadcast({
        "type": "log",
        "message": msg
    })

# API Routes
@app.get("/api/health")
async def health():
    return {"status": "ok"}

@app.post("/api/connect")
async def connect_platform(req: ConnectRequest):
    if state.running:
        raise HTTPException(status_code=400, detail="Download in progress")
    
    try:
        if req.platform == "fanbox":
            if not req.sessid:
                raise HTTPException(status_code=400, detail="Sessid required")
            state.downloader = FanboxDownloader(req.sessid)
            creators = state.downloader.fetch_supporting_creators()
            return {"success": True, "creators": [
                {"id": c.get("creatorId"), "title": c.get("title", "No Title")} 
                for c in creators if c.get("creatorId")
            ]}
            
        elif req.platform == "patreon":
            if not req.rss_url:
                raise HTTPException(status_code=400, detail="RSS URL required")
            cid = req.creator_id or "patreon"
            state.downloader = PatreonDownloader(rss_url=req.rss_url, creator_id=cid)
            return {"success": True, "creators": [{"id": cid, "title": "Patreon Creator"}]}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/download/start")
async def start_download(opts: DownloadOptions):
    if state.running:
        raise HTTPException(status_code=400, detail="Already running")
    if not state.downloader:
        raise HTTPException(status_code=400, detail="Not connected")
        
    if opts.creator_id:
        state.downloader.set_creator(opts.creator_id)
        
    state.running = True
    state.progress = 0
    state.status_msg = "Starting..."
    await notify_state()
    
    asyncio.create_task(run_download_task(opts))
    return {"status": "started"}

@app.post("/api/download/stop")
async def stop_download():
    if state.downloader:
        state.downloader.request_stop()
        await notify_log("Stop requested...")
    return {"status": "stopping"}

async def run_download_task(opts: DownloadOptions):
    loop = asyncio.get_running_loop()
    
    def progress_cb(val):
        state.progress = val
        asyncio.run_coroutine_threadsafe(notify_state(), loop)
        
    def status_cb(msg):
        state.status_msg = msg
        asyncio.run_coroutine_threadsafe(notify_log(msg), loop)
        asyncio.run_coroutine_threadsafe(notify_state(), loop)
        
    try:
        state.downloader.clear_stop()
        await asyncio.to_thread(
            state.downloader.run,
            progress_callback=progress_cb,
            status_callback=status_cb,
            max_workers=opts.parallel_downloads,
            skip_existing=opts.skip_existing,
            extract_archives=opts.extract_archives,
            auto_extract_archives=opts.auto_extract_archives
        )
        await notify_log("Download finished successfully.")
    except Exception as e:
        await notify_log(f"Download error: {str(e)}")
    finally:
        state.running = False
        await notify_state()

@app.get("/api/files")
async def list_files(path: str = ""):
    target_path = DOWNLOADS_ROOT
    if state.downloader and getattr(state.downloader, "base_dir", None):
        target_path = state.downloader.base_dir
        
    if not os.path.exists(target_path):
        return []
        
    return build_tree_nodes(target_path)

@app.get("/api/files/download")
async def download_file(path: str):
    # Security check: Ensure path is within DOWNLOADS_ROOT
    abs_root = os.path.abspath(DOWNLOADS_ROOT)
    abs_path = os.path.abspath(path)
    if not abs_path.startswith(abs_root):
        raise HTTPException(status_code=403, detail="Access denied")
    
    if not os.path.exists(abs_path) or not os.path.isfile(abs_path):
        raise HTTPException(status_code=404, detail="File not found")
        
    return FileResponse(abs_path)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # Send initial state
        await websocket.send_json({
            "type": "state", 
            "running": state.running,
            "progress": state.progress,
            "status": state.status_msg
        })
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
