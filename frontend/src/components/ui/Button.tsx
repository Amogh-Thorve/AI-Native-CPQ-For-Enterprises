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
      sm: "px-3 py-1.5 text-xs font-medium rounded-xs gap-1.5",
      md: "px-4 py-2.5 text-sm font-medium rounded-xs gap-2",
      lg: "px-4 py-3 text-sm font-medium rounded-xs gap-2.5",
    };

    // One charcoal action colour; secondary is an outlined companion. No coloured CTAs.
    const variantStyles = {
      primary:
        "bg-primary hover:bg-slate-700 active:bg-slate-700 text-white disabled:bg-canvas-soft disabled:text-slate-400 disabled:border disabled:border-hairline",
      secondary:
        "bg-transparent hover:bg-ink/8 text-ink border border-ink disabled:bg-canvas-soft disabled:text-slate-400 disabled:border-hairline",
      outline:
        "bg-transparent hover:bg-ink/8 text-ink border border-ink disabled:bg-canvas-soft disabled:text-slate-400 disabled:border-hairline",
      ghost:
        "bg-ink/0 hover:bg-ink/8 text-ink disabled:text-slate-400",
      danger:
        "bg-transparent hover:bg-rose-50 text-rose-600 border border-rose-600 disabled:bg-canvas-soft disabled:text-slate-400 disabled:border-hairline",
      success:
        "bg-primary hover:bg-slate-700 active:bg-slate-700 text-white disabled:bg-canvas-soft disabled:text-slate-400 disabled:border disabled:border-hairline",
    };

    return (
      <button
        ref={ref}
        disabled={disabled || isLoading}
        className={cn(
          "inline-flex items-center justify-center transition-colors duration-150 cursor-pointer disabled:cursor-not-allowed select-none",
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
