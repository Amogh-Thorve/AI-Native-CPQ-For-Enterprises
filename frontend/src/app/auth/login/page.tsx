"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import Link from "next/link";
import { Loader2, AlertCircle } from "lucide-react";
import { useLogin } from "@/hooks/useAuth";
import { cn } from "@/lib/utils";

// ─── Form validation schema ───────────────────────────────────────────────────

const loginSchema = z.object({
  // Accept .local / non-deliverable dev domains — full RFC validation is on the backend.
  email: z
    .string()
    .min(3, "Email is required")
    .refine((v) => v.includes("@") && v.split("@").length === 2, {
      message: "Please enter a valid email address",
    }),
  password: z.string().min(1, "Password is required"),
});

type LoginFormValues = z.infer<typeof loginSchema>;

// ─── Component ────────────────────────────────────────────────────────────────

export default function LoginPage() {
  const login = useLogin();

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
  });

  const onSubmit = (values: LoginFormValues) => {
    login.mutate(values);
  };

  return (
    <div className="min-h-screen bg-canvas-warm flex flex-col items-center justify-center p-6 font-sans">
      <div className="w-full max-w-md bg-canvas border border-hairline rounded-xl p-8 space-y-8">
        {/* Brand header */}
        <div className="flex flex-col items-center space-y-2">
          <h1 className="text-3xl font-extrabold text-brand-mark">
            CPQ COGNITIVE
          </h1>
          <p className="text-xs text-slate-500 font-semibold tracking-wide uppercase">
            Enterprise Client Workspace
          </p>
        </div>

        {/* API error banner */}
        {login.error && (
          <div className="flex items-center gap-3 px-4 py-3 rounded-lg bg-rose-50 border border-rose-200 text-sm text-rose-700">
            <AlertCircle size={16} className="shrink-0 text-rose-600" />
            <span>
              {(login.error as { detail?: string }).detail ?? "Login failed. Please try again."}
            </span>
          </div>
        )}

        {/* Form */}
        <form className="space-y-5" onSubmit={handleSubmit(onSubmit)} noValidate>
          {/* Email */}
          <div className="space-y-1.5">
            <label
              htmlFor="email"
              className="text-xs font-bold text-slate-600 uppercase tracking-wider"
            >
              Email Address
            </label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              placeholder="name@company.com"
              className={cn(
                "w-full px-4 py-3 bg-canvas border rounded-md text-sm text-ink focus:outline-none placeholder-slate-400 transition-colors",
                errors.email
                  ? "border-rose-600 focus:border-rose-600"
                  : "border-field-border focus:border-ink"
              )}
              {...register("email")}
            />
            {errors.email && (
              <p className="text-xs text-rose-600">{errors.email.message}</p>
            )}
          </div>

          {/* Password */}
          <div className="space-y-1.5">
            <div className="flex justify-between items-center">
              <label
                htmlFor="password"
                className="text-xs font-bold text-slate-600 uppercase tracking-wider"
              >
                Password
              </label>
              <a href="#" className="text-xs text-link hover:underline font-semibold">
                Forgot password?
              </a>
            </div>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              placeholder="••••••••"
              className={cn(
                "w-full px-4 py-3 bg-canvas border rounded-md text-sm text-ink focus:outline-none placeholder-slate-400 transition-colors",
                errors.password
                  ? "border-rose-600 focus:border-rose-600"
                  : "border-field-border focus:border-ink"
              )}
              {...register("password")}
            />
            {errors.password && (
              <p className="text-xs text-rose-600">{errors.password.message}</p>
            )}
          </div>

          {/* Submit */}
          <button
            id="login-submit"
            type="submit"
            disabled={login.isPending}
            className="w-full py-3.5 bg-primary text-white rounded-xs font-medium text-sm hover:bg-slate-700 disabled:opacity-60 disabled:cursor-not-allowed transition-all duration-200 flex items-center justify-center gap-2"
          >
            {login.isPending ? (
              <>
                <Loader2 size={16} className="animate-spin" />
                <span>Signing in…</span>
              </>
            ) : (
              "Sign In"
            )}
          </button>
        </form>

        {/* Switch to register */}
        <div className="text-center text-xs text-slate-500 font-medium">
          New to the platform?{" "}
          <Link href="/auth/register" className="text-link hover:underline font-bold">
            Request Registration
          </Link>
        </div>
      </div>
    </div>
  );
}
