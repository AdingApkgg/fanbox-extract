// Simple API client

export interface Creator {
  id: string;
  title: string;
}

export interface ConnectResponse {
  success: boolean;
  creators: Creator[];
}

export interface FileNode {
  id: string;
  label: string;
  icon?: string;
  children?: FileNode[];
}

export const api = {
  async connect(platform: "fanbox" | "patreon", data: any): Promise<ConnectResponse> {
    const res = await fetch("/api/connect", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ platform, ...data }),
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async startDownload(options: any) {
    const res = await fetch("/api/download/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(options),
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async stopDownload() {
    const res = await fetch("/api/download/stop", {
      method: "POST",
    });
    return res.json();
  },

  async getFiles(path = ""): Promise<FileNode[]> {
    const res = await fetch(`/api/files?path=${encodeURIComponent(path)}`);
    return res.json();
  },
};
