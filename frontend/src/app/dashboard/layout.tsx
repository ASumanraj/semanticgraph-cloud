import React from 'react';
import { Sidebar } from '@/components/Sidebar';
import { ChevronRight } from 'lucide-react';

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex h-screen bg-page text-text font-sans selection:bg-teal/30">
      <Sidebar />

      {/* Main Content */}
      <main className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top Header */}
        <header className="h-14 flex items-center justify-between px-6 border-b border-border bg-page/80 backdrop-blur-md sticky top-0 z-10">
          <div className="flex items-center text-sm text-muted">
            <span className="font-medium text-text">SemanticGraph</span>
            <ChevronRight className="w-4 h-4 mx-1" />
            <span className="text-text">Console</span>
          </div>

          <div className="flex items-center space-x-4">
            <div className="text-xs px-2.5 py-1 rounded-lg bg-panel border border-border text-muted font-mono">
              Stage 1 Substrate
            </div>
          </div>
        </header>

        {/* Page Content */}
        <div className="flex-1 overflow-auto bg-page">
          {children}
        </div>
      </main>
    </div>
  );
}
