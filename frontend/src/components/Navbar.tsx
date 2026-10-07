"use client";

import { Bell, Search, User } from "lucide-react";

export function Navbar() {
  return (
    <header className="flex h-16 shrink-0 items-center justify-between border-b border-border bg-panel px-6 text-muted">
      <div className="flex flex-1 items-center gap-4">
        <div className="relative w-96">
          <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3">
            <Search size={16} className="text-muted" />
          </div>
          <input
            type="text"
            className="block w-full rounded-lg border border-border bg-page py-1.5 pl-10 pr-3 text-sm placeholder:text-muted focus:border-teal focus:outline-none focus:ring-1 focus:ring-teal/30 text-text"
            placeholder="Search resources, queries, or chunks..."
          />
        </div>
      </div>
      
      <div className="flex items-center gap-4">
        <button className="relative rounded-full p-2 hover:bg-page transition-colors" aria-label="Notifications">
          <Bell size={20} className="text-muted" />
          <span className="absolute top-1.5 right-1.5 flex h-2 w-2">
            <span className="inline-flex rounded-full h-2 w-2 bg-teal"></span>
          </span>
        </button>
        
        <div className="flex items-center gap-3 ml-2 pl-4 border-l border-border">
          <div className="flex flex-col items-end">
            <span className="text-sm font-medium text-text">Alice Engineer</span>
            <span className="text-xs text-muted">Admin</span>
          </div>
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-teal/20 text-teal border border-teal/30">
            <User size={18} />
          </div>
        </div>
      </div>
    </header>
  );
}
