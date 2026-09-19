"use client";

import { Bell, Search, User } from "lucide-react";

export function Navbar() {
  return (
    <header className="flex h-16 shrink-0 items-center justify-between border-b border-gray-800 bg-[#0A0A0A] px-6 text-gray-300">
      <div className="flex flex-1 items-center gap-4">
        <div className="relative w-96">
          <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3">
            <Search size={16} className="text-gray-500" />
          </div>
          <input
            type="text"
            className="block w-full rounded-md border border-gray-800 bg-[#111] py-1.5 pl-10 pr-3 text-sm placeholder:text-gray-500 focus:border-gray-700 focus:outline-none focus:ring-1 focus:ring-gray-700 text-gray-200"
            placeholder="Search resources, queries, or chunks..."
          />
        </div>
      </div>
      
      <div className="flex items-center gap-4">
        <button className="relative rounded-full p-2 hover:bg-gray-800 transition-colors">
          <Bell size={20} className="text-gray-400" />
          <span className="absolute top-1.5 right-1.5 flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-indigo-500"></span>
          </span>
        </button>
        
        <div className="flex items-center gap-3 ml-2 pl-4 border-l border-gray-800">
          <div className="flex flex-col items-end">
            <span className="text-sm font-medium text-white">Alice Engineer</span>
            <span className="text-xs text-gray-500">Admin</span>
          </div>
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-indigo-600/20 text-indigo-400 border border-indigo-500/30">
            <User size={18} />
          </div>
        </div>
      </div>
    </header>
  );
}
