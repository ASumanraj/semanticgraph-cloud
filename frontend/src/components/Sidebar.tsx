"use client";

import { useState } from "react";
import { LayoutDashboard, Network, GitFork, ShieldCheck, Settings, ChevronLeft, ChevronRight } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const navigation = [
  { name: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { name: "Graph Explorer", href: "/dashboard/explorer", icon: Network },
  { name: "Ontology", href: "/dashboard/ontology", icon: GitFork },
  { name: "Evaluations", href: "/dashboard/evaluations", icon: ShieldCheck },
  { name: "Settings", href: "/dashboard/settings", icon: Settings },
];

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);
  const pathname = usePathname();

  return (
    <aside
      className={`flex flex-col border-r border-border bg-panel text-muted transition-all duration-300 ${
        collapsed ? "w-16" : "w-64"
      } h-screen shrink-0`}
    >
      <div className="flex h-14 items-center justify-between border-b border-border px-4">
        {!collapsed && (
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded bg-teal flex items-center justify-center text-xs font-bold text-page">
              SG
            </div>
            <span className="text-sm font-semibold text-text tracking-wide">SemanticGraph</span>
          </div>
        )}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="rounded p-1.5 hover:bg-page hover:text-text transition-colors"
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
        </button>
      </div>

      <nav className="flex-1 space-y-1 p-3">
        {navigation.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.name}
              href={item.href}
              className={`group flex items-center rounded-lg px-2.5 py-2 text-sm font-medium transition-colors ${
                isActive
                  ? "bg-teal/15 text-teal border border-teal/30"
                  : "text-muted hover:bg-page hover:text-text"
              }`}
              title={collapsed ? item.name : undefined}
            >
              <item.icon
                className={`flex-shrink-0 ${collapsed ? "mr-0" : "mr-3"} ${
                  isActive ? "text-teal" : "text-muted group-hover:text-text"
                }`}
                size={18}
              />
              {!collapsed && <span>{item.name}</span>}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
