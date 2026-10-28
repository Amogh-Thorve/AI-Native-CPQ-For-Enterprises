"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Users,
  BookOpen,
  DollarSign,
  Sliders,
  FileText,
  CheckSquare,
  ArrowRightLeft,
  Settings,
  HelpCircle,
  Bell,
  Search,
  LogOut,
  ChevronDown,
  Sparkles
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/hooks/useAuth";

interface NavLinkProps {
  href: string;
  label: string;
  icon: React.ReactNode;
  active: boolean;
}

function NavLink({ href, label, icon, active }: NavLinkProps) {
  return (
    <Link
      href={href}
      className={cn(
        "flex items-center gap-3 px-3 py-2.5 rounded-md text-sm transition-colors duration-150 select-none border-l-4",
        active
          ? "bg-canvas text-ink font-bold border-primary"
          : "text-slate-700 hover:text-ink hover:bg-canvas-tint border-transparent font-medium"
      )}
    >
      <span className={cn(active ? "text-ink" : "text-slate-500")}>{icon}</span>
      <span>{label}</span>
    </Link>
  );
}

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const [searchQuery, setSearchQuery] = useState("");
  const [isUserMenuOpen, setIsUserMenuOpen] = useState(false);

  const mainLinks = [
    { href: "/dashboard", label: "Dashboard", icon: <LayoutDashboard size={17} /> },
    { href: "/customers", label: "Customers", icon: <Users size={17} /> },
    { href: "/catalog", label: "Product Catalog", icon: <BookOpen size={17} /> },
    { href: "/configuration", label: "Product Config", icon: <Sliders size={17} /> },
    { href: "/pricing", label: "Pricing Engine", icon: <DollarSign size={17} /> },
    { href: "/quotes", label: "Quote Builder", icon: <FileText size={17} /> },
    { href: "/approvals", label: "Approvals", icon: <CheckSquare size={17} /> },
    { href: "/integrations", label: "Integrations", icon: <ArrowRightLeft size={17} /> },
  ];

  const bottomLinks = [
    { href: "/dashboard", label: "Settings", icon: <Settings size={17} /> },
    { href: "/dashboard", label: "Help & Support", icon: <HelpCircle size={17} /> },
  ];

  const roleLabels: Record<string, string> = {
    sales_rep: "Sales Representative",
    manager: "Sales Manager",
    executive: "Executive",
    admin: "Administrator",
  };

  const displayName = user?.full_name || "Aarav lunkad";
  const displayRole = user?.role ? roleLabels[user.role] || user.role : "Executive";
  const initials = displayName
    .split(" ")
    .map((n) => n[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);

  return (
    <div className="flex min-h-screen bg-canvas-warm text-ink font-sans antialiased">
      {/* ─── Top Bar ────────────────────────────────────────────── */}
      <header className={"h-[72px] fixed top-0 inset-x-0 bg-canvas border-b border-hairline flex items-center justify-between px-6 z-30"}>
        {/* Brand Logo */}
        <div className="flex items-center gap-2.5 w-60">
          <span className="font-extrabold text-xl text-brand-mark">CPQ Cognitive</span>
        </div>


        {/* Global Search */}
        <div className="flex-1 max-w-xl mx-4">
          <div className="relative flex items-center">
            <Search size={15} className="absolute left-3 text-slate-400 pointer-events-none" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search products, customers, or quotes..."
              className="w-full pl-9 pr-14 py-2.5 bg-canvas border border-field-border rounded-md text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:border-ink transition-colors"
            />
            <div className="absolute right-2.5 flex items-center gap-0.5 text-[10px] font-semibold text-slate-400 border border-hairline bg-canvas px-1.5 py-0.5 rounded pointer-events-none">
              <span>⌘</span>
              <span>K</span>
            </div>
          </div>
        </div>

        {/* Right Section: Notifications & User Profile */}
        <div className="flex items-center gap-3.5">
          {/* Notifications */}
          <button
            className="relative p-2 rounded-lg text-slate-500 hover:text-slate-800 hover:bg-slate-100 transition-colors cursor-pointer"
            title="Notifications"
          >
            <Bell size={17} />
            <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-brand-mark" />
          </button>

          {/* User Profile */}
          <div className="relative">
            <button
              onClick={() => setIsUserMenuOpen(!isUserMenuOpen)}
              className="flex items-center gap-2.5 p-1 rounded-lg hover:bg-slate-100 transition-colors cursor-pointer"
            >
              <div className="w-8 h-8 rounded-full bg-primary text-white flex items-center justify-center text-xs font-bold">
                {initials}
              </div>
              <div className="text-left hidden sm:block">
                <div className="text-xs font-bold text-slate-900 leading-tight">{displayName}</div>
                <div className="text-[10px] text-slate-500 font-medium capitalize">{displayRole}</div>
              </div>
              <ChevronDown size={14} className="text-slate-400" />
            </button>

            {/* User Dropdown */}
            {isUserMenuOpen && (
              <div className="absolute right-0 mt-2 w-48 bg-canvas border border-hairline rounded-xl py-1.5 z-40 text-xs">
                <div className="px-3 py-2 border-b border-slate-100">
                  <div className="font-semibold text-slate-800">{displayName}</div>
                  <div className="text-slate-400 text-[11px] truncate">{user?.email || "aarav@enterprise.com"}</div>
                </div>
                <button
                  onClick={() => {
                    setIsUserMenuOpen(false);
                    logout();
                  }}
                  className="w-full text-left px-3 py-2 text-rose-600 hover:bg-rose-50 flex items-center gap-2 font-medium cursor-pointer"
                >
                  <LogOut size={14} />
                  <span>Log Out</span>
                </button>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* ─── Left Sidebar ───────────────────────────────────────── */}
      <aside className="w-60 bg-canvas-soft border-r border-hairline flex flex-col fixed inset-y-0 left-0 top-[72px] z-20">
        {/* Navigation Links */}
        <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
          {mainLinks.map((link) => (
            <NavLink
              key={link.label}
              href={link.href}
              label={link.label}
              icon={link.icon}
              active={pathname.startsWith(link.href)}
            />
          ))}
        </nav>

        {/* Bottom System Links */}
        <div className="p-3 border-t border-hairline space-y-1">
          {bottomLinks.map((link) => (
            <NavLink
              key={link.label}
              href={link.href}
              label={link.label}
              icon={link.icon}
              active={false}
            />
          ))}

          {/* AI Copilot Badge */}
          <div className="pt-2">
            <div className="flex items-center gap-2.5 p-2 rounded-md bg-canvas border border-hairline text-ink">
              <Sparkles size={14} className="text-slate-600 shrink-0" />
              <div className="text-[11px] leading-tight">
                <span className="font-semibold">AI Copilot</span>
                <span className="block text-[10px] text-slate-500">Cognitive Pricing</span>
              </div>
            </div>
          </div>
        </div>
      </aside>

      {/* ─── Main Content Canvas ─────────────────────────────────── */}
      <div className="flex-1 pl-60 pt-[72px] flex flex-col min-h-screen">
        <main className="flex-1 p-8 max-w-7xl w-full mx-auto">{children}</main>
      </div>
    </div>
  );
}
