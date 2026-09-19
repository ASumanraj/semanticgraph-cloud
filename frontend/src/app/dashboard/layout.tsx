import React from 'react';
import Link from 'next/link';
import { 
  Folder, 
  Network, 
  Database, 
  Settings, 
  ChevronRight,
  Menu,
  Bell,
  Search,
  User,
  PanelLeftClose,
  PanelLeftOpen
} from 'lucide-react';

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex h-screen bg-[#0a0a0b] text-slate-200 font-sans selection:bg-indigo-500/30">
      {/* Sidebar */}
      <aside className="w-64 border-r border-white/5 bg-[#0a0a0b] flex flex-col transition-all duration-300">
        <div className="h-14 flex items-center px-4 border-b border-white/5 font-semibold text-white tracking-wide">
          <div className="w-6 h-6 rounded bg-indigo-500 mr-3 flex items-center justify-center text-xs text-white">
            SG
          </div>
          SemanticGraph
        </div>

        <nav className="flex-1 px-3 py-4 space-y-1">
          <Link href="/dashboard/projects" className="flex items-center px-3 py-2 text-sm font-medium rounded-md text-slate-300 hover:text-white hover:bg-white/5 group transition-colors">
            <Folder className="w-4 h-4 mr-3 text-slate-400 group-hover:text-indigo-400" />
            Projects
          </Link>
          <Link href="/dashboard/explorer" className="flex items-center px-3 py-2 text-sm font-medium rounded-md text-slate-300 hover:text-white hover:bg-white/5 group transition-colors">
            <Network className="w-4 h-4 mr-3 text-slate-400 group-hover:text-indigo-400" />
            Graph Explorer
          </Link>
          <Link href="/dashboard/connectors" className="flex items-center px-3 py-2 text-sm font-medium rounded-md text-slate-300 hover:text-white hover:bg-white/5 group transition-colors">
            <Database className="w-4 h-4 mr-3 text-slate-400 group-hover:text-indigo-400" />
            Data Connectors
          </Link>
        </nav>

        <div className="p-3 border-t border-white/5">
          <Link href="/dashboard/settings" className="flex items-center px-3 py-2 text-sm font-medium rounded-md text-slate-300 hover:text-white hover:bg-white/5 group transition-colors">
            <Settings className="w-4 h-4 mr-3 text-slate-400 group-hover:text-indigo-400" />
            Settings
          </Link>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top Navbar */}
        <header className="h-14 flex items-center justify-between px-6 border-b border-white/5 bg-[#0a0a0b]/80 backdrop-blur-md sticky top-0 z-10">
          <div className="flex items-center text-sm text-slate-400">
            <div className="flex items-center hover:text-slate-200 cursor-pointer transition-colors">
              <span className="font-medium text-slate-300">Acme Corp</span>
            </div>
            <ChevronRight className="w-4 h-4 mx-1" />
            <span className="text-slate-300">Dashboard</span>
          </div>

          <div className="flex items-center space-x-4">
            <button className="text-slate-400 hover:text-white transition-colors">
              <Search className="w-4 h-4" />
            </button>
            <button className="text-slate-400 hover:text-white transition-colors relative">
              <Bell className="w-4 h-4" />
              <span className="absolute top-0 right-0 w-1.5 h-1.5 bg-indigo-500 rounded-full"></span>
            </button>
            <div className="w-px h-4 bg-white/10 mx-2"></div>
            <button className="flex items-center space-x-2 text-sm text-slate-300 hover:text-white transition-colors">
              <div className="w-7 h-7 rounded-full bg-gradient-to-tr from-indigo-500 to-purple-500 flex items-center justify-center text-white font-medium">
                JS
              </div>
            </button>
          </div>
        </header>

        {/* Page Content */}
        <div className="flex-1 overflow-auto bg-[#0a0a0b]">
          {children}
        </div>
      </main>
    </div>
  );
}
