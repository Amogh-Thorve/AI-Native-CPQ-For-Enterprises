"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import Link from "next/link";
import { ShieldCheck, Loader2, AlertCircle, Sparkles } from "lucide-react";
import { useLogin } from "@/hooks/useAuth";
import { cn } from "@/lib/utils";
import { DEMO_CREDENTIALS, DEMO_PENDING_STORAGE_KEY } from "@/lib/demoTour";

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
    setValue,
    formState: { errors },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
  });

  const fillDemoAccount = () => {
    setValue("email", DEMO_CREDENTIALS.email, { shouldValidate: true, shouldDirty: true });
    setValue("password", DEMO_CREDENTIALS.password, { shouldValidate: true, shouldDirty: true });
    sessionStorage.setItem(DEMO_PENDING_STORAGE_KEY, "1");
  };

  const onSubmit = (values: LoginFormValues) => {
    login.mutate(values);
  };

  return (
    <div className="min-h-screen bg-zinc-950 flex flex-col items-center justify-center p-6 font-sans">
      <div className="w-full max-w-md bg-zinc-900 border border-zinc-800 rounded-2xl p-8 space-y-8 shadow-2xl">
        {/* Brand header */}
        <div className="flex flex-col items-center space-y-2">
          <div className="p-3 rounded-2xl bg-zinc-800 border border-zinc-700/50">
            <ShieldCheck className="text-teal-400" size={32} />
          </div>
          <h1 className="text-2xl font-extrabold tracking-wider bg-gradient-to-r from-teal-400 to-emerald-400 bg-clip-text text-transparent">
            CPQ COGNITIVE
          </h1>
          <p className="text-xs text-zinc-500 font-semibold tracking-wide uppercase">
            Enterprise Client Workspace
          </p>
        </div>

        {/* API error banner */}
        {login.error && (
          <div className="flex items-center gap-3 px-4 py-3 rounded-lg bg-red-950/40 border border-red-800/50 text-sm text-red-300">
            <AlertCircle size={16} className="shrink-0 text-red-400" />
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
              className="text-xs font-bold text-zinc-400 uppercase tracking-wider"
            >
              Email Address
            </label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              placeholder="name@company.com"
              className={cn(
                "w-full px-4 py-3 bg-zinc-950 border rounded-xl text-sm text-zinc-200 focus:outline-none placeholder-zinc-600 transition-colors",
                errors.email
                  ? "border-red-700 focus:border-red-600"
                  : "border-zinc-800 focus:border-teal-600"
              )}
              {...register("email")}
            />
            {errors.email && (
              <p className="text-xs text-red-400">{errors.email.message}</p>
            )}
          </div>

          {/* Password */}
          <div className="space-y-1.5">
            <div className="flex justify-between items-center">
              <label
                htmlFor="password"
                className="text-xs font-bold text-zinc-400 uppercase tracking-wider"
              >
                Password
              </label>
              <a href="#" className="text-xs text-teal-400 hover:text-teal-300 font-semibold">
                Forgot password?
              </a>
            </div>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              placeholder="••••••••"
              className={cn(
                "w-full px-4 py-3 bg-zinc-950 border rounded-xl text-sm text-zinc-200 focus:outline-none placeholder-zinc-600 transition-colors",
                errors.password
                  ? "border-red-700 focus:border-red-600"
                  : "border-zinc-800 focus:border-teal-600"
              )}
              {...register("password")}
            />
            {errors.password && (
              <p className="text-xs text-red-400">{errors.password.message}</p>
            )}
          </div>

          {/* Submit */}
          <button
            id="login-submit"
            type="submit"
            disabled={login.isPending}
            className="w-full py-3.5 bg-teal-500 text-zinc-950 rounded-xl font-bold text-sm hover:bg-teal-400 disabled:opacity-60 disabled:cursor-not-allowed transition-all duration-200 shadow-lg shadow-teal-500/10 flex items-center justify-center gap-2"
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

        <button
          type="button"
          onClick={fillDemoAccount}
          className="w-full py-2.5 rounded-xl border border-teal-700/60 bg-zinc-950 text-teal-300 text-xs font-semibold hover:bg-zinc-800 hover:border-teal-500 transition-colors flex items-center justify-center gap-2"
        >
          <Sparkles size={14} />
          Use demo account
        </button>
        <p className="text-[11px] text-zinc-500 text-center">
          Fills {DEMO_CREDENTIALS.email}. Sign in to open the dashboard tour.
        </p>

        {/* Switch to register */}
        <div className="text-center text-xs text-zinc-500 font-medium">
          New to the platform?{" "}
          <Link href="/auth/register" className="text-teal-400 hover:text-teal-300 font-bold">
            Request Registration
          </Link>
        </div>
      </div>
    </div>
  );
}
