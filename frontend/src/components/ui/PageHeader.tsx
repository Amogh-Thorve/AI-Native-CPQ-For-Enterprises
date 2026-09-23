import React from "react";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { cn } from "@/lib/utils";

interface PageHeaderProps {
  title: string;
  description?: string;
  backHref?: string;
  backLabel?: string;
  onBack?: () => void;
  actions?: React.ReactNode;
  className?: string;
  badge?: React.ReactNode;
}

export function PageHeader({
  title,
  description,
  backHref,
  backLabel = "Back",
  onBack,
  actions,
  className,
  badge,
}: PageHeaderProps) {
  return (
    <div className={cn("mb-6 flex flex-col gap-3", className)}>
      {(backHref || onBack) && (
        <div>
          {backHref ? (
            <Link
              href={backHref}
              className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-500 hover:text-slate-900 transition-colors"
            >
              <ArrowLeft size={14} />
              <span>{backLabel}</span>
            </Link>
          ) : (
            <button
              onClick={onBack}
              className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-500 hover:text-slate-900 transition-colors cursor-pointer"
            >
              <ArrowLeft size={14} />
              <span>{backLabel}</span>
            </button>
          )}
        </div>
      )}

      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">{title}</h1>
            {badge}
          </div>
          {description && (
            <p className="text-sm text-slate-500 mt-1 font-normal">{description}</p>
          )}
        </div>

        {actions && <div className="flex items-center gap-2.5 flex-wrap">{actions}</div>}
      </div>
    </div>
  );
}
