import { Hono } from 'hono'
import { cors } from 'hono/cors'
import { config } from 'dotenv'
import { runPythonModule, runPythonBridge, checkPythonVersion } from './python-bridge.ts'
import { resolve, join } from 'path'
import { WebSocketServer, WebSocket } from 'ws'
import { createServer } from 'http'
import { serve } from '@hono/node-server'

// Load .env from project root
config({ path: resolve(import.meta.dir, '../../.env') })

const app = new Hono()

// Global state for download process
let downloadProcess: any = null;
let activeClients: Set<WebSocket> = new Set();

// Setup WebSocket Server
const server = createServer()
const wss = new WebSocketServer({ server })

wss.on('connection', (ws) => {
    console.log('Client connected')
    activeClients.add(ws)
    
    ws.on('close', () => {
        activeClients.delete(ws)
    })
})

// Function to broadcast messages to all connected clients
function broadcast(message: any) {
    const data = JSON.stringify(message)
    for (const client of activeClients) {
        if (client.readyState === WebSocket.OPEN) {
            client.send(data)
        }
    }
}

app.use('/*', cors())

app.get('/', (c) => c.text('Fanbox Extract Bun Backend is Running!'))

app.get('/api/health', async (c) => {
    try {
        const pythonVersion = await checkPythonVersion()
        return c.json({
            status: 'ok',
            backend: 'bun',
            python: pythonVersion,
            env_loaded: !!process.env.FANBOXSESSID,
            downloading: !!downloadProcess
        })
    } catch (e: any) {
        return c.json({ status: 'error', message: e.message }, 500)
    }
})

app.get('/api/test-bridge', async (c) => {
    try {
        const result = await runPythonBridge('test', { message: 'Hello from Bun' })
        return c.json(result)
    } catch (e: any) {
        return c.json({ success: false, error: e.message }, 500)
    }
})

app.post('/api/connect', async (c) => {
    try {
        const body = await c.req.json()
        const sessid = body.sessid || process.env.FANBOXSESSID
        
        if (!sessid) {
            return c.json({ success: false, error: "No FANBOXSESSID provided" }, 400)
        }
        
        const result = await runPythonBridge('list_creators', { sessid })
        
        if (result.error) {
            return c.json({ success: false, error: result.error }, 400)
        }
        return c.json(result)
    } catch (e: any) {
        return c.json({ success: false, error: e.message }, 500)
    }
})

// Start Download
app.post('/api/download/start', async (c) => {
    if (downloadProcess) {
        return c.json({ success: false, error: "Download already in progress" }, 400)
    }

    try {
        const body = await c.req.json()
        const sessid = body.sessid || process.env.FANBOXSESSID
        const creatorId = body.creatorId
        const platform = body.platform || 'fanbox'

        if (!sessid) return c.json({ success: false, error: "Missing sessid" }, 400)
        if (!creatorId) return c.json({ success: false, error: "Missing creatorId" }, 400)

        // Validate via bridge first
        const validation = await runPythonBridge('start_download', { sessid, creator_id: creatorId })
        if (validation.error) {
             return c.json({ success: false, error: validation.error }, 400)
        }

        // Spawn Python process for actual downloading
        const PROJECT_ROOT = resolve(import.meta.dir, '../../');
        
        // Construct arguments for main.py
        // Usage: python3 main.py [sessid] [creator_id]
        // But main.py expects env vars or args. 
        // Let's spawn main.py directly
        
        console.log(`Starting download for ${creatorId}...`)
        
        // Using Bun.spawn to keep a handle on the process
        downloadProcess = Bun.spawn(["python3", "-u", "main.py", sessid, creatorId], {
            cwd: PROJECT_ROOT,
            env: { 
                ...process.env, 
                PYTHONPATH: PROJECT_ROOT, 
                PYTHONUNBUFFERED: '1',
                FANBOXSESSID: sessid
            },
            stdout: "pipe",
            stderr: "pipe",
        });

        // Stream stdout
        (async () => {
            const reader = downloadProcess.stdout.getReader();
            const decoder = new TextDecoder();
            try {
                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;
                    const text = decoder.decode(value);
                    console.log(`[DL]: ${text}`);
                    broadcast({ type: 'log', message: text });
                }
            } catch (e) {
                console.error("Stream error", e);
            } finally {
                downloadProcess = null;
                broadcast({ type: 'status', status: 'stopped' });
            }
        })();

        // Stream stderr
         (async () => {
            const reader = downloadProcess.stderr.getReader();
            const decoder = new TextDecoder();
            try {
                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;
                    const text = decoder.decode(value);
                    console.error(`[DL ERR]: ${text}`);
                    broadcast({ type: 'log', message: text, level: 'error' });
                }
            } catch (e) {
                console.error("Stream error", e);
            }
        })();

        return c.json({ success: true, message: "Download started" })
    } catch (e: any) {
        return c.json({ success: false, error: e.message }, 500)
    }
})

// Stop Download
app.post('/api/download/stop', async (c) => {
    if (!downloadProcess) {
        return c.json({ success: false, message: "No download in progress" })
    }

    try {
        downloadProcess.kill();
        downloadProcess = null;
        broadcast({ type: 'status', status: 'stopped', message: 'Download stopped by user' });
        return c.json({ success: true, message: "Download stopped" })
    } catch (e: any) {
        return c.json({ success: false, error: e.message }, 500)
    }
})

// Get Files
app.get('/api/files', async (c) => {
    const path = c.req.query('path') || ''
    try {
        const result = await runPythonBridge('get_files', { path })
        if (result.error) {
             return c.json({ success: false, error: result.error }, 403) // 403 for access denied usually
        }
        return c.json(result.files)
    } catch (e: any) {
        return c.json({ success: false, error: e.message }, 500)
    }
})

const port = 3001
console.log(`Server is running on http://localhost:${port}`)

// Hono + WebSocket (Node/Bun Adapter)
// For Bun, we can just export the object. But we need to combine HTTP and WS.
// However, @hono/node-server with 'ws' is a bit tricky.
// The easiest way for Bun is to use Bun.serve which supports both.

export default {
    port,
    fetch(req: Request, server: any) {
        // Upgrade to WebSocket if requested
        if (server.upgrade(req)) {
            return;
        }
        return app.fetch(req, server);
    },
    websocket: {
        open(ws: any) {
            console.log('Client connected (Bun WS)');
            activeClients.add(ws);
        },
        message(ws: any, message: any) {
            // Handle incoming messages if needed
        },
        close(ws: any) {
            console.log('Client disconnected (Bun WS)');
            activeClients.delete(ws);
        },
    }
}
