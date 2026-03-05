"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { useSocket } from "@/lib/socket";
import { Play, Square } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Select } from "@/components/ui/select-native";
import { useToast } from "@/components/ui/use-toast";

export default function Dashboard() {
  const { state, connected } = useSocket();
  const [sessid, setSessid] = useState("");
  const [rss, setRss] = useState("");
  const [creators, setCreators] = useState<any[]>([]);
  const [selectedCreator, setSelectedCreator] = useState("");
  const [platform, setPlatform] = useState<"fanbox" | "patreon">("fanbox");
  const { toast } = useToast();

  const connect = async (platformName: "fanbox" | "patreon") => {
    try {
      setPlatform(platformName);
      const payload = platformName === "fanbox" ? { sessid } : { rss_url: rss };
      const res = await api.connect(platformName, payload);
      if (res.creators && res.creators.length > 0) {
        setCreators(res.creators);
        setSelectedCreator(res.creators[0].id);
        toast({
          title: "Connected",
          description: `Found ${res.creators.length} creators.`,
        });
      } else {
        toast({
          title: "Connected",
          description: "No creators found or invalid response.",
          variant: "destructive",
        });
      }
    } catch (e: any) {
      toast({
        title: "Connection Failed",
        description: e.message,
        variant: "destructive",
      });
    }
  };

  const handleStart = async () => {
    try {
      await api.startDownload({
        creatorId: selectedCreator,
        sessid: sessid, 
        platform: platform, 
        parallel_downloads: 5,
      });
      toast({
        title: "Download Started",
        description: `Downloading content for creator ${selectedCreator}`,
      });
    } catch (e: any) {
      toast({
        title: "Error",
        description: e.message,
        variant: "destructive",
      });
    }
  };

  const handleStop = async () => {
    await api.stopDownload();
    toast({
      title: "Download Stopped",
      description: "The download process has been stopped.",
    });
  };

  return (
    <div className="flex flex-col gap-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
          <p className="text-muted-foreground">Manage your Fanbox and Patreon downloads.</p>
        </div>
        <div className={`flex items-center gap-2 px-3 py-1 rounded-full text-xs font-medium border ${connected ? 'bg-green-500/10 text-green-500 border-green-500/20' : 'bg-red-500/10 text-red-500 border-red-500/20'}`}>
          <div className={`w-2 h-2 rounded-full ${connected ? 'bg-green-500' : 'bg-red-500'}`} />
          {connected ? 'System Online' : 'System Offline'}
        </div>
      </div>
      
      {state.running && (
        <Card className="border-blue-500/20 bg-blue-500/5">
          <CardHeader className="pb-2">
            <div className="flex justify-between items-center">
                <CardTitle className="text-blue-500">Active Task</CardTitle>
                <span className="font-mono text-sm">{Math.round(state.progress * 100)}%</span>
            </div>
            <CardDescription className="text-blue-400/80">{state.status || "Running..."}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Progress value={state.progress * 100} className="h-2" />
            <Button onClick={handleStop} variant="destructive" className="w-full">
              <Square className="w-4 h-4 mr-2" /> Stop Download
            </Button>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Fanbox</CardTitle>
            <CardDescription>Connect using your session ID</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
                <label className="text-sm font-medium">FANBOXSESSID</label>
                <Input 
                    type="password" 
                    value={sessid} 
                    onChange={(e) => setSessid(e.target.value)} 
                    disabled={state.running}
                    placeholder="Your session cookie"
                />
            </div>
            <Button onClick={() => connect("fanbox")} className="w-full" disabled={state.running}>
              Connect Fanbox
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Patreon</CardTitle>
            <CardDescription>Connect using RSS feed URL</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
                <label className="text-sm font-medium">RSS URL</label>
                <Input 
                    value={rss} 
                    onChange={(e) => setRss(e.target.value)} 
                    disabled={state.running}
                    placeholder="https://www.patreon.com/rss/..."
                />
            </div>
            <Button onClick={() => connect("patreon")} variant="secondary" className="w-full" disabled={state.running}>
              Connect Patreon
            </Button>
          </CardContent>
        </Card>
      </div>

      {creators.length > 0 && (
        <Card className="border-green-500/20">
          <CardHeader>
            <CardTitle>Download Control</CardTitle>
            <CardDescription>Select content to download</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Select Creator</label>
              <Select 
                value={selectedCreator}
                onChange={(e) => setSelectedCreator(e.target.value)}
                disabled={state.running}
              >
                {creators.map(c => (
                  <option key={c.id} value={c.id} className="bg-background">
                    {c.title} ({c.id})
                  </option>
                ))}
              </Select>
            </div>
            
            <Button 
              onClick={handleStart} 
              className="w-full bg-green-600 hover:bg-green-700"
              disabled={state.running}
            >
              <Play className="w-4 h-4 mr-2" /> Start Download
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
