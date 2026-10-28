"use client";

import React, { useState } from "react";
import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { API_BASE, errorMessage } from "@/lib/api";

interface Proposal {
  company_name: string;
  quote_number: string;
  version: number;
  title?: string | null;
  description?: string | null;
  customer_name: string;
  status: string;
  currency: string;
  valid_until?: string | null;
  lines: { product_name?: string | null; sku?: string | null; billing_type: string; quantity: number; unit_price: string; discount_percentage: string; total_price: string }[];
  subtotal: string;
  discount_amount: string;
  tax_label?: string | null;
  tax_amount: string;
  total_amount: string;
  notes?: string | null;
  terms: string;
  has_pdf: boolean;
  can_respond: boolean;
  responded_by?: string | null;
  responded_at?: string | null;
}

// Public, unauthenticated: the unguessable token in the URL is the credential.
async function publicRequest<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: body ? "POST" : "GET",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw await res.json().catch(() => ({ detail: "Request failed." }));
  return res.json();
}

const money = (v: string, cur: string) => `${cur} ${Number(v).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

export default function ProposalPage() {
  const { token } = useParams<{ token: string }>();
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [note, setNote] = useState("");
  const [declining, setDeclining] = useState(false);

  const { data: p, isLoading, error } = useQuery<Proposal>({
    queryKey: ["proposal", token],
    queryFn: () => publicRequest<Proposal>(`/public/proposals/${token}`),
    retry: false,
  });

  const respond = useMutation({
    mutationFn: (kind: "accept" | "decline") =>
      publicRequest<Proposal>(`/public/proposals/${token}/${kind}`, kind === "accept" ? { name, note: note || undefined } : { name, reason: note || undefined }),
    onSuccess: (data) => queryClient.setQueryData(["proposal", token], data),
  });

  const inputCls = "w-full px-3 py-2.5 bg-canvas border border-field-border rounded-md text-sm focus:outline-none focus:border-ink";

  if (isLoading) return <div className="min-h-screen bg-canvas-warm p-8 text-sm text-slate-600">Loading proposal…</div>;
  if (error || !p)
    return (
      <div className="min-h-screen bg-canvas-warm flex items-center justify-center p-8">
        <div className="bg-canvas border border-hairline rounded-xl p-8 max-w-md text-center">
          <h1 className="text-3xl text-ink mb-2">Proposal not found</h1>
          <p className="text-sm text-slate-600">{errorMessage(error, "This link is not valid or has been removed.")}</p>
        </div>
      </div>
    );

  return (
    <div className="min-h-screen bg-canvas-warm">
      <header className="h-[72px] bg-canvas border-b border-hairline flex items-center px-8">
        <span className="font-extrabold text-xl text-brand-mark">{p.company_name}</span>
      </header>
      <main className="max-w-4xl mx-auto px-6 py-12 space-y-6">
        <div>
          <h1 className="text-4xl text-ink">{p.title || "Sales proposal"}</h1>
          <div className="mt-3 h-1 w-10 bg-accent-gold" />
          <p className="text-sm text-slate-600 mt-3">
            Prepared for <b className="text-ink">{p.customer_name}</b> · {p.quote_number} (v{p.version})
            {p.valid_until ? ` · valid until ${new Date(p.valid_until).toLocaleDateString()}` : ""}
          </p>
          {p.description && <p className="text-sm text-ink mt-3">{p.description}</p>}
        </div>

        <div className="bg-canvas border border-hairline rounded-xl overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="bg-canvas-tint text-xs text-slate-600">
              <tr>
                <th className="text-left px-4 py-3 font-semibold">Item</th>
                <th className="text-left px-4 py-3 font-semibold">Billing</th>
                <th className="text-right px-4 py-3 font-semibold">Qty</th>
                <th className="text-right px-4 py-3 font-semibold">Unit price</th>
                <th className="text-right px-4 py-3 font-semibold">Disc %</th>
                <th className="text-right px-4 py-3 font-semibold">Total</th>
              </tr>
            </thead>
            <tbody>
              {p.lines.map((l, i) => (
                <tr key={i} className="border-t border-hairline">
                  <td className="px-4 py-3">
                    <div className="font-semibold text-ink">{l.product_name}</div>
                    <div className="text-[11px] text-slate-500 font-mono">{l.sku}</div>
                  </td>
                  <td className="px-4 py-3">{l.billing_type}</td>
                  <td className="px-4 py-3 text-right">{l.quantity}</td>
                  <td className="px-4 py-3 text-right">{money(l.unit_price, p.currency)}</td>
                  <td className="px-4 py-3 text-right">{l.discount_percentage}</td>
                  <td className="px-4 py-3 text-right font-semibold">{money(l.total_price, p.currency)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="border-t border-hairline p-4 flex justify-end">
            <div className="w-64 space-y-1 text-sm">
              <div className="flex justify-between"><span className="text-slate-600">Subtotal</span><span>{money(p.subtotal, p.currency)}</span></div>
              {Number(p.discount_amount) > 0 && <div className="flex justify-between"><span className="text-slate-600">Discount</span><span>-{money(p.discount_amount, p.currency)}</span></div>}
              {Number(p.tax_amount) > 0 && <div className="flex justify-between"><span className="text-slate-600">{p.tax_label || "Tax"}</span><span>{money(p.tax_amount, p.currency)}</span></div>}
              <div className="flex justify-between border-t border-ink pt-2 font-extrabold text-base"><span>Total</span><span>{money(p.total_amount, p.currency)}</span></div>
            </div>
          </div>
        </div>

        {p.notes && <p className="text-sm text-ink">{p.notes}</p>}
        <p className="text-xs text-slate-600">{p.terms}</p>

        {p.has_pdf && (
          <a href={`${API_BASE}/public/proposals/${token}/pdf`} target="_blank" rel="noreferrer" className="inline-block text-sm text-link hover:underline">
            Download PDF
          </a>
        )}

        {p.can_respond ? (
          <div className="bg-canvas border border-hairline rounded-xl p-6 space-y-4">
            <h2 className="text-xl text-ink">Your response</h2>
            <input className={inputCls} placeholder="Your full name" value={name} onChange={(e) => setName(e.target.value)} />
            <textarea className={inputCls} rows={3} placeholder={declining ? "Reason (optional)" : "Comments (optional)"} value={note} onChange={(e) => setNote(e.target.value)} />
            {respond.isError && <p className="text-sm text-rose-600">{errorMessage(respond.error)}</p>}
            <div className="flex gap-3">
              {!declining ? (
                <>
                  <button
                    disabled={name.trim().length < 2 || respond.isPending}
                    onClick={() => respond.mutate("accept")}
                    className="px-4 py-2.5 bg-primary text-white rounded-xs text-sm font-medium hover:bg-slate-700 disabled:bg-canvas-soft disabled:text-slate-400 disabled:border disabled:border-hairline cursor-pointer disabled:cursor-not-allowed"
                  >
                    {respond.isPending ? "Submitting…" : "Accept proposal"}
                  </button>
                  <button onClick={() => setDeclining(true)} className="px-4 py-2.5 border border-ink text-ink rounded-xs text-sm font-medium hover:bg-ink/8 cursor-pointer">
                    Decline
                  </button>
                </>
              ) : (
                <>
                  <button
                    disabled={name.trim().length < 2 || respond.isPending}
                    onClick={() => respond.mutate("decline")}
                    className="px-4 py-2.5 border border-rose-600 text-rose-600 rounded-xs text-sm font-medium hover:bg-rose-50 disabled:opacity-50 cursor-pointer"
                  >
                    Confirm decline
                  </button>
                  <button onClick={() => setDeclining(false)} className="px-4 py-2.5 border border-ink text-ink rounded-xs text-sm font-medium cursor-pointer">
                    Back
                  </button>
                </>
              )}
            </div>
          </div>
        ) : (
          <div className="bg-canvas border border-hairline rounded-xl p-6">
            <h2 className="text-xl text-ink">
              {p.status === "ACCEPTED" ? "Proposal accepted" : p.status === "REJECTED" ? "Proposal declined" : "This proposal is no longer open for response"}
            </h2>
            {p.responded_by && (
              <p className="text-sm text-slate-600 mt-1">
                {p.responded_by}{p.responded_at ? ` · ${new Date(p.responded_at).toLocaleString()}` : ""}
              </p>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
