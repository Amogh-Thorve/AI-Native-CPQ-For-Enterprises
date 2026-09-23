import React from "react";
import { cn } from "@/lib/utils";

interface DataTableProps extends React.HTMLAttributes<HTMLTableElement> {
  children: React.ReactNode;
  className?: string;
}

export function DataTable({ children, className, ...props }: DataTableProps) {
  return (
    <div className="w-full overflow-x-auto border border-slate-200/80 rounded-xl bg-white shadow-xs">
      <table className={cn("w-full text-left border-collapse text-xs", className)} {...props}>
        {children}
      </table>
    </div>
  );
}

export function TableHead({
  children,
  className,
  ...props
}: React.HTMLAttributes<HTMLTableSectionElement>) {
  return (
    <thead
      className={cn("bg-slate-50/80 border-b border-slate-200 text-slate-500 font-semibold uppercase tracking-wider text-[11px]", className)}
      {...props}
    >
      {children}
    </thead>
  );
}

export function TableRow({
  children,
  className,
  ...props
}: React.HTMLAttributes<HTMLTableRowElement>) {
  return (
    <tr
      className={cn(
        "border-b border-slate-100 hover:bg-slate-50/70 transition-colors duration-150 last:border-b-0",
        className
      )}
      {...props}
    >
      {children}
    </tr>
  );
}

export function TableHeader({
  children,
  className,
  ...props
}: React.ThHTMLAttributes<HTMLTableCellElement>) {
  return (
    <th className={cn("px-4 py-3 font-semibold text-slate-600", className)} {...props}>
      {children}
    </th>
  );
}

export function TableCell({
  children,
  className,
  ...props
}: React.TdHTMLAttributes<HTMLTableCellElement>) {
  return (
    <td className={cn("px-4 py-3 text-slate-800 align-middle", className)} {...props}>
      {children}
    </td>
  );
}
