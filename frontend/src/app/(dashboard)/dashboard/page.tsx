"use client";

import React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, ArrowRight, CheckCircle, FileText, TrendingUp, Users } from "lucide-react";
import { api, errorMessage } from "@/lib/api";
import {
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  DataTable,
  MetricCard,
  PageHeader,
  StatusBadge,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui";

interface Dashboard {
  won_revenue: number;
  won_revenue_this_month: number;
  won_revenue_last_month: number;
  open_pipeline_value: number;
  open_quotes: number;
  status_counts: Record<string, number>;
  pending_approvals: number;
  win_rate_percent: number | null;
  average_margin_percent: number | null;
  total_customers: number;
  monthly: { month: string; won_revenue: number; quotes_created: number }[];
  top_products: { name: string; value: number }[];
  top_customers: { name: string; value: number }[];
  recent_quotes: {
    id: number;
    quote_number: string;
    title: string | null;
    customer_name: string;
    total_amount: number;
    currency: string;
    status: string;
    created_at: string;
  }[];
}

const usd = (n: number) => `$${n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

function monthDelta(cur: number, prev: number): { value: string; isPositive: boolean } | undefined {
  if (prev <= 0) return undefined;
  const pct = ((cur - prev) / prev) * 100;
  return { value: `${pct >= 0 ? "+" : ""}${pct.toFixed(1)}%`, isPositive: pct >= 0 };
}

function RankList({ title, rows }: { title: string; rows: { name: string; value: number }[] }) {
  const max = Math.max(1, ...rows.map((r) => r.value));
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">{title}</CardTitle>
        <CardDescription>By open and accepted quote value</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {rows.length === 0 && <p className="text-sm text-slate-500">No quote data yet.</p>}
        {rows.map((r) => (
          <div key={r.name} className="space-y-1">
            <div className="flex justify-between text-xs">
              <span className="font-medium text-slate-700 truncate pr-2">{r.name}</span>
              <span className="text-slate-500">{usd(r.value)}</span>
            </div>
            <div className="h-1.5 rounded-full bg-slate-100">
              <div className="h-1.5 rounded-full bg-blue-500" style={{ width: `${(r.value / max) * 100}%` }} />
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

export default function DashboardHome() {
  const { data, isLoading, error } = useQuery<Dashboard>({
    queryKey: ["dashboard"],
    queryFn: () => api.get<Dashboard>("/analytics/dashboard"),
  });

  const maxMonth = Math.max(1, ...(data?.monthly ?? []).map((m) => m.won_revenue));
  const draftCount = data?.status_counts?.DRAFT ?? 0;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Workspace Overview"
        description="Live pipeline, approvals and revenue from your quotes."
        actions={
          <Link href="/quotes">
            <Button variant="primary" icon={<ArrowRight size={14} />} iconPosition="right">
              Go to quotes
            </Button>
          </Link>
        }
      />

      {error && <p className="text-sm text-rose-600">{errorMessage(error, "Could not load dashboard.")}</p>}
      {isLoading && <p className="text-sm text-slate-500">Loading dashboard…</p>}

      {data && (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <MetricCard
              title="Won Revenue"
              value={usd(data.won_revenue)}
              subtext={`${usd(data.won_revenue_this_month)} this month`}
              icon={<TrendingUp size={18} className="text-blue-600" />}
              trend={monthDelta(data.won_revenue_this_month, data.won_revenue_last_month)}
            />
            <MetricCard
              title="Open Pipeline"
              value={usd(data.open_pipeline_value)}
              subtext={`${data.open_quotes} open quote(s), ${draftCount} draft`}
              icon={<FileText size={18} className="text-teal-600" />}
            />
            <MetricCard
              title="Pending Approvals"
              value={data.pending_approvals}
              subtext={data.pending_approvals ? "Awaiting a decision" : "Nothing waiting"}
              icon={<AlertTriangle size={18} className="text-amber-600" />}
            />
            <MetricCard
              title="Win Rate"
              value={data.win_rate_percent != null ? `${data.win_rate_percent}%` : "—"}
              subtext={
                data.average_margin_percent != null
                  ? `Avg margin ${data.average_margin_percent}%`
                  : data.win_rate_percent == null
                    ? "No decided quotes yet"
                    : "Accepted vs rejected/expired"
              }
              icon={<CheckCircle size={18} className="text-emerald-600" />}
            />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
            <Card className="lg:col-span-2">
              <CardHeader>
                <CardTitle className="text-sm">Won revenue, last 6 months</CardTitle>
                <CardDescription>Accepted quotes by month of acceptance</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex items-end gap-3 h-40">
                  {data.monthly.map((m) => (
                    <div key={m.month} className="flex-1 flex flex-col items-center justify-end gap-1 h-full">
                      <span className="text-[10px] text-slate-500">{m.won_revenue > 0 ? usd(m.won_revenue) : ""}</span>
                      <div
                        className="w-full rounded-t bg-blue-500/80 min-h-[2px]"
                        style={{ height: `${(m.won_revenue / maxMonth) * 100}%` }}
                        title={`${m.quotes_created} quote(s) created`}
                      />
                      <span className="text-[10px] text-slate-400">{m.month.slice(5)}/{m.month.slice(2, 4)}</span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-sm flex items-center gap-2">
                  <Users size={14} className="text-slate-500" /> Pipeline by status
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {Object.keys(data.status_counts).length === 0 && <p className="text-sm text-slate-500">No quotes yet.</p>}
                {Object.entries(data.status_counts).map(([status, count]) => (
                  <div key={status} className="flex items-center justify-between">
                    <StatusBadge status={status} />
                    <span className="text-sm font-semibold text-slate-800">{count}</span>
                  </div>
                ))}
                <div className="pt-2 text-xs text-slate-400">{data.total_customers} active customer record(s)</div>
              </CardContent>
            </Card>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <RankList title="Top products" rows={data.top_products} />
            <RankList title="Top customers" rows={data.top_customers} />
          </div>

          <div className="space-y-3">
            <h2 className="text-sm font-semibold text-slate-800">Recent quotes</h2>
            <DataTable>
              <TableHead>
                <TableRow>
                  <TableHeader>Quote #</TableHeader>
                  <TableHeader>Title</TableHeader>
                  <TableHeader>Customer</TableHeader>
                  <TableHeader>Status</TableHeader>
                  <TableHeader className="text-right">Total</TableHeader>
                  <TableHeader>Created</TableHeader>
                </TableRow>
              </TableHead>
              <tbody>
                {data.recent_quotes.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} className="text-center py-8 text-slate-500">No quotes yet.</TableCell>
                  </TableRow>
                ) : (
                  data.recent_quotes.map((q) => (
                    <TableRow key={q.id}>
                      <TableCell className="font-semibold text-slate-900">{q.quote_number}</TableCell>
                      <TableCell>{q.title || "Untitled"}</TableCell>
                      <TableCell className="text-slate-600">{q.customer_name}</TableCell>
                      <TableCell><StatusBadge status={q.status} /></TableCell>
                      <TableCell className="text-right font-semibold">{usd(q.total_amount)}</TableCell>
                      <TableCell className="text-slate-500">{new Date(q.created_at).toLocaleDateString()}</TableCell>
                    </TableRow>
                  ))
                )}
              </tbody>
            </DataTable>
          </div>
        </>
      )}
    </div>
  );
}
