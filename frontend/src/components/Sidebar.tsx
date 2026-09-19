"use client";

import { useState } from "react";
import { LayoutDashboard, Users, Settings, Database, Network, ChevronLeft, ChevronRight } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const navigation = [
  { name: "Dashboard", href: "/", icon: LayoutDashboard },
  { name: "Knowledge Graph", href: "/graph", icon: Network },
  { name: "Data Sources", href: "/sources", icon: Database },
  { name: "Team", href: "/team", icon: Users },
  { name: "Settings", href: "/settings", icon: Settings },
];

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);
  const pathname = usePathname();

  return (
    <aside
      className={`flex flex-col border-r border-gray-800 bg-[#0A0A0A] text-gray-300 transition-all duration-300 ${
        collapsed ? "w-16" : "w-64"
      } h-screen`}
    >
      <div className="flex h-16 items-center justify-between border-b border-gray-800 px-4">
        {!collapsed && <span className="text-lg font-semibold text-white tracking-wide">SemanticGraph</span>}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="rounded p-1.5 hover:bg-gray-800 hover:text-white transition-colors"
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
                  ? "bg-gray-800 text-white"
                  : "text-gray-400 hover:bg-gray-800/50 hover:text-gray-100"
              }`}
              title={collapsed ? item.name : undefined}
            >
              <item.icon
                className={`flex-shrink-0 ${collapsed ? "mr-0" : "mr-3"} ${
                  isActive ? "text-white" : "text-gray-400 group-hover:text-gray-300"
                }`}
                size={20}
              />
              {!collapsed && <span>{item.name}</span>}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
