"use client";

import React, { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  Download,
  FileText,
  Mail,
  Plus,
  RefreshCw,
  Send,
  Sparkles,
  Trash2,
  CheckCircle,
  Cloud,
  Copy,
  XCircle,
} from "lucide-react";
import { api, errorMessage } from "@/lib/api";
import {
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  DataTable,
  FilterSelect,
  Modal,
  PageHeader,
  SearchBar,
  StatusBadge,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui";

// ─── Types (mirror backend QuoteRead) ───────────────────────────────────────

interface CustomerSummary {
  id: number;
  name?: string;
  legal_name?: string | null;
  display_name?: string | null;
  customer_number?: string | null;
  email?: string | null;
}

interface QuoteLine {
  id: number;
  product_id: number;
  product_name?: string | null;
  sku?: string | null;
  billing_type: string;
  currency: string;
  quantity: number;
  unit_price: string;
  discount_percentage: string;
  discount_amount: string;
  total_price: string;
  margin_percentage?: string | null;
  pricing_method?: string | null;
  configuration_id?: string | null;
}

interface AuditLog {
  id: number;
  action: string;
  user_role?: string | null;
  timestamp: string;
  after_value?: Record<string, unknown> | null;
}

type QuoteStatus = "DRAFT" | "SUBMITTED" | "APPROVED" | "SENT" | "ACCEPTED" | "REJECTED" | "EXPIRED" | "CANCELLED";

interface Quote {
  id: number;
  quote_number: string;
  version: number;
  customer_id: number;
  title?: string | null;
  description?: string | null;
  notes?: string | null;
  status: QuoteStatus;
  currency: string;
  valid_until?: string | null;
  subtotal: string;
  discount_amount: string;
  tax_amount: string;
  total_amount: string;
  margin_percentage?: string | null;
  customer?: CustomerSummary | null;
  created_at: string;
  items: QuoteLine[];
  audit_logs: AuditLog[];
}

interface Product {
  id: number;
  sku: string;
  name: string;
  base_price: string | number;
  currency: string;
  is_active: boolean;
  billing_type: string;
}

interface QuoteDocument {
  id: number;
  generated_at: string;
  file_path: string;
}

interface EmailLog {
  id: number;
  recipient: string;
  subject: string;
  sent_at: string;
  status: string;
  error_message?: string | null;
}

interface PendingLine {
  product_id: number;
  product_name: string;
  quantity: number;
  configuration_id?: string;
  configuration_snapshot?: Record<string, unknown>;
}

const PENDING_LINE_KEY = "cpq_pending_line";

const money = (v: string | number | null | undefined, cur = "USD") =>
  `${cur} ${Number(v ?? 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

const customerName = (c?: CustomerSummary | null, id?: number) =>
  c?.display_name || c?.name || c?.legal_name || (id ? `Customer #${id}` : "—");

const fmtDate = (iso?: string | null) => (iso ? new Date(iso).toLocaleDateString() : "—");

const toIsoEndOfDay = (date: string) => (date ? `${date}T23:59:59Z` : undefined);

// ─── Page ───────────────────────────────────────────────────────────────────

type View = { mode: "list" } | { mode: "new" } | { mode: "detail"; id: number };

export default function QuotesPage() {
  const [view, setView] = useState<View>({ mode: "list" });
  const [notice, setNotice] = useState<{ text: string; type: "success" | "error" } | null>(null);

  const notify = (text: string, type: "success" | "error" = "success") => {
    setNotice({ text, type });
    setTimeout(() => setNotice(null), 5000);
  };

  return (
    <div className="space-y-6">
      {notice && (
        <div
          className={`fixed top-5 right-5 z-50 max-w-md px-4 py-3 rounded-xl shadow-lg border text-sm font-medium ${
            notice.type === "success"
              ? "bg-emerald-50 text-emerald-800 border-emerald-200"
              : "bg-rose-50 text-rose-800 border-rose-200"
          }`}
        >
          {notice.text}
        </div>
      )}
      {view.mode === "list" && (
        <QuoteList onOpen={(id) => setView({ mode: "detail", id })} onNew={() => setView({ mode: "new" })} />
      )}
      {view.mode === "new" && (
        <NewQuote
          onCancel={() => setView({ mode: "list" })}
          onCreated={(id) => setView({ mode: "detail", id })}
          notify={notify}
        />
      )}
      {view.mode === "detail" && (
        <QuoteDetail
          id={view.id}
          onBack={() => setView({ mode: "list" })}
          onOpen={(id) => setView({ mode: "detail", id })}
          notify={notify}
        />
      )}
    </div>
  );
}

// ─── List ───────────────────────────────────────────────────────────────────

function QuoteList({ onOpen, onNew }: { onOpen: (id: number) => void; onNew: () => void }) {
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("ALL");

  const { data: quotes = [], isLoading, error } = useQuery<Quote[]>({
    queryKey: ["quotes", status, search],
    queryFn: () => {
      const params = new URLSearchParams();
      if (status !== "ALL") params.append("status", status);
      if (search.trim()) params.append("search", search.trim());
      const qs = params.toString();
      return api.get<Quote[]>(qs ? `/quotes/?${qs}` : "/quotes/");
    },
  });

  return (
    <>
      <PageHeader
        title="Quotes"
        description="Build, approve, send and track customer quotes."
        actions={
          <Button variant="primary" icon={<Plus size={15} />} onClick={onNew}>
            New Quote
          </Button>
        }
      />
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-white p-3 rounded-xl border border-slate-200/80 shadow-xs">
        <SearchBar value={search} onChangeValue={setSearch} placeholder="Search by quote number or title..." className="w-full sm:w-80" />
        <FilterSelect value={status} onChange={(e) => setStatus(e.target.value)} label="Status">
          <option value="ALL">All Statuses</option>
          {["DRAFT", "SUBMITTED", "APPROVED", "SENT", "ACCEPTED", "REJECTED", "EXPIRED", "CANCELLED"].map((s) => (
            <option key={s} value={s}>
              {s.charAt(0) + s.slice(1).toLowerCase()}
            </option>
          ))}
        </FilterSelect>
      </div>
      <DataTable>
        <TableHead>
          <TableRow>
            <TableHeader>Quote #</TableHeader>
            <TableHeader>Title</TableHeader>
            <TableHeader>Customer</TableHeader>
            <TableHeader>Status</TableHeader>
            <TableHeader>Total</TableHeader>
            <TableHeader>Valid until</TableHeader>
            <TableHeader className="text-right">Actions</TableHeader>
          </TableRow>
        </TableHead>
        <tbody>
          {isLoading ? (
            <TableRow>
              <TableCell colSpan={7} className="text-center py-8 text-slate-500">Loading quotes…</TableCell>
            </TableRow>
          ) : error ? (
            <TableRow>
              <TableCell colSpan={7} className="text-center py-8 text-rose-600">{errorMessage(error, "Could not load quotes.")}</TableCell>
            </TableRow>
          ) : quotes.length === 0 ? (
            <TableRow>
              <TableCell colSpan={7} className="text-center py-8 text-slate-500">No quotes yet. Create the first one.</TableCell>
            </TableRow>
          ) : (
            quotes.map((q) => (
              <TableRow key={q.id} className="cursor-pointer" onClick={() => onOpen(q.id)}>
                <TableCell className="font-semibold text-slate-900">
                  {q.quote_number} <span className="text-slate-400 font-normal">v{q.version}</span>
                </TableCell>
                <TableCell className="text-slate-800">{q.title || "Untitled"}</TableCell>
                <TableCell className="text-slate-600">{customerName(q.customer, q.customer_id)}</TableCell>
                <TableCell><StatusBadge status={q.status} /></TableCell>
                <TableCell className="font-semibold text-slate-900">{money(q.total_amount, q.currency)}</TableCell>
                <TableCell className="text-slate-500">{fmtDate(q.valid_until)}</TableCell>
                <TableCell className="text-right">
                  <Button variant="secondary" size="sm" onClick={() => onOpen(q.id)}>Open</Button>
                </TableCell>
              </TableRow>
            ))
          )}
        </tbody>
      </DataTable>
    </>
  );
}

// ─── New quote ──────────────────────────────────────────────────────────────

function NewQuote({
  onCancel,
  onCreated,
  notify,
}: {
  onCancel: () => void;
  onCreated: (id: number) => void;
  notify: (t: string, type?: "success" | "error") => void;
}) {
  const queryClient = useQueryClient();
  const [customerSearch, setCustomerSearch] = useState("");
  const [customerId, setCustomerId] = useState<number | null>(null);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [validUntil, setValidUntil] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() + 30);
    return d.toISOString().slice(0, 10);
  });
  const [currency, setCurrency] = useState("USD");

  const { data: customers } = useQuery<{ items: CustomerSummary[] }>({
    queryKey: ["customers-picker", customerSearch],
    queryFn: () => {
      const params = new URLSearchParams({ page: "1", page_size: "50" });
      if (customerSearch.trim()) params.append("search", customerSearch.trim());
      return api.get<{ items: CustomerSummary[] }>(`/customers/?${params.toString()}`);
    },
  });

  const create = useMutation({
    mutationFn: () =>
      api.post<Quote>("/quotes/", {
        customer_id: customerId,
        title: title || undefined,
        description: description || undefined,
        currency,
        valid_until: toIsoEndOfDay(validUntil),
        items: [],
      }),
    onSuccess: (q) => {
      queryClient.invalidateQueries({ queryKey: ["quotes"] });
      notify(`Draft ${q.quote_number} created. Add products below.`);
      onCreated(q.id);
    },
    onError: (e) => notify(errorMessage(e, "Failed to create quote."), "error"),
  });

  const inputCls = "w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-sm focus:outline-none focus:border-blue-500";

  return (
    <>
      <button onClick={onCancel} className="flex items-center gap-1.5 text-xs font-medium text-slate-500 hover:text-slate-800 cursor-pointer">
        <ArrowLeft size={14} /> Back to quotes
      </button>
      <PageHeader title="New Quote" description="Choose the customer, then add products on the next screen." />
      <Card>
        <CardContent className="p-5 grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="md:col-span-2 space-y-2">
            <label className="text-xs font-semibold text-slate-700">Customer *</label>
            <input className={inputCls} placeholder="Search customers…" value={customerSearch} onChange={(e) => setCustomerSearch(e.target.value)} />
            <select
              size={6}
              className={inputCls}
              value={customerId ?? ""}
              onChange={(e) => setCustomerId(Number(e.target.value))}
            >
              {(customers?.items ?? []).map((c) => (
                <option key={c.id} value={c.id}>
                  {customerName(c)} {c.customer_number ? `(${c.customer_number})` : ""}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1">
            <label className="text-xs font-semibold text-slate-700">Quote title</label>
            <input className={inputCls} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Network refresh – Phase 1" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-xs font-semibold text-slate-700">Valid until</label>
              <input type="date" className={inputCls} value={validUntil} onChange={(e) => setValidUntil(e.target.value)} />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-semibold text-slate-700">Currency</label>
              <select className={inputCls} value={currency} onChange={(e) => setCurrency(e.target.value)}>
                <option>USD</option>
              </select>
            </div>
          </div>
          <div className="md:col-span-2 space-y-1">
            <label className="text-xs font-semibold text-slate-700">Description</label>
            <textarea className={inputCls} rows={3} value={description} onChange={(e) => setDescription(e.target.value)} />
          </div>
          <div className="md:col-span-2 flex justify-end gap-2">
            <Button variant="secondary" onClick={onCancel}>Cancel</Button>
            <Button variant="primary" disabled={!customerId || create.isPending} onClick={() => create.mutate()}>
              {create.isPending ? "Creating…" : "Create draft"}
            </Button>
          </div>
        </CardContent>
      </Card>
    </>
  );
}

// ─── Detail ─────────────────────────────────────────────────────────────────

function QuoteDetail({
  id,
  onBack,
  onOpen,
  notify,
}: {
  id: number;
  onBack: () => void;
  onOpen: (id: number) => void;
  notify: (t: string, type?: "success" | "error") => void;
}) {
  const queryClient = useQueryClient();
  const [pickerOpen, setPickerOpen] = useState(false);
  const [emailOpen, setEmailOpen] = useState(false);
  const [aiSummary, setAiSummary] = useState<{ summary_text: string; explanation: string; source: string } | null>(null);
  const [pending, setPending] = useState<PendingLine | null>(() => {
    try {
      const raw = typeof window !== "undefined" ? sessionStorage.getItem(PENDING_LINE_KEY) : null;
      return raw ? (JSON.parse(raw) as PendingLine) : null;
    } catch {
      return null; // malformed handoff
    }
  });

  const { data: quote, isLoading, error } = useQuery<Quote>({
    queryKey: ["quote", id],
    queryFn: () => api.get<Quote>(`/quotes/${id}`),
  });

  const { data: documents = [] } = useQuery<QuoteDocument[]>({
    queryKey: ["quote-documents", id],
    queryFn: () => api.get<QuoteDocument[]>(`/documents/quote/${id}`),
  });
  const { data: emails = [] } = useQuery<EmailLog[]>({
    queryKey: ["quote-emails", id],
    queryFn: () => api.get<EmailLog[]>(`/emails/quote/${id}`),
  });
  const { data: sf } = useQuery<{ connected: boolean }>({
    queryKey: ["salesforce-status"],
    queryFn: () => api.get<{ connected: boolean }>("/integrations/salesforce/status"),
  });

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["quote", id] });
    queryClient.invalidateQueries({ queryKey: ["quotes"] });
    queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    queryClient.invalidateQueries({ queryKey: ["approval-requests"] });
  };
  const fail = (e: unknown) => notify(errorMessage(e), "error");

  const addLine = useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post(`/quotes/${id}/items`, body),
    onSuccess: () => refresh(),
    onError: fail,
  });
  const updateLine = useMutation({
    mutationFn: ({ itemId, body }: { itemId: number; body: Record<string, unknown> }) =>
      api.put(`/quotes/${id}/items/${itemId}`, body),
    onSuccess: () => refresh(),
    onError: fail,
  });
  const removeLine = useMutation({
    mutationFn: (itemId: number) => api.delete(`/quotes/${id}/items/${itemId}`),
    onSuccess: () => refresh(),
    onError: fail,
  });
  const action = useMutation({
    mutationFn: ({ path, label }: { path: string; label: string }) =>
      api.post<Quote>(`/quotes/${id}/${path}`).then((q) => ({ q, label })),
    onSuccess: ({ q, label }) => {
      refresh();
      notify(label);
      if (q.id !== id) onOpen(q.id);
    },
    onError: fail,
  });
  const generate = useMutation({
    mutationFn: () => api.post<QuoteDocument>("/documents/generate", { quote_id: id }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["quote-documents", id] });
      notify("Proposal PDF generated.");
    },
    onError: fail,
  });
  const summarize = useMutation({
    mutationFn: () => api.post<{ summary_text: string; explanation: string; source: string }>("/ai/quote-summary", { quote_id: id }),
    onSuccess: setAiSummary,
    onError: fail,
  });
  const syncSf = useMutation({
    mutationFn: () => api.post<{ status: string; error_summary?: string | null }>(`/integrations/salesforce/sync-quote/${id}`),
    onSuccess: (log) => {
      refresh();
      if (log.status === "success") notify("Synced to Salesforce.");
      else notify(log.error_summary || "Salesforce sync failed.", "error");
    },
    onError: fail,
  });

  const downloadPdf = async (docId: number) => {
    try {
      const blob = await api.download(`/documents/${docId}/download`);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${quote?.quote_number ?? "quote"}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      fail(e);
    }
  };

  const addPendingLine = () => {
    if (!pending) return;
    addLine.mutate(
      {
        product_id: pending.product_id,
        quantity: pending.quantity,
        discount_percentage: 0,
        configuration_id: pending.configuration_id,
        configuration_snapshot: pending.configuration_snapshot,
      },
      {
        onSuccess: () => {
          sessionStorage.removeItem(PENDING_LINE_KEY);
          setPending(null);
          notify("Configured product added to the quote.");
        },
      }
    );
  };

  if (isLoading) return <p className="text-sm text-slate-500">Loading quote…</p>;
  if (error || !quote) return <p className="text-sm text-rose-600">{errorMessage(error, "Quote not found.")}</p>;

  const isDraft = quote.status === "DRAFT";
  const canDeliver = ["APPROVED", "SENT", "ACCEPTED"].includes(quote.status);
  const showMargin = quote.margin_percentage != null;

  return (
    <>
      <button onClick={onBack} className="flex items-center gap-1.5 text-xs font-medium text-slate-500 hover:text-slate-800 cursor-pointer">
        <ArrowLeft size={14} /> Back to quotes
      </button>
      <PageHeader
        title={`${quote.quote_number} · v${quote.version}`}
        description={`${quote.title || "Untitled quote"} — ${customerName(quote.customer, quote.customer_id)}`}
        actions={<StatusBadge status={quote.status} />}
      />

      {pending && isDraft && (
        <div className="flex items-center justify-between gap-3 p-3 rounded-xl border border-blue-200 bg-blue-50 text-sm text-blue-900">
          <span>
            Configured product ready: <b>{pending.product_name}</b> × {pending.quantity}
          </span>
          <div className="flex gap-2">
            <Button size="sm" variant="primary" onClick={addPendingLine} disabled={addLine.isPending}>Add to this quote</Button>
            <Button size="sm" variant="secondary" onClick={() => { sessionStorage.removeItem(PENDING_LINE_KEY); setPending(null); }}>Dismiss</Button>
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="flex flex-wrap gap-2">
        {isDraft && (
          <>
            <Button variant="secondary" icon={<Plus size={14} />} onClick={() => setPickerOpen(true)}>Add product</Button>
            <Button
              variant="primary"
              icon={<Send size={14} />}
              disabled={quote.items.length === 0 || action.isPending}
              onClick={() => action.mutate({ path: "submit", label: "Quote submitted. Check Approvals if review is required." })}
            >
              Submit for approval
            </Button>
          </>
        )}
        {canDeliver && (
          <>
            <Button variant="secondary" icon={<FileText size={14} />} onClick={() => generate.mutate()} disabled={generate.isPending}>
              {generate.isPending ? "Generating…" : "Generate PDF"}
            </Button>
            <Button variant="secondary" icon={<Mail size={14} />} disabled={documents.length === 0} onClick={() => setEmailOpen(true)}>
              Email proposal
            </Button>
            {quote.status !== "ACCEPTED" && (
              <Button variant="success" icon={<CheckCircle size={14} />} onClick={() => action.mutate({ path: "accept", label: "Quote marked as accepted." })}>
                Mark accepted
              </Button>
            )}
            {sf?.connected && (
              <Button variant="secondary" icon={<Cloud size={14} />} onClick={() => syncSf.mutate()} disabled={syncSf.isPending}>
                Sync to Salesforce
              </Button>
            )}
          </>
        )}
        <Button variant="secondary" icon={<Sparkles size={14} />} onClick={() => summarize.mutate()} disabled={summarize.isPending}>
          {summarize.isPending ? "Analysing…" : "AI summary"}
        </Button>
        {["APPROVED", "SENT", "ACCEPTED", "REJECTED", "EXPIRED", "CANCELLED"].includes(quote.status) && (
          <Button variant="secondary" icon={<Copy size={14} />} onClick={() => action.mutate({ path: "revise", label: "New revision created as a draft." })}>
            Revise
          </Button>
        )}
        {!["CANCELLED", "REJECTED", "ACCEPTED", "EXPIRED"].includes(quote.status) && (
          <Button variant="danger" icon={<XCircle size={14} />} onClick={() => { if (confirm("Cancel this quote?")) action.mutate({ path: "cancel", label: "Quote cancelled." }); }}>
            Cancel quote
          </Button>
        )}
      </div>

      {aiSummary && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm flex items-center gap-2">
              <Sparkles size={14} className="text-teal-600" /> AI summary
              <span className="text-[10px] font-medium text-slate-400 uppercase">{aiSummary.source === "gemini" ? "Gemini" : "Data-driven"}</span>
            </CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-slate-700 space-y-2">
            <p>{aiSummary.summary_text}</p>
            <p className="text-slate-500">{aiSummary.explanation}</p>
          </CardContent>
        </Card>
      )}

      {/* Line items */}
      <DataTable>
        <TableHead>
          <TableRow>
            <TableHeader>Product</TableHeader>
            <TableHeader>Billing</TableHeader>
            <TableHeader className="text-right">Qty</TableHeader>
            <TableHeader className="text-right">Unit price</TableHeader>
            <TableHeader className="text-right">Disc %</TableHeader>
            <TableHeader className="text-right">Total</TableHeader>
            {showMargin && <TableHeader className="text-right">Margin</TableHeader>}
            {isDraft && <TableHeader />}
          </TableRow>
        </TableHead>
        <tbody>
          {quote.items.length === 0 ? (
            <TableRow>
              <TableCell colSpan={8} className="text-center py-8 text-slate-500">No products yet.</TableCell>
            </TableRow>
          ) : (
            quote.items.map((it) => (
              <TableRow key={it.id}>
                <TableCell>
                  <div className="font-semibold text-slate-900">{it.product_name}</div>
                  <div className="text-[11px] text-slate-400 font-mono">
                    {it.sku} {it.configuration_id ? "· configured" : ""}
                  </div>
                </TableCell>
                <TableCell>{it.billing_type}</TableCell>
                <TableCell className="text-right">
                  {isDraft ? (
                    <NumberCell
                      key={`q-${it.id}-${it.quantity}`}
                      value={it.quantity}
                      min={1}
                      step={1}
                      onCommit={(v) => updateLine.mutate({ itemId: it.id, body: { quantity: v } })}
                    />
                  ) : (
                    it.quantity
                  )}
                </TableCell>
                <TableCell className="text-right">{money(it.unit_price, it.currency)}</TableCell>
                <TableCell className="text-right">
                  {isDraft ? (
                    <NumberCell
                      key={`d-${it.id}-${it.discount_percentage}`}
                      value={Number(it.discount_percentage)}
                      min={0}
                      max={100}
                      step={0.5}
                      onCommit={(v) => updateLine.mutate({ itemId: it.id, body: { discount_percentage: v } })}
                    />
                  ) : (
                    Number(it.discount_percentage).toFixed(1)
                  )}
                </TableCell>
                <TableCell className="text-right font-semibold">{money(it.total_price, it.currency)}</TableCell>
                {showMargin && (
                  <TableCell className="text-right text-slate-500">
                    {it.margin_percentage != null ? `${Number(it.margin_percentage).toFixed(1)}%` : "—"}
                  </TableCell>
                )}
                {isDraft && (
                  <TableCell className="text-right">
                    <button onClick={() => removeLine.mutate(it.id)} className="p-1.5 text-slate-400 hover:text-rose-600 cursor-pointer" title="Remove line">
                      <Trash2 size={14} />
                    </button>
                  </TableCell>
                )}
              </TableRow>
            ))
          )}
        </tbody>
      </DataTable>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
        <div className="lg:col-span-2 space-y-6">
          {/* Documents & emails */}
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Proposal documents & delivery</CardTitle>
              <CardDescription>PDFs are generated once a quote is approved.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              {documents.length === 0 && emails.length === 0 && <p className="text-slate-500">Nothing generated or sent yet.</p>}
              {documents.map((d) => (
                <div key={d.id} className="flex items-center justify-between">
                  <span className="text-slate-700">PDF · {new Date(d.generated_at + "Z").toLocaleString()}</span>
                  <Button size="sm" variant="secondary" icon={<Download size={13} />} onClick={() => downloadPdf(d.id)}>Download</Button>
                </div>
              ))}
              {emails.map((m) => (
                <div key={m.id} className="flex items-start justify-between gap-3 border-t border-slate-100 pt-2">
                  <div>
                    <div className="text-slate-800">{m.subject}</div>
                    <div className="text-xs text-slate-500">
                      to {m.recipient} · {new Date(m.sent_at + "Z").toLocaleString()}
                    </div>
                    {m.error_message && <div className="text-xs text-rose-600 mt-0.5">{m.error_message}</div>}
                  </div>
                  <StatusBadge status={m.status === "sent" ? "APPROVED" : "REJECTED"} className="shrink-0" showDot={false} />
                </div>
              ))}
            </CardContent>
          </Card>

          {/* Audit */}
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Activity</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-xs">
              {quote.audit_logs.length === 0 && <p className="text-slate-500">No activity recorded.</p>}
              {quote.audit_logs.map((a) => (
                <div key={a.id} className="flex justify-between gap-3 border-b border-slate-100 pb-1.5">
                  <span className="font-medium text-slate-700">{a.action.replace(/_/g, " ").toLowerCase()}</span>
                  <span className="text-slate-400">
                    {a.user_role ? `${a.user_role} · ` : ""}
                    {new Date(a.timestamp).toLocaleString()}
                  </span>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>

        {/* Totals */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Totals</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <Row label="Subtotal" value={money(quote.subtotal, quote.currency)} />
            {Number(quote.discount_amount) > 0 && <Row label="Discount" value={`-${money(quote.discount_amount, quote.currency)}`} />}
            {Number(quote.tax_amount) > 0 && <Row label="Tax" value={money(quote.tax_amount, quote.currency)} />}
            <div className="border-t border-slate-200 pt-2">
              <Row label="Total" value={money(quote.total_amount, quote.currency)} strong />
            </div>
            {showMargin && <Row label="Blended margin" value={`${Number(quote.margin_percentage).toFixed(1)}%`} />}
            <Row label="Valid until" value={fmtDate(quote.valid_until)} />
          </CardContent>
        </Card>
      </div>

      <ProductPicker
        isOpen={pickerOpen}
        onClose={() => setPickerOpen(false)}
        onPick={(p) => {
          addLine.mutate({ product_id: p.id, quantity: 1, discount_percentage: 0 }, { onSuccess: () => setPickerOpen(false) });
        }}
      />
      <EmailModal
        isOpen={emailOpen}
        onClose={() => setEmailOpen(false)}
        quoteId={id}
        onSent={(ok, msg) => {
          queryClient.invalidateQueries({ queryKey: ["quote-emails", id] });
          refresh();
          notify(msg, ok ? "success" : "error");
          if (ok) setEmailOpen(false);
        }}
      />
    </>
  );
}

function Row({ label, value, strong }: { label: string; value: string; strong?: boolean }) {
  return (
    <div className="flex justify-between">
      <span className="text-slate-500">{label}</span>
      <span className={strong ? "font-bold text-slate-900 text-base" : "font-medium text-slate-800"}>{value}</span>
    </div>
  );
}

/** Numeric input that commits on blur/Enter so every keystroke doesn't trigger a repricing call. */
function NumberCell({
  value,
  min,
  max,
  step,
  onCommit,
}: {
  value: number;
  min: number;
  max?: number;
  step: number;
  onCommit: (v: number) => void;
}) {
  const [text, setText] = useState(String(value));
  const commit = () => {
    let n = Number(text);
    if (Number.isNaN(n)) n = value;
    n = Math.max(min, max != null ? Math.min(max, n) : n);
    setText(String(n));
    if (n !== value) onCommit(n);
  };
  return (
    <input
      type="number"
      value={text}
      min={min}
      max={max}
      step={step}
      onChange={(e) => setText(e.target.value)}
      onBlur={commit}
      onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
      className="w-20 px-2 py-1 text-right border border-slate-200 rounded-md text-sm focus:outline-none focus:border-blue-500"
    />
  );
}

function ProductPicker({ isOpen, onClose, onPick }: { isOpen: boolean; onClose: () => void; onPick: (p: Product) => void }) {
  const [search, setSearch] = useState("");
  const { data: products = [], isLoading } = useQuery<Product[]>({
    queryKey: ["product-picker", search],
    queryFn: () => {
      const params = new URLSearchParams({ limit: "30", status: "active" });
      if (search.trim()) params.append("search", search.trim());
      return api.get<Product[]>(`/products?${params.toString()}`);
    },
    enabled: isOpen,
  });
  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Add product" description="Prices are calculated by the pricing engine when the line is added." maxWidth="2xl">
      <div className="space-y-3">
        <SearchBar value={search} onChangeValue={setSearch} placeholder="Search by name or SKU…" />
        <div className="max-h-96 overflow-y-auto divide-y divide-slate-100 border border-slate-200 rounded-lg">
          {isLoading ? (
            <p className="p-4 text-sm text-slate-500">Loading…</p>
          ) : products.length === 0 ? (
            <p className="p-4 text-sm text-slate-500">No matching active products.</p>
          ) : (
            products.map((p) => (
              <button
                key={p.id}
                onClick={() => onPick(p)}
                className="w-full flex items-center justify-between gap-3 px-4 py-2.5 text-left hover:bg-slate-50 cursor-pointer"
              >
                <div>
                  <div className="text-sm font-semibold text-slate-900">{p.name}</div>
                  <div className="text-[11px] text-slate-400 font-mono">{p.sku} · {p.billing_type}</div>
                </div>
                <span className="text-sm text-slate-600">{money(p.base_price, p.currency)}</span>
              </button>
            ))
          )}
        </div>
      </div>
    </Modal>
  );
}

function EmailModal({
  isOpen,
  onClose,
  quoteId,
  onSent,
}: {
  isOpen: boolean;
  onClose: () => void;
  quoteId: number;
  onSent: (ok: boolean, msg: string) => void;
}) {
  const [recipient, setRecipient] = useState("");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [source, setSource] = useState<string>("");

  const draft = useMutation({
    mutationFn: () =>
      api.post<{ subject: string; body: string; recipient?: string | null; source: string }>("/ai/draft-email", { quote_id: quoteId }),
    onSuccess: (d) => {
      setSubject(d.subject);
      setBody(d.body);
      if (d.recipient) setRecipient(d.recipient);
      setSource(d.source);
    },
  });
  useEffect(() => {
    if (isOpen) draft.mutate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen]);

  const send = useMutation({
    mutationFn: () =>
      api.post<EmailLog>("/emails/send", { quote_id: quoteId, recipient, subject, body }),
    onSuccess: (log) =>
      log.status === "sent"
        ? onSent(true, `Proposal emailed to ${log.recipient}.`)
        : onSent(false, log.error_message || "Email could not be delivered."),
    onError: (e) => onSent(false, errorMessage(e, "Failed to send email.")),
  });

  const inputCls = "w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-sm focus:outline-none focus:border-blue-500";
  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Email proposal"
      description="The latest generated PDF is attached automatically."
      maxWidth="2xl"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Close</Button>
          <Button variant="secondary" icon={<RefreshCw size={13} />} onClick={() => draft.mutate()} disabled={draft.isPending}>
            Redraft
          </Button>
          <Button variant="primary" icon={<Send size={14} />} onClick={() => send.mutate()} disabled={!recipient || !subject || !body || send.isPending}>
            {send.isPending ? "Sending…" : "Send"}
          </Button>
        </>
      }
    >
      <div className="space-y-3">
        {draft.isPending && <p className="text-xs text-slate-500">Drafting email…</p>}
        {source && <p className="text-[11px] text-slate-400">Draft generated by {source === "gemini" ? "Gemini" : "the data-driven template"} — review before sending.</p>}
        <input className={inputCls} placeholder="Recipient email" value={recipient} onChange={(e) => setRecipient(e.target.value)} />
        <input className={inputCls} placeholder="Subject" value={subject} onChange={(e) => setSubject(e.target.value)} />
        <textarea className={inputCls} rows={10} value={body} onChange={(e) => setBody(e.target.value)} />
      </div>
    </Modal>
  );
}
