import React from "react";
import { cn } from "@/lib/utils";

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost" | "danger" | "success" | "outline";
  size?: "sm" | "md" | "lg";
  icon?: React.ReactNode;
  iconPosition?: "left" | "right";
  isLoading?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      children,
      className,
      variant = "primary",
      size = "md",
      icon,
      iconPosition = "left",
      isLoading = false,
      disabled,
      ...props
    },
    ref
  ) => {
    const sizeStyles = {
      sm: "px-3 py-1.5 text-xs font-medium rounded-lg gap-1.5",
      md: "px-4 py-2 text-sm font-medium rounded-lg gap-2",
      lg: "px-5 py-2.5 text-sm font-semibold rounded-lg gap-2.5",
    };

    const variantStyles = {
      primary:
        "bg-blue-600 hover:bg-blue-700 text-white shadow-xs focus:ring-2 focus:ring-blue-500/20 active:bg-blue-800 disabled:bg-blue-300",
      secondary:
        "bg-white hover:bg-slate-50 text-slate-700 border border-slate-200 shadow-xs focus:ring-2 focus:ring-slate-200 active:bg-slate-100 disabled:opacity-50",
      outline:
        "bg-transparent hover:bg-slate-100 text-slate-700 border border-slate-200 focus:ring-2 focus:ring-slate-200 disabled:opacity-50",
      ghost:
        "bg-transparent hover:bg-slate-100 text-slate-600 hover:text-slate-900 disabled:opacity-50",
      danger:
        "bg-rose-600 hover:bg-rose-700 text-white shadow-xs focus:ring-2 focus:ring-rose-500/20 active:bg-rose-800 disabled:bg-rose-300",
      success:
        "bg-emerald-600 hover:bg-emerald-700 text-white shadow-xs focus:ring-2 focus:ring-emerald-500/20 active:bg-emerald-800 disabled:bg-emerald-300",
    };

    return (
      <button
        ref={ref}
        disabled={disabled || isLoading}
        className={cn(
          "inline-flex items-center justify-center transition-all duration-150 cursor-pointer disabled:cursor-not-allowed select-none",
          sizeStyles[size],
          variantStyles[variant],
          className
        )}
        {...props}
      >
        {isLoading && (
          <span className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
        )}
        {!isLoading && icon && iconPosition === "left" && icon}
        {children}
        {!isLoading && icon && iconPosition === "right" && icon}
      </button>
    );
  }
);
Button.displayName = "Button";
