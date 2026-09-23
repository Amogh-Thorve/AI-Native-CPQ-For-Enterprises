import React from "react";
import { cn } from "@/lib/utils";

interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
}

export function EmptyState({
  icon,
  title,
  description,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center p-12 text-center bg-white border border-slate-200/80 rounded-xl shadow-xs",
        className
      )}
    >
      {icon && (
        <div className="w-12 h-12 rounded-xl bg-slate-100 flex items-center justify-center text-slate-500 mb-3 border border-slate-200/60">
          {icon}
        </div>
      )}
      <h3 className="text-base font-semibold text-slate-800">{title}</h3>
      {description && (
        <p className="text-xs text-slate-500 max-w-sm mt-1 mb-4 leading-relaxed">
          {description}
        </p>
      )}
      {action && <div>{action}</div>}
    </div>
  );
}
