"use client";

import { useState, useEffect } from "react";
import { api, FileNode } from "@/lib/api";
import { Folder, File, Download, Loader2, Home, ChevronRight, ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useToast } from "@/components/ui/use-toast";

export default function FilesPage() {
  const [files, setFiles] = useState<FileNode[]>([]);
  const [loading, setLoading] = useState(false);
  const [currentPath, setCurrentPath] = useState("");
  const { toast } = useToast();

  const loadFiles = async (path: string = "") => {
    setLoading(true);
    try {
      const data = await api.getFiles(path);
      // Ensure data is an array
      if (Array.isArray(data)) {
        setFiles(data);
        setCurrentPath(path);
      } else {
        console.error("Invalid file data:", data);
        setFiles([]);
        toast({
          title: "Error loading files",
          description: "Received invalid data format from server.",
          variant: "destructive",
        });
      }
    } catch (e: any) {
      console.error(e);
      setFiles([]);
      toast({
        title: "Error loading files",
        description: e.message || "Failed to fetch files.",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadFiles();
  }, []);

  const handleNavigate = (path: string) => {
      loadFiles(path);
  };
  
  const handleUp = () => {
      if (!currentPath) return;
      const parts = currentPath.split('/');
      parts.pop();
      const parent = parts.join('/');
      loadFiles(parent);
  };

  const handleDownload = (id: string) => {
    // Navigate if folder
    const file = files.find(f => f.id === id);
    if (file && file.children) {
        // Construct new path
        const newPath = currentPath ? `${currentPath}/${id}` : id;
        loadFiles(newPath);
    } else {
        // It's a file, download it (mock for now)
        toast({
            title: "Download",
            description: "File download functionality coming soon.",
        });
    }
  };

  const pathSegments = currentPath ? currentPath.split('/') : [];

  return (
    <div className="flex flex-col gap-6 h-full max-w-5xl mx-auto w-full">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
            <h1 className="text-3xl font-bold tracking-tight">Files</h1>
        </div>
        <Button 
          variant="outline"
          size="icon"
          onClick={() => loadFiles(currentPath)}
          disabled={loading}
        >
          <Loader2 className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </Button>
      </div>

      <Card className="flex-1 overflow-hidden flex flex-col bg-card/50">
        <div className="p-4 border-b bg-muted/30 flex items-center gap-2 text-sm overflow-x-auto whitespace-nowrap">
          <Button 
            variant="ghost" 
            size="icon" 
            className="h-6 w-6" 
            onClick={() => loadFiles("")}
            disabled={!currentPath}
          >
            <Home className="w-4 h-4" />
          </Button>
          
          {currentPath && (
             <Button 
                variant="ghost" 
                size="icon" 
                className="h-6 w-6 mr-2" 
                onClick={handleUp}
             >
                <ArrowLeft className="w-4 h-4" />
             </Button>
          )}

          <div className="flex items-center gap-1 text-muted-foreground">
            <span className="text-muted-foreground/50">/</span>
            <span>downloads</span>
            {pathSegments.map((segment, i) => {
                const path = pathSegments.slice(0, i + 1).join('/');
                return (
                    <div key={path} className="flex items-center gap-1">
                        <ChevronRight className="w-3 h-3 text-muted-foreground/50" />
                        <button 
                            onClick={() => loadFiles(path)}
                            className="hover:text-foreground hover:underline underline-offset-4 transition-colors"
                        >
                            {segment}
                        </button>
                    </div>
                );
            })}
          </div>
        </div>
        
        <ScrollArea className="flex-1">
          <div className="p-2">
            {files.length === 0 && !loading && (
              <div className="flex flex-col items-center justify-center h-64 text-muted-foreground gap-2">
                <Folder className="w-12 h-12 opacity-20" />
                <p>{currentPath ? "Empty folder" : "No files found"}</p>
              </div>
            )}
            
            <div className="grid gap-1">
              {files.map((node) => (
                <div 
                  key={node.id}
                  onClick={() => node.children ? handleDownload(node.id) : null}
                  className={`flex items-center justify-between p-3 rounded-lg transition-all border border-transparent ${node.children ? 'cursor-pointer hover:bg-accent hover:border-border' : 'hover:bg-accent/50'}`}
                >
                  <div className="flex items-center gap-3 overflow-hidden">
                    {node.children ? (
                      <div className="p-2 bg-blue-500/10 rounded-md">
                        <Folder className="w-5 h-5 text-blue-500 shrink-0" />
                      </div>
                    ) : (
                      <div className="p-2 bg-slate-500/10 rounded-md">
                        <File className="w-5 h-5 text-slate-500 shrink-0" />
                      </div>
                    )}
                    <span className="truncate text-sm font-medium">{node.label}</span>
                  </div>
                  
                  {!node.children && (
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={(e) => {
                          e.stopPropagation();
                          handleDownload(node.id);
                      }}
                      className="opacity-0 group-hover:opacity-100 transition-opacity"
                      title="Download"
                    >
                      <Download className="w-4 h-4 text-muted-foreground" />
                    </Button>
                  )}
                </div>
              ))}
            </div>
          </div>
        </ScrollArea>
      </Card>
    </div>
  );
}
