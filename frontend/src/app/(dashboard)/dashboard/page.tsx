"use client";

import React from "react";
import Link from "next/link";
import {
  TrendingUp,
  FileSpreadsheet,
  AlertTriangle,
  Clock,
  Sparkles,
  ArrowRight,
  FileText,
  Users,
  CheckCircle,
  Building,
  Laptop,
  CheckSquare
} from "lucide-react";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  Button,
  StatusBadge,
  PageHeader,
  DataTable,
  TableHead,
  TableRow,
  TableHeader,
  TableCell,
  MetricCard
} from "@/components/ui";

export default function DashboardHome() {
  const recentQuotes = [
    {
      id: 1,
      quote_number: "Q-2026-0001",
      title: "Acme IT Infrastructure Upgrade",
      customer: "Acme Corporation",
      amount: "$14,342.00",
      status: "DRAFT" as const,
      date: "Sep 23, 2026",
    },
    {
      id: 2,
      quote_number: "Q-2026-0002",
      title: "Cloud Infrastructure Migration",
      customer: "Global Logistics Tech",
      amount: "$48,920.00",
      status: "SUBMITTED" as const,
      date: "Sep 22, 2026",
    },
    {
      id: 3,
      quote_number: "Q-2026-0003",
      title: "Enterprise Cybersecurity Bundle",
      customer: "Horizon Financial",
      amount: "$29,400.00",
      status: "APPROVED" as const,
      date: "Sep 20, 2026",
    },
    {
      id: 4,
      quote_number: "Q-2026-0004",
      title: "Hardware Refresh Phase 2",
      customer: "TechCorp Systems",
      amount: "$35,788.00",
      status: "APPROVED" as const,
      date: "Sep 18, 2026",
    },
  ];

  return (
    <div className="space-y-6">
      {/* ─── Page Header ────────────────────────────────────────── */}
      <div data-demo="dashboard-header">
      <PageHeader
        title="Workspace Overview"
        description="Monitor your quote pipeline, pending approval queues, and CRM sync operations."
        actions={
          <Link href="/quotes">
            <Button variant="primary" icon={<ArrowRight size={14} />} iconPosition="right">
              Create Quote
            </Button>
          </Link>
        }
      />
      </div>

      {/* ─── Top 4 KPI Cards ────────────────────────────────────── */}
      <div data-demo="dashboard-kpis" className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Total Quotation Revenue"
          value="$128,450.00"
          subtext="+14.2% vs last month"
          icon={<TrendingUp size={18} className="text-blue-600" />}
          trend={{ value: "+14.2%", isPositive: true }}
        />
        <MetricCard
          title="Active Quotes Pipeline"
          value="12 Quotes"
          subtext="3 Drafts, 9 in Review"
          icon={<FileText size={18} className="text-teal-600" />}
        />
        <MetricCard
          title="Pending Approvals"
          value="2 Pending"
          subtext="Requires executive sign-off"
          icon={<AlertTriangle size={18} className="text-amber-600" />}
          trend={{ value: "Action Req", isPositive: false }}
        />
        <MetricCard
          title="Win Rate / Conversion"
          value="68.5%"
          subtext="$340k pipeline value"
          icon={<CheckCircle size={18} className="text-emerald-600" />}
          trend={{ value: "+4.1%", isPositive: true }}
        />
      </div>

      {/* ─── 2-Column Dashboard Layout ───────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column (8 cols): Pipeline & Recent Quotes */}
        <div className="lg:col-span-8 space-y-6">
          {/* Quote Pipeline Visualizer */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm">Quotation Pipeline Stages</CardTitle>
              <CardDescription>Value distribution across active quote lifecycles</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                <div className="flex h-3 rounded-full overflow-hidden bg-slate-100">
                  <div style={{ width: "25%" }} className="bg-slate-400" title="Draft (25%)" />
                  <div style={{ width: "35%" }} className="bg-blue-600" title="Submitted (35%)" />
                  <div style={{ width: "30%" }} className="bg-emerald-600" title="Approved (30%)" />
                  <div style={{ width: "10%" }} className="bg-amber-500" title="In Negotiation (10%)" />
                </div>
                <div className="flex items-center justify-between text-xs text-slate-500 font-medium">
                  <span className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-slate-400" /> Draft: $32.1k
                  </span>
                  <span className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-blue-600" /> Submitted: $45.0k
                  </span>
                  <span className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-emerald-600" /> Approved: $38.5k
                  </span>
                  <span className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-amber-500" /> In Review: $12.8k
                  </span>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Recent Quotes Table */}
          <Card data-demo="dashboard-quotes">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between w-full">
                <div>
                  <CardTitle className="text-sm">Recent Quotes</CardTitle>
                  <CardDescription>Latest quotes generated across your enterprise team</CardDescription>
                </div>
                <Link href="/quotes">
                  <Button variant="ghost" size="sm">
                    View All
                  </Button>
                </Link>
              </div>
            </CardHeader>
            <CardContent className="p-0">
              <DataTable className="border-0 rounded-none">
                <TableHead>
                  <TableRow>
                    <TableHeader>Quote #</TableHeader>
                    <TableHeader>Title</TableHeader>
                    <TableHeader>Customer</TableHeader>
                    <TableHeader>Amount</TableHeader>
                    <TableHeader>Status</TableHeader>
                    <TableHeader>Date</TableHeader>
                  </TableRow>
                </TableHead>
                <tbody>
                  {recentQuotes.map((q) => (
                    <TableRow key={q.id} data-demo={q.quote_number === "Q-2026-0001" ? "quote-q-2026-0001" : undefined}>
                      <TableCell className="font-semibold text-slate-900 font-mono text-xs">
                        {q.quote_number}
                      </TableCell>
                      <TableCell className="font-medium text-slate-800">{q.title}</TableCell>
                      <TableCell className="text-slate-600">{q.customer}</TableCell>
                      <TableCell className="font-bold text-slate-900">{q.amount}</TableCell>
                      <TableCell>
                        <StatusBadge status={q.status} />
                      </TableCell>
                      <TableCell className="text-slate-400 text-xs">{q.date}</TableCell>
                    </TableRow>
                  ))}
                </tbody>
              </DataTable>
            </CardContent>
          </Card>
        </div>

        {/* Right Column (4 cols): Approvals, Copilot, & Activity */}
        <div className="lg:col-span-4 space-y-6">
          {/* Pending Approvals Card */}
          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between w-full">
                <div className="flex items-center gap-2">
                  <CheckSquare size={16} className="text-amber-600" />
                  <CardTitle className="text-sm">Pending Sign-off</CardTitle>
                </div>
                <Link href="/approvals">
                  <Button variant="ghost" size="sm">
                    Queue (2)
                  </Button>
                </Link>
              </div>
            </CardHeader>
            <CardContent className="space-y-3 pt-1 text-xs">
              <div className="p-3 bg-slate-50 border border-slate-200/80 rounded-xl space-y-2">
                <div className="flex justify-between items-start">
                  <span className="font-semibold text-slate-900 font-mono">Q-2026-0001</span>
                  <span className="font-bold text-slate-900">$14,342.00</span>
                </div>
                <p className="text-[11px] text-slate-500">Acme Corporation • 10% override</p>
                <div className="flex gap-2 pt-1">
                  <Link href="/approvals" className="w-full">
                    <Button variant="primary" size="sm" className="w-full text-[11px] py-1">
                      Review Quote
                    </Button>
                  </Link>
                </div>
              </div>

              <div className="p-3 bg-slate-50 border border-slate-200/80 rounded-xl space-y-2">
                <div className="flex justify-between items-start">
                  <span className="font-semibold text-slate-900 font-mono">Q-2026-0004</span>
                  <span className="font-bold text-slate-900">$48,920.00</span>
                </div>
                <p className="text-[11px] text-slate-500">Global Logistics • 18.5% override</p>
                <div className="flex gap-2 pt-1">
                  <Link href="/approvals" className="w-full">
                    <Button variant="secondary" size="sm" className="w-full text-[11px] py-1">
                      Review Quote
                    </Button>
                  </Link>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* AI Copilot Suggestion Card */}
          <div className="p-5 bg-gradient-to-br from-teal-50/80 via-white to-teal-50/40 border border-teal-200/80 rounded-xl shadow-2xs space-y-2.5">
            <div className="flex items-center gap-2 text-teal-800 font-bold text-xs">
              <Sparkles size={15} className="text-teal-600" />
              <span>Gemini Copilot Suggestion</span>
            </div>
            <h4 className="text-xs font-bold text-slate-900">
              Optimal Margin Opportunity on Acme Corp
            </h4>
            <p className="text-xs text-slate-600 leading-relaxed">
              Based on historical win rates for Technology accounts, bundling 3-Year ProSupport with the Dell Latitude 7440 increases close probability by 22% while boosting margin by +4.8%.
            </p>
            <div className="pt-1">
              <Link href="/quotes">
                <Button variant="primary" size="sm">
                  Apply in Quote Builder
                </Button>
              </Link>
            </div>
          </div>

          {/* Recent Activity Card */}
          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center gap-2">
                <Clock size={15} className="text-slate-500" />
                <CardTitle className="text-sm">Recent Activity</CardTitle>
              </div>
            </CardHeader>
            <CardContent className="space-y-3.5 pt-1 text-xs">
              <div className="flex items-start gap-3">
                <div className="w-7 h-7 rounded-lg bg-blue-50 border border-blue-100 flex items-center justify-center text-blue-600 shrink-0 mt-0.5">
                  <Laptop size={13} />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-semibold text-slate-800 leading-tight">Quote Q-2026-0001 edited</p>
                  <p className="text-[11px] text-slate-500">10 units Latitude 7440</p>
                </div>
                <span className="text-[10px] text-slate-400">2m ago</span>
              </div>

              <div className="flex items-start gap-3">
                <div className="w-7 h-7 rounded-lg bg-emerald-50 border border-emerald-100 flex items-center justify-center text-emerald-600 shrink-0 mt-0.5">
                  <Building size={13} />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-semibold text-slate-800 leading-tight">New customer onboarded</p>
                  <p className="text-[11px] text-slate-500">Acme Corporation</p>
                </div>
                <span className="text-[10px] text-slate-400">15m ago</span>
              </div>

              <div className="flex items-start gap-3">
                <div className="w-7 h-7 rounded-lg bg-teal-50 border border-teal-100 flex items-center justify-center text-teal-600 shrink-0 mt-0.5">
                  <CheckCircle size={13} />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-semibold text-slate-800 leading-tight">Quote Q-2026-0003 approved</p>
                  <p className="text-[11px] text-slate-500">Horizon Financial ($29,400)</p>
                </div>
                <span className="text-[10px] text-slate-400">1h ago</span>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
