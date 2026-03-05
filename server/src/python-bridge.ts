import { resolve, join } from 'path';

// Bun specific: import.meta.dir is the directory of the current module
const PROJECT_ROOT = resolve(import.meta.dir, '../../');

export async function runPythonScript(scriptName: string, args: string[] = []) {
    const scriptPath = join(PROJECT_ROOT, scriptName);
    
    try {
        const proc = Bun.spawn(["python3", scriptPath, ...args], {
            cwd: PROJECT_ROOT,
            env: { ...process.env, PYTHONPATH: PROJECT_ROOT, PYTHONUNBUFFERED: '1' },
            stdout: "pipe",
            stderr: "pipe",
        });
        
        const stdout = await new Response(proc.stdout).text();
        const stderr = await new Response(proc.stderr).text();
        const exitCode = await proc.exited;

        return { stdout, stderr, success: exitCode === 0 };
    } catch (e: any) {
        return { stdout: "", stderr: e.message, success: false };
    }
}

export async function runPythonModule(moduleName: string, args: string[] = []) {
    try {
        const proc = Bun.spawn(["python3", "-m", moduleName, ...args], {
            cwd: PROJECT_ROOT,
            env: { ...process.env, PYTHONPATH: PROJECT_ROOT, PYTHONUNBUFFERED: '1' },
            stdout: "pipe",
            stderr: "pipe",
        });

        const stdout = await new Response(proc.stdout).text();
        const stderr = await new Response(proc.stderr).text();
        const exitCode = await proc.exited;

        return { stdout, stderr, success: exitCode === 0 };
    } catch (e: any) {
        return { stdout: "", stderr: e.message, success: false };
    }
}

export async function runPythonBridge(command: string, payload: any) {
    try {
        const payloadStr = JSON.stringify(payload);
        const { stdout, stderr, success } = await runPythonModule('fanbox_extractor.bridge', [command, payloadStr]);
        
        if (!success) {
            throw new Error(`Python error: ${stderr}`);
        }
        
        try {
            return JSON.parse(stdout);
        } catch (e) {
            throw new Error(`Invalid JSON from Python: ${stdout}`);
        }
    } catch (e: any) {
        throw new Error(`Bridge failed: ${e.message}`);
    }
}

export async function checkPythonVersion() {
    try {
        const proc = Bun.spawn(["python3", "--version"], { stdout: "pipe" });
        const text = await new Response(proc.stdout).text();
        return text.trim();
    } catch (e) {
        throw new Error("Python 3 not found");
    }
}
