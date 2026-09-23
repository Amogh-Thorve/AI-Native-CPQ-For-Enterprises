import React from "react";
import { cn } from "@/lib/utils";

interface MetricCardProps {
  title: string;
  value: string | number;
  subtext?: string;
  icon?: React.ReactNode;
  trend?: {
    value: string;
    isPositive?: boolean;
  };
  className?: string;
}

export function MetricCard({
  title,
  value,
  subtext,
  icon,
  trend,
  className,
}: MetricCardProps) {
  return (
    <div
      className={cn(
        "bg-white border border-slate-200/80 rounded-xl p-5 shadow-xs hover:shadow-sm transition-all duration-200",
        className
      )}
    >
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
          {title}
        </span>
        {icon && (
          <div className="p-2 rounded-lg bg-slate-50 text-slate-600 border border-slate-100">
            {icon}
          </div>
        )}
      </div>

      <div className="flex items-baseline gap-2">
        <div className="text-2xl font-bold tracking-tight text-slate-900">{value}</div>
        {trend && (
          <span
            className={cn(
              "text-xs font-semibold px-1.5 py-0.5 rounded",
              trend.isPositive
                ? "bg-emerald-50 text-emerald-700"
                : "bg-rose-50 text-rose-700"
            )}
          >
            {trend.value}
          </span>
        )}
      </div>

      {subtext && <div className="text-xs text-slate-500 mt-2 font-medium">{subtext}</div>}
    </div>
  );
}
