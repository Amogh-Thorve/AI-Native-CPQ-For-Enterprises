import React from "react";
import { cn } from "@/lib/utils";
import { CheckCircle2, Clock, XCircle, AlertCircle, Check, Circle } from "lucide-react";

export type BadgeVariant =
  | "ACTIVE"
  | "DRAFT"
  | "SUBMITTED"
  | "PENDING"
  | "APPROVED"
  | "REJECTED"
  | "EXPIRED"
  | "CANCELLED"
  | "ARCHIVED"
  | "INACTIVE"
  | "CONFIGURED"
  | "STANDARD"
  | "CONNECTED"
  | "DISCONNECTED"
  | "INFO"
  | "WARNING";

interface StatusBadgeProps {
  status: string;
  variant?: BadgeVariant;
  className?: string;
  showDot?: boolean;
}

export function StatusBadge({ status, variant, className, showDot = true }: StatusBadgeProps) {
  const norm = (variant || status || "").toUpperCase().trim();

  let style = "bg-slate-100 text-slate-700 border-slate-200";
  let icon: React.ReactNode = null;

  switch (norm) {
    case "ACTIVE":
    case "APPROVED":
    case "CONNECTED":
      style = "bg-emerald-50 text-emerald-700 border-emerald-200/80";
      icon = <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 mr-1.5" />;
      break;

    case "CONFIGURED":
      style = "bg-emerald-50 text-emerald-700 border-emerald-200/80";
      icon = <Check size={12} className="text-emerald-600 mr-1 stroke-[2.5]" />;
      break;

    case "STANDARD":
      style = "bg-slate-50 text-slate-600 border-slate-200";
      icon = <span className="w-1.5 h-1.5 rounded-full bg-slate-400 mr-1.5" />;
      break;

    case "DRAFT":
      style = "bg-slate-100 text-slate-700 border-slate-200";
      icon = <span className="w-1.5 h-1.5 rounded-full bg-slate-400 mr-1.5" />;
      break;

    case "PENDING":
    case "SUBMITTED":
      style = "bg-blue-50 text-blue-700 border-blue-200/80";
      icon = <span className="w-1.5 h-1.5 rounded-full bg-blue-500 mr-1.5 animate-pulse" />;
      break;

    case "WARNING":
    case "EXPIRED":
      style = "bg-amber-50 text-amber-700 border-amber-200/80";
      icon = <span className="w-1.5 h-1.5 rounded-full bg-amber-500 mr-1.5" />;
      break;

    case "REJECTED":
    case "CANCELLED":
    case "DISCONNECTED":
      style = "bg-rose-50 text-rose-700 border-rose-200/80";
      icon = <span className="w-1.5 h-1.5 rounded-full bg-rose-500 mr-1.5" />;
      break;

    case "ARCHIVED":
    case "INACTIVE":
      style = "bg-slate-100 text-slate-500 border-slate-200";
      icon = <span className="w-1.5 h-1.5 rounded-full bg-slate-400 mr-1.5" />;
      break;

    default:
      style = "bg-slate-100 text-slate-700 border-slate-200";
      icon = <span className="w-1.5 h-1.5 rounded-full bg-slate-400 mr-1.5" />;
  }

  return (
    <span
      className={cn(
        "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border tracking-wide",
        style,
        className
      )}
    >
      {showDot && icon}
      {status}
    </span>
  );
}
