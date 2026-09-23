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
  ShieldCheck,
  Sparkles
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/hooks/useAuth";
import { useDemoTour } from "@/components/demo/DemoTourProvider";
import { Button } from "@/components/ui/Button";

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
        "flex items-center gap-3 px-3 py-2 rounded-lg text-xs font-medium transition-all duration-150 select-none",
        active
          ? "bg-blue-50 text-blue-600 font-semibold shadow-2xs"
          : "text-slate-600 hover:text-slate-900 hover:bg-slate-100/70"
      )}
    >
      <span className={cn(active ? "text-blue-600" : "text-slate-500")}>{icon}</span>
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
  const { isActive: isDemoActive, start: startDemo, stop: stopDemo } = useDemoTour();
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
    <div className="flex min-h-screen bg-slate-50 text-slate-900 font-sans antialiased">
      {/* ─── Top Bar ────────────────────────────────────────────── */}
      <header className={cn("h-14 fixed top-0 inset-x-0 bg-white border-b border-slate-200/80 flex items-center justify-between px-6", isDemoActive ? "z-[70]" : "z-30")}>
        {/* Brand Logo */}
        <div className="flex items-center gap-2.5 w-60">
          <div className="w-8 h-8 rounded-lg bg-teal-50 border border-teal-200/70 flex items-center justify-center text-teal-600 shadow-2xs">
            <ShieldCheck size={20} className="stroke-[2.2]" />
          </div>
          <span className="font-bold text-sm tracking-tight text-slate-900 uppercase">
            CPQ <span className="text-teal-600 font-extrabold">Cognitive</span>
          </span>
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
              className="w-full pl-9 pr-14 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-xs text-slate-800 placeholder-slate-400 focus:outline-none focus:bg-white focus:border-blue-500 focus:ring-2 focus:ring-blue-500/10 transition-all shadow-2xs"
            />
            <div className="absolute right-2.5 flex items-center gap-0.5 text-[10px] font-semibold text-slate-400 border border-slate-200 bg-white px-1.5 py-0.5 rounded shadow-2xs pointer-events-none">
              <span>⌘</span>
              <span>K</span>
            </div>
          </div>
        </div>

        {/* Right Section: Notifications & User Profile */}
        <div className="flex items-center gap-3.5">
          <Button
            variant={isDemoActive ? "secondary" : "outline"}
            size="sm"
            icon={<Sparkles size={14} className="text-teal-600" />}
            onClick={isDemoActive ? stopDemo : startDemo}
            className={cn(
              isDemoActive
                ? "border-teal-200 text-teal-800"
                : "border-teal-200 text-teal-800 hover:bg-teal-50"
            )}
          >
            {isDemoActive ? "Stop demo" : "Demo Mode"}
          </Button>
          {/* Notifications */}
          <button
            className="relative p-2 rounded-lg text-slate-500 hover:text-slate-800 hover:bg-slate-100 transition-colors cursor-pointer"
            title="Notifications"
          >
            <Bell size={17} />
            <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-blue-600 ring-2 ring-white" />
          </button>

          {/* User Profile */}
          <div className="relative">
            <button
              onClick={() => setIsUserMenuOpen(!isUserMenuOpen)}
              className="flex items-center gap-2.5 p-1 rounded-lg hover:bg-slate-100 transition-colors cursor-pointer"
            >
              <div className="w-8 h-8 rounded-full bg-slate-800 text-white flex items-center justify-center text-xs font-bold tracking-wider shadow-2xs">
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
              <div className="absolute right-0 mt-2 w-48 bg-white border border-slate-200 rounded-xl shadow-lg py-1.5 z-40 text-xs">
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
      <aside className="w-60 bg-white border-r border-slate-200/80 flex flex-col fixed inset-y-0 left-0 top-14 z-20">
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
        <div className="p-3 border-t border-slate-100 space-y-1">
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
            <div className="flex items-center gap-2.5 p-2 rounded-lg bg-teal-50/60 border border-teal-100 text-teal-800">
              <Sparkles size={14} className="text-teal-600 shrink-0" />
              <div className="text-[11px] leading-tight">
                <span className="font-semibold">AI Copilot</span>
                <span className="block text-[10px] text-teal-600">Cognitive Pricing</span>
              </div>
            </div>
          </div>
        </div>
      </aside>

      {/* ─── Main Content Canvas ─────────────────────────────────── */}
      <div className="flex-1 pl-60 pt-14 flex flex-col min-h-screen">
        <main data-demo="app-main" className="flex-1 p-8 max-w-7xl w-full mx-auto">{children}</main>
      </div>
    </div>
  );
}
