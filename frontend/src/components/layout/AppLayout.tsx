import React from 'react';
import { LayoutDashboard, Settings, User } from 'lucide-react';

export function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen w-full overflow-hidden bg-bg-primary text-text-primary selection:bg-brand-500/30">
      <div className="absolute top-0 -left-1/4 w-1/2 h-1/2 bg-brand-900/20 rounded-full blur-[120px] pointer-events-none" />
      <div className="absolute bottom-0 -right-1/4 w-1/2 h-1/2 bg-brand-800/10 rounded-full blur-[120px] pointer-events-none" />

      <aside className="relative z-10 w-64 flex-shrink-0 glass border-r border-border-subtle flex-col hidden md:flex">
        <div className="h-16 flex items-center px-6 border-b border-border-subtle">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-brand-400 to-brand-600 flex items-center justify-center shadow-[0_0_15px_rgba(139,92,246,0.5)]">
              <span className="font-bold text-white tracking-tighter">SG</span>
            </div>
            <span className="font-semibold text-lg tracking-wide text-gradient">SemanticGraph</span>
          </div>
        </div>
        <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
          <NavItem icon={<LayoutDashboard size={18} />} label="Dashboard" active />
          <NavItem icon={<Settings size={18} />} label="Settings" />
          <NavItem icon={<User size={18} />} label="Profile" />
        </nav>
      </aside>

      <div className="flex-1 flex flex-col min-w-0 relative z-10">
        <header className="h-16 glass border-b border-border-subtle flex items-center justify-between px-6 sticky top-0 z-20">
          <h2 className="text-sm font-medium text-text-secondary">Overview</h2>
          <div className="flex items-center gap-4">
            <div className="w-8 h-8 rounded-full bg-bg-secondary border border-border-subtle flex items-center justify-center">
              <User size={16} className="text-text-secondary" />
            </div>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto p-6 lg:p-8">
          <div className="mx-auto max-w-6xl">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}

function NavItem({ icon, label, active = false }: { icon: React.ReactNode, label: string, active?: boolean }) {
  return (
    <button className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-200 ${active ? 'bg-brand-500/10 text-brand-300 border border-brand-500/20 shadow-[0_0_10px_rgba(139,92,246,0.1)]' : 'text-text-secondary hover:text-text-primary hover:bg-bg-secondary'}`}>
      {icon}
      <span className="font-medium text-sm">{label}</span>
    </button>
  );
}
