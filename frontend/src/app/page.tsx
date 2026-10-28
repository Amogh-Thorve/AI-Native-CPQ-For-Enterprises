import React from "react";
import Link from "next/link";

export default function Home() {
  return (
    <div className="min-h-screen bg-canvas flex flex-col font-sans">
      <header className="h-[72px] bg-canvas border-b border-hairline flex items-center justify-between px-8">
        <span className="font-extrabold text-xl text-brand-mark">CPQ Cognitive</span>
        <div className="flex items-center gap-3">
          <Link href="/auth/login" className="text-sm font-medium text-ink hover:underline">
            Sign in
          </Link>
          <Link
            href="/auth/register"
            className="px-4 py-2.5 bg-primary text-white rounded-xs text-sm font-medium hover:bg-slate-700 transition-colors"
          >
            Register
          </Link>
        </div>
      </header>

      <section className="bg-canvas-warm py-12 flex-1 flex items-center">
        <div className="max-w-4xl mx-auto px-8 space-y-6">
          <h1 className="text-5xl md:text-6xl text-ink">Enterprise Configure, Price &amp; Quote</h1>
          <div className="h-1 w-10 bg-accent-gold" aria-hidden="true" />
          <p className="text-2xl text-ink max-w-2xl" style={{ lineHeight: 1.4 }}>
            Configure bundles, price with volume and discount rules, route approvals, deliver proposals and sync won deals to Salesforce.
          </p>
          <div className="flex gap-3 pt-2">
            <Link
              href="/auth/login"
              className="px-4 py-2.5 bg-primary text-white rounded-xs text-sm font-medium hover:bg-slate-700 transition-colors"
            >
              Sign in
            </Link>
            <Link
              href="/auth/register"
              className="px-4 py-2.5 border border-ink text-ink rounded-xs text-sm font-medium hover:bg-ink/8 transition-colors"
            >
              Request access
            </Link>
          </div>
        </div>
      </section>

      <footer className="bg-canvas py-6 text-center text-xs text-ink border-t border-hairline">
        &copy; {new Date().getFullYear()} CPQ Cognitive. All rights reserved.
      </footer>
    </div>
  );
}
