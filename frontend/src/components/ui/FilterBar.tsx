import React from "react";
import { Search, X } from "lucide-react";
import { cn } from "@/lib/utils";

interface SearchBarProps extends React.InputHTMLAttributes<HTMLInputElement> {
  value: string;
  onChangeValue: (val: string) => void;
  placeholder?: string;
  className?: string;
  shortcut?: string;
}

export function SearchBar({
  value,
  onChangeValue,
  placeholder = "Search...",
  className,
  shortcut,
  ...props
}: SearchBarProps) {
  return (
    <div className={cn("relative flex items-center", className)}>
      <Search size={15} className="absolute left-3 text-slate-400 pointer-events-none" />
      <input
        type="text"
        value={value}
        onChange={(e) => onChangeValue(e.target.value)}
        placeholder={placeholder}
        className="w-full pl-9 pr-9 py-2 bg-white border border-slate-200 rounded-lg text-xs text-slate-800 placeholder-slate-400 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/10 transition-all shadow-xs"
        {...props}
      />
      {value ? (
        <button
          onClick={() => onChangeValue("")}
          className="absolute right-2.5 p-0.5 text-slate-400 hover:text-slate-600 rounded-full hover:bg-slate-100 transition-colors"
          type="button"
        >
          <X size={13} />
        </button>
      ) : shortcut ? (
        <span className="absolute right-2.5 text-[10px] font-medium text-slate-400 border border-slate-200 bg-slate-50 px-1.5 py-0.5 rounded pointer-events-none">
          {shortcut}
        </span>
      ) : null}
    </div>
  );
}

interface FilterSelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  className?: string;
}

export function FilterSelect({ label, children, className, ...props }: FilterSelectProps) {
  return (
    <div className="flex items-center gap-1.5">
      {label && <span className="text-xs text-slate-500 font-medium">{label}:</span>}
      <select
        className={cn(
          "bg-white border border-slate-200 text-slate-700 text-xs rounded-lg px-2.5 py-2 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/10 shadow-xs transition-all cursor-pointer",
          className
        )}
        {...props}
      >
        {children}
      </select>
    </div>
  );
}

interface FilterBarProps {
  children: React.ReactNode;
  className?: string;
}

export function FilterBar({ children, className }: FilterBarProps) {
  return (
    <div
      className={cn(
        "bg-white border border-slate-200/80 p-3 rounded-xl shadow-xs flex flex-col sm:flex-row items-center justify-between gap-3 mb-4",
        className
      )}
    >
      {children}
    </div>
  );
}
