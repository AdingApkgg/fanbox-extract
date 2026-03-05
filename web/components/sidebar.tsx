"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, Folder, Settings, Terminal, Download } from "lucide-react";
import { cn } from "@/lib/utils";
import { useSocket } from "@/lib/socket";

const items = [
  { label: "Dashboard", icon: LayoutDashboard, href: "/" },
  { label: "Files", icon: Folder, href: "/files" },
  { label: "Logs", icon: Terminal, href: "/logs" },
  { label: "Settings", icon: Settings, href: "/settings" },
];

export function Sidebar() {
  const pathname = usePathname();
  const { connected } = useSocket();

  return (
    <div className="w-64 h-full border-r bg-card border-border flex flex-col p-4 shrink-0">
      <div className="flex items-center gap-2 px-2 mb-8">
        <Download className="w-8 h-8 text-primary" />
        <span className="text-xl font-bold">Fanbox DL</span>
      </div>

      <nav className="flex flex-col gap-2">
        {items.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={cn(
              "flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-colors hover:bg-accent hover:text-accent-foreground",
              pathname === item.href ? "bg-primary text-primary-foreground hover:bg-primary/90" : "text-muted-foreground"
            )}
          >
            <item.icon className="w-5 h-5" />
            {item.label}
          </Link>
        ))}
      </nav>

      <div className="mt-auto p-4 bg-muted/20 rounded-lg border border-border">
        <div className="text-xs font-bold text-muted-foreground uppercase mb-2">Status</div>
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${connected ? 'bg-green-500' : 'bg-red-500'}`} />
          <span className="text-sm text-muted-foreground">{connected ? 'Connected' : 'Disconnected'}</span>
        </div>
      </div>
    </div>
  );
}
