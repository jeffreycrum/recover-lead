import { NavLink } from "react-router-dom";
import {
  BarChart3,
  FileSignature,
  Home,
  Mail,
  Map,
  Search,
  Settings,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { useState } from "react";
import { cn } from "@/lib/utils";

const navItems = [
  { to: "/", icon: Home, label: "Dashboard" },
  { to: "/leads", icon: Search, label: "Browse Leads" },
  { to: "/my-leads", icon: BarChart3, label: "My Leads" },
  { to: "/letters", icon: Mail, label: "Letters" },
  { to: "/contracts", icon: FileSignature, label: "Contracts" },
  { to: "/counties", icon: Map, label: "Counties" },
  { to: "/settings", icon: Settings, label: "Settings" },
];

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <aside
      className={cn(
        "flex flex-col border-r border-[var(--lt-line)] bg-[linear-gradient(180deg,var(--lt-surface)_0%,var(--lt-bg-2)_100%)] text-[var(--lt-text)] transition-all duration-200",
        collapsed ? "w-16" : "w-60"
      )}
    >
      <div className="flex items-center justify-between border-b border-[var(--lt-line)] p-4">
        {!collapsed && (
          <div className="flex items-center gap-3">
            <div className="relative grid h-9 w-9 place-items-center rounded-xl bg-[linear-gradient(135deg,var(--lt-emerald)_0%,#0ea572_100%)] shadow-[0_4px_14px_rgba(16,185,129,0.35),inset_0_1px_0_rgba(255,255,255,0.2)]">
              <div className="h-2.5 w-2.5 rounded-full bg-[#052e1f]" />
              <span className="absolute right-1.5 top-1.5 h-1.5 w-1.5 rounded-full bg-[var(--lt-emerald)] shadow-[0_0_10px_var(--lt-emerald)] animate-[lt-pulse_2s_ease-in-out_infinite]" />
            </div>
            <div className="min-w-0">
              <span className="block text-base font-bold tracking-[-0.01em]">
                Recover<span className="text-[var(--lt-emerald)]">Lead</span>
              </span>
              <span className="mono text-[10px] uppercase tracking-[0.18em] text-[var(--lt-text-dim)]">
                Live Workspace
              </span>
            </div>
          </div>
        )}
        <button
          onClick={() => setCollapsed(!collapsed)}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          aria-expanded={!collapsed}
          aria-controls="app-sidebar-nav"
          className="rounded-full border border-transparent p-1.5 text-[var(--lt-text-muted)] transition-colors hover:border-[var(--lt-line)] hover:bg-[var(--lt-surface-2)] hover:text-[var(--lt-text)]"
        >
          {collapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
        </button>
      </div>

      <nav id="app-sidebar-nav" className="flex-1 px-2 py-4">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/"}
            aria-label={collapsed ? item.label : undefined}
            title={collapsed ? item.label : undefined}
            className={({ isActive }) =>
              cn(
                "mx-1.5 flex items-center gap-3 rounded-full border border-transparent py-2.5 text-sm font-medium transition-all",
                collapsed ? "justify-center px-0" : "px-4",
                isActive
                  ? "bg-[var(--lt-surface-2)] text-[var(--lt-text)] shadow-[inset_0_0_0_1px_var(--lt-line-2)]"
                  : "text-[var(--lt-text-muted)] hover:border-[var(--lt-line)] hover:bg-[rgba(255,255,255,0.02)] hover:text-[var(--lt-text)]"
              )
            }
          >
            <item.icon size={18} />
            <span className={collapsed ? "sr-only" : undefined}>{item.label}</span>
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
