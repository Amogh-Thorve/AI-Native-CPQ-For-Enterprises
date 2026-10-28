"use client";

import React, { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Plus, Sparkles } from "lucide-react";
import { api, errorMessage } from "@/lib/api";
import { Button, Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui";

type Notify = (text: string, type?: "success" | "error") => void;

const inputCls = "w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-sm focus:outline-none focus:border-blue-500";

export function SourceTag({ source }: { source: string }) {
  return (
    <span className="text-[10px] font-medium text-slate-500 uppercase border border-hairline rounded px-1.5 py-0.5">
      {source === "gemini" ? "Gemini" : "Data-driven"}
    </span>
  );
}

// ─── Natural-language quote builder ─────────────────────────────────────────

interface Match { product_id: number; sku: string; name: string; base_price: number; currency: string }
interface ParsedLine { query: string; quantity: number; discount_percentage: number; matched: Match | null; confidence: number; alternatives: Match[] }
interface Parsed {
  source: string;
  customer_id: number | null;
  customer_name: string | null;
  title: string | null;
  lines: ParsedLine[];
  warnings: string[];
  created_quote_id: number | null;
  created_quote_number: string | null;
}

export function AiQuoteBuilder({ onCreated, notify }: { onCreated: (id: number) => void; notify: Notify }) {
  const queryClient = useQueryClient();
  const [prompt, setPrompt] = useState("");
  const [parsed, setParsed] = useState<Parsed | null>(null);
  const [customerSearch, setCustomerSearch] = useState("");
  const [customerOverride, setCustomerOverride] = useState<number | null>(null);

  const { data: customers } = useQuery<{ items: { id: number; legal_name: string; display_name?: string | null }[] }>({
    queryKey: ["ai-customers", customerSearch],
    queryFn: () => api.get(`/customers/?page=1&page_size=20${customerSearch ? `&search=${encodeURIComponent(customerSearch)}` : ""}`),
    enabled: parsed != null && parsed.customer_id == null,
  });

  const interpret = useMutation({
    mutationFn: () => api.post<Parsed>("/ai/quote-from-text", { prompt, customer_id: customerOverride ?? undefined }),
    onSuccess: setParsed,
    onError: (e) => notify(errorMessage(e), "error"),
  });
  const create = useMutation({
    mutationFn: () => api.post<Parsed>("/ai/quote-from-text", { prompt, customer_id: customerOverride ?? parsed?.customer_id ?? undefined, create: true }),
    onSuccess: (r) => {
      queryClient.invalidateQueries({ queryKey: ["quotes"] });
      notify(`Draft ${r.created_quote_number} created from your description.`);
      if (r.created_quote_id) onCreated(r.created_quote_id);
    },
    onError: (e) => notify(errorMessage(e), "error"),
  });

  const hasCustomer = (customerOverride ?? parsed?.customer_id) != null;
  const usable = parsed?.lines.filter((l) => l.matched).length ?? 0;

  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle className="text-sm flex items-center gap-2">
            <Sparkles size={14} className="text-slate-600" /> Describe the quote
            {parsed && <SourceTag source={parsed.source} />}
          </CardTitle>
          <CardDescription>
            e.g. “Quote for Acme Corp: 10 Dell Latitude 7440 and 50 cloud subscriptions with 8% discount, valid 45 days”. Products and customers are always matched against your real catalog.
          </CardDescription>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <textarea className={inputCls} rows={3} value={prompt} onChange={(e) => { setPrompt(e.target.value); setParsed(null); }} placeholder="Describe the customer, products, quantities and any discount…" />
        <div className="flex gap-2">
          <Button variant="secondary" icon={<Sparkles size={14} />} disabled={prompt.trim().length < 3 || interpret.isPending} onClick={() => interpret.mutate()}>
            {interpret.isPending ? "Interpreting…" : "Interpret"}
          </Button>
        </div>

        {parsed && (
          <div className="space-y-3 border-t border-hairline pt-3 text-sm">
            <div>
              <span className="text-slate-500">Customer: </span>
              {parsed.customer_id ? <b>{parsed.customer_name}</b> : <span className="text-rose-600">not recognised</span>}
            </div>
            {!parsed.customer_id && (
              <div className="space-y-2">
                <input className={inputCls} placeholder="Search for the customer…" value={customerSearch} onChange={(e) => setCustomerSearch(e.target.value)} />
                <select className={inputCls} size={4} value={customerOverride ?? ""} onChange={(e) => setCustomerOverride(Number(e.target.value))}>
                  {(customers?.items ?? []).map((c) => (
                    <option key={c.id} value={c.id}>{c.display_name || c.legal_name}</option>
                  ))}
                </select>
              </div>
            )}
            <div className="border border-hairline rounded-lg divide-y divide-hairline">
              {parsed.lines.length === 0 && <p className="p-3 text-slate-500">No products recognised.</p>}
              {parsed.lines.map((l, i) => (
                <div key={i} className="p-3 flex items-center justify-between gap-3">
                  <div>
                    <div className="text-slate-500 text-xs">“{l.query}” × {l.quantity}{l.discount_percentage ? ` · ${l.discount_percentage}% off` : ""}</div>
                    {l.matched ? (
                      <div className="font-semibold text-ink">{l.matched.name} <span className="font-mono text-[11px] text-slate-500">{l.matched.sku}</span></div>
                    ) : (
                      <div className="text-rose-600">No catalog match{l.alternatives.length ? ` — closest: ${l.alternatives.map((a) => a.name).join(", ")}` : ""}</div>
                    )}
                  </div>
                  {l.matched && <span className="text-xs text-slate-500">match {Math.round(l.confidence * 100)}%</span>}
                </div>
              ))}
            </div>
            {parsed.warnings.map((w, i) => (
              <p key={i} className="text-xs text-amber-700 flex items-center gap-1.5"><AlertTriangle size={12} /> {w}</p>
            ))}
            <Button variant="primary" disabled={!hasCustomer || usable === 0 || create.isPending} onClick={() => create.mutate()}>
              {create.isPending ? "Creating…" : `Create draft with ${usable} line(s)`}
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ─── Deal insights ──────────────────────────────────────────────────────────

interface Insights {
  win_probability: number | null;
  confidence: string;
  decided_quotes_used: number;
  current_discount: number;
  discount_bands: { band: string; decided: number; won: number; win_rate: number | null }[];
  discount_guidance: string | null;
  risks: string[];
  next_actions: string[];
  narrative: string;
  source: string;
}

export function DealInsightsCard({ quoteId, version }: { quoteId: number; version: string }) {
  const { data, isLoading, error } = useQuery<Insights>({
    queryKey: ["deal-insights", quoteId, version],
    queryFn: () => api.get<Insights>(`/ai/deal-insights/${quoteId}`),
    retry: false,
  });
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm flex items-center gap-2">
          <Sparkles size={14} className="text-slate-600" /> Deal insights {data && <SourceTag source={data.source} />}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        {isLoading && <p className="text-slate-500">Analysing…</p>}
        {error && <p className="text-rose-600">{errorMessage(error)}</p>}
        {data && (
          <>
            <div className="flex items-end gap-4">
              <div>
                <div className="text-[10px] uppercase font-bold text-slate-500">Win probability</div>
                <div className="text-3xl font-extrabold text-ink">{data.win_probability != null ? `${data.win_probability.toFixed(0)}%` : "—"}</div>
              </div>
              <div className="text-xs text-slate-500 pb-1.5">
                {data.confidence === "none" ? "No won/lost quotes yet" : `${data.confidence} confidence · ${data.decided_quotes_used} past outcomes`}
              </div>
            </div>
            <p className="text-slate-700">{data.narrative}</p>
            {data.discount_guidance && <p className="text-xs text-slate-600">{data.discount_guidance}</p>}
            {data.decided_quotes_used > 0 && (
              <div className="grid grid-cols-4 gap-2 text-center text-[11px]">
                {data.discount_bands.map((b) => (
                  <div key={b.band} className="border border-hairline rounded p-1.5">
                    <div className="text-slate-500">{b.band}</div>
                    <div className="font-bold text-ink">{b.win_rate != null ? `${b.win_rate}%` : "—"}</div>
                    <div className="text-slate-400">{b.won}/{b.decided}</div>
                  </div>
                ))}
              </div>
            )}
            {data.risks.length > 0 && (
              <ul className="text-xs text-rose-700 space-y-1">
                {data.risks.map((r, i) => <li key={i} className="flex gap-1.5"><AlertTriangle size={12} className="shrink-0 mt-0.5" />{r}</li>)}
              </ul>
            )}
            {data.next_actions.length > 0 && (
              <ul className="text-xs text-slate-700 list-disc pl-4 space-y-0.5">
                {data.next_actions.map((a, i) => <li key={i}>{a}</li>)}
              </ul>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}

// ─── Cross-sell recommendations ─────────────────────────────────────────────

interface Rec { product_id: number; name: string; sku: string; base_price: number; currency: string; reason: string }

export function RecommendationsCard({ customerId, currentProductIds, onAdd }: { customerId: number; currentProductIds: number[]; onAdd: (productId: number) => void }) {
  const { data, isLoading } = useQuery<{ recommendations: Rec[]; reasoning: string; source: string }>({
    queryKey: ["ai-recs", customerId, currentProductIds.join(",")],
    queryFn: () => api.post("/ai/recommendations", { customer_id: customerId, current_product_ids: currentProductIds }),
    retry: false,
  });
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm flex items-center gap-2">
          <Sparkles size={14} className="text-slate-600" /> Suggested add-ons {data && <SourceTag source={data.source} />}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
        {isLoading && <p className="text-slate-500">Finding suggestions…</p>}
        {data && data.recommendations.length === 0 && <p className="text-slate-500">{data.reasoning}</p>}
        {data?.recommendations.map((r) => (
          <div key={r.product_id} className="flex items-center justify-between gap-3 border-b border-hairline pb-2">
            <div>
              <div className="font-semibold text-ink">{r.name}</div>
              <div className="text-xs text-slate-500">{r.reason}</div>
            </div>
            <Button size="sm" variant="secondary" icon={<Plus size={12} />} onClick={() => onAdd(r.product_id)}>Add</Button>
          </div>
        ))}
        {data && data.recommendations.length > 0 && <p className="text-xs text-slate-500">{data.reasoning}</p>}
      </CardContent>
    </Card>
  );
}
