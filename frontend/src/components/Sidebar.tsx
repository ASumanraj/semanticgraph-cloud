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
      className={`flex flex-col border-r border-gray-800 bg-[#0A0A0A] text-gray-300 transition-all duration-300 ${
        collapsed ? "w-16" : "w-64"
      } h-screen shrink-0`}
    >
      <div className="flex h-14 items-center justify-between border-b border-gray-800 px-4">
        {!collapsed && (
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded bg-indigo-600 flex items-center justify-center text-xs font-bold text-white">
              SG
            </div>
            <span className="text-sm font-semibold text-white tracking-wide">SemanticGraph</span>
          </div>
        )}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="rounded p-1.5 hover:bg-gray-800 hover:text-white transition-colors"
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
              className={`group flex items-center rounded-md px-2.5 py-2 text-sm font-medium transition-colors ${
                isActive
                  ? "bg-indigo-600/20 text-indigo-400 border border-indigo-500/30"
                  : "text-gray-400 hover:bg-gray-800/50 hover:text-gray-100"
              }`}
              title={collapsed ? item.name : undefined}
            >
              <item.icon
                className={`flex-shrink-0 ${collapsed ? "mr-0" : "mr-3"} ${
                  isActive ? "text-indigo-400" : "text-gray-400 group-hover:text-gray-300"
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
