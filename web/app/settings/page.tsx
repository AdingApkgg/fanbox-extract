"use client";

import { useState } from "react";

export default function SettingsPage() {
  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-3xl font-bold tracking-tight">Settings</h1>
      
      <div className="grid gap-6 max-w-2xl">
        <div className="rounded-xl border bg-card p-6 space-y-6">
          <h2 className="text-lg font-semibold">Download Options</h2>
          
          <div className="space-y-4">
            <label className="flex items-center gap-3 cursor-pointer">
              <input type="checkbox" className="w-4 h-4 rounded border-input bg-background" defaultChecked />
              <span className="text-sm font-medium">Skip existing files</span>
            </label>
            
            <label className="flex items-center gap-3 cursor-pointer">
              <input type="checkbox" className="w-4 h-4 rounded border-input bg-background" defaultChecked />
              <span className="text-sm font-medium">Extract archives</span>
            </label>
            
            <label className="flex items-center gap-3 cursor-pointer">
              <input type="checkbox" className="w-4 h-4 rounded border-input bg-background" defaultChecked />
              <span className="text-sm font-medium">Auto extract to folder</span>
            </label>
          </div>
        </div>

        <div className="rounded-xl border bg-card p-6 space-y-6">
          <h2 className="text-lg font-semibold">Performance</h2>
          
          <div className="space-y-4">
            <div className="space-y-2">
              <div className="flex justify-between">
                <label className="text-sm font-medium">Parallel Downloads</label>
                <span className="text-sm text-muted-foreground">5</span>
              </div>
              <input type="range" min="1" max="10" defaultValue="5" className="w-full" />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
