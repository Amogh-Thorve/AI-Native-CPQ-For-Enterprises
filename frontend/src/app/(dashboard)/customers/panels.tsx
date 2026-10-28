"use client";

import React from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Sparkles } from "lucide-react";
import { api, errorMessage } from "@/lib/api";
import { Button, StatusBadge } from "@/components/ui";
import { SourceTag } from "../quotes/ai-panels";

interface CustomerQuote {
  id: number;
  quote_number: string;
  version: number;
  title?: string | null;
  status: string;
  currency: string;
  total_amount: string;
  created_at: string;
  audit_logs: { id: number; action: string; user_role?: string | null; timestamp: string }[];
}

const money = (v: string, cur: string) => `${cur} ${Number(v).toLocaleString("en-US", { minimumFractionDigits: 2 })}`;

function useCustomerQuotes(customerId: number) {
  return useQuery<CustomerQuote[]>({
    queryKey: ["customer-quotes", customerId],
    queryFn: () => api.get<CustomerQuote[]>(`/quotes/?customer_id=${customerId}&limit=100`),
  });
}

export function CustomerQuotesTab({ customerId }: { customerId: number }) {
  const { data = [], isLoading, error } = useCustomerQuotes(customerId);
  if (isLoading) return <p className="text-slate-500">Loading quotes…</p>;
  if (error) return <p className="text-rose-600">{errorMessage(error)}</p>;
  if (data.length === 0) return <p className="text-slate-500 py-4 text-center">No quotes for this customer yet. Create one in the Quote Builder.</p>;
  return (
    <div className="divide-y divide-slate-100">
      {data.map((q) => (
        <div key={q.id} className="py-2.5 flex items-center justify-between gap-3">
          <div>
            <div className="font-semibold text-slate-800">{q.quote_number} <span className="text-slate-400 font-normal">v{q.version}</span></div>
            <div className="text-[11px] text-slate-500">{q.title || "Untitled"} · {new Date(q.created_at).toLocaleDateString()}</div>
          </div>
          <div className="text-right">
            <div className="font-semibold text-slate-800">{money(q.total_amount, q.currency)}</div>
            <StatusBadge status={q.status} />
          </div>
        </div>
      ))}
    </div>
  );
}

export function CustomerActivityTab({ customerId, createdAt }: { customerId: number; createdAt: string }) {
  const { data = [], isLoading } = useCustomerQuotes(customerId);
  if (isLoading) return <p className="text-slate-500">Loading activity…</p>;
  const events = data
    .flatMap((q) => q.audit_logs.map((a) => ({ ts: a.timestamp, text: `${a.action.replace(/_/g, " ").toLowerCase()} · ${q.quote_number}`, who: a.user_role })))
    .concat([{ ts: createdAt, text: "customer record created", who: null }])
    .sort((a, b) => new Date(b.ts).getTime() - new Date(a.ts).getTime())
    .slice(0, 40);
  return (
    <div className="space-y-3 pl-2 border-l border-slate-200">
      {events.map((e, i) => (
        <div key={i} className="relative pl-3">
          <span className="w-2 h-2 rounded-full bg-slate-400 absolute -left-[5px] top-1" />
          <div className="font-semibold text-slate-800 capitalize">{e.text}</div>
          <div className="text-[10px] text-slate-400">{e.who ? `${e.who} · ` : ""}{new Date(e.ts).toLocaleString()}</div>
        </div>
      ))}
    </div>
  );
}

export function CustomerAiBrief({ customerId }: { customerId: number }) {
  const brief = useMutation({
    mutationFn: () => api.post<{ summary_text: string; key_metrics: string[]; source: string }>("/ai/customer-summary", { customer_id: customerId }),
  });
  return (
    <div className="space-y-2">
      <Button size="sm" variant="secondary" icon={<Sparkles size={13} />} onClick={() => brief.mutate()} disabled={brief.isPending}>
        {brief.isPending ? "Analysing…" : "AI account briefing"}
      </Button>
      {brief.isError && <p className="text-rose-600">{errorMessage(brief.error)}</p>}
      {brief.data && (
        <div className="p-3 border border-slate-200 rounded-lg bg-white space-y-2">
          <div className="flex items-center gap-2"><SourceTag source={brief.data.source} /></div>
          <p className="text-slate-700">{brief.data.summary_text}</p>
          <ul className="text-[11px] text-slate-500 list-disc pl-4">
            {brief.data.key_metrics.map((m, i) => <li key={i}>{m}</li>)}
          </ul>
        </div>
      )}
    </div>
  );
}
