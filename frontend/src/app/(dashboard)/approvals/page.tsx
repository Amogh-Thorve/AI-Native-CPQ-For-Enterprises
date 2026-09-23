"use client";

import React, { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  CheckSquare,
  Clock,
  Filter,
  CheckCircle2,
  XCircle,
  ShieldAlert,
  ArrowRight,
  TrendingUp,
  User,
  Check,
  X
} from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import { useDemoTour } from "@/components/demo/DemoTourProvider";
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
  Tabs
} from "@/components/ui";

interface ApprovalItem {
  id: number;
  quote_number: string;
  customer_name: string;
  amount: string;
  discount_percentage: string;
  margin_percentage: string;
  requested_by: string;
  requested_role: string;
  status: "PENDING" | "APPROVED" | "REJECTED";
  submitted_date: string;
  reason: string;
}

export default function ApprovalsPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const { isActive: isDemoActive, flags: demoFlags, mockApprovals } = useDemoTour();
  const [activeTab, setActiveTab] = useState<string>("pending");

  // Approval queue items
  const [approvalItems, setApprovalItems] = useState<ApprovalItem[]>([
    {
      id: 1,
      quote_number: "Q-2026-0001",
      customer_name: "Acme Corporation",
      amount: "$14,342.00",
      discount_percentage: "10.0%",
      margin_percentage: "32.5%",
      requested_by: "Sarah Johnson",
      requested_role: "Sales Rep",
      status: "PENDING",
      submitted_date: "2026-09-23 14:30",
      reason: "Volume Hardware & Multi-seat License Discount override",
    },
    {
      id: 2,
      quote_number: "Q-2026-0004",
      customer_name: "Global Logistics Tech",
      amount: "$48,920.00",
      discount_percentage: "18.5%",
      margin_percentage: "26.1%",
      requested_by: "Michael Chang",
      requested_role: "Account Executive",
      status: "PENDING",
      submitted_date: "2026-09-22 17:15",
      reason: "Competitive displacement vs Legacy Oracle CPQ",
    },
  ]);

  const handleApprove = (id: number) => {
    if (isDemoActive) return;
    setApprovalItems((prev) =>
      prev.map((item) => (item.id === id ? { ...item, status: "APPROVED" } : item))
    );
    alert("Quote approved successfully! Notifications dispatched to sales rep.");
  };

  const handleReject = (id: number) => {
    if (isDemoActive) return;
    setApprovalItems((prev) =>
      prev.map((item) => (item.id === id ? { ...item, status: "REJECTED" } : item))
    );
    alert("Quote rejected with margin violation notice.");
  };

  const sourceItems = isDemoActive ? mockApprovals : approvalItems;
  const pendingItems = sourceItems.filter((i) => i.status === "PENDING");
  const historyItems = sourceItems.filter((i) => i.status !== "PENDING");

  useEffect(() => {
    if (isDemoActive) {
      setActiveTab(demoFlags.approvalsTab);
    }
  }, [isDemoActive, demoFlags.approvalsTab]);

  const tabs = [
    { id: "pending", label: "Pending Review", count: pendingItems.length },
    { id: "history", label: "Completed History", count: historyItems.length },
  ];

  return (
    <div className="space-y-6">
      {/* ─── Page Header ────────────────────────────────────────── */}
      <div data-demo="approvals-header">
      <PageHeader
        title="Approvals"
        description="Review, sign off on, or reject quotes flagged for discount overrides or low margins."
      />
      </div>

      {/* ─── Tabs ───────────────────────────────────────────────── */}
      <div className="bg-white px-4 border border-slate-200/80 rounded-xl shadow-xs">
        <Tabs tabs={tabs} activeTab={activeTab} onChange={setActiveTab} />
      </div>

      {/* ─── Approvals Table ────────────────────────────────────── */}
      <Card data-demo="approvals-table">
        <DataTable className="border-0 rounded-none">
          <TableHead>
            <TableRow>
              <TableHeader>Quote</TableHeader>
              <TableHeader>Customer</TableHeader>
              <TableHeader>Amount</TableHeader>
              <TableHeader>Discount</TableHeader>
              <TableHeader>Margin</TableHeader>
              <TableHeader>Requested By</TableHeader>
              <TableHeader>Status</TableHeader>
              <TableHeader>Submitted</TableHeader>
              <TableHeader className="text-right">Actions</TableHeader>
            </TableRow>
          </TableHead>
          <tbody>
            {(activeTab === "pending" ? pendingItems : historyItems).length === 0 ? (
              <TableRow>
                <TableCell colSpan={9} className="text-center py-12 text-slate-500">
                  <CheckSquare size={36} className="mx-auto text-slate-300 mb-2" />
                  <p className="font-semibold text-slate-700">Approval queue is clear</p>
                  <p className="text-[11px] text-slate-400 mt-1">
                    No discount overrides or threshold violations currently require your sign-off.
                  </p>
                </TableCell>
              </TableRow>
            ) : (
              (activeTab === "pending" ? pendingItems : historyItems).map((item) => (
                <TableRow key={item.id} data-demo={item.quote_number === "Q-2026-0001" ? "approval-acme" : undefined}>
                  <TableCell className="font-semibold text-slate-900 font-mono text-xs">
                    {item.quote_number}
                  </TableCell>
                  <TableCell className="font-medium text-slate-800">{item.customer_name}</TableCell>
                  <TableCell className="font-bold text-slate-900">{item.amount}</TableCell>
                  <TableCell>
                    <span className="font-semibold text-amber-700 bg-amber-50 px-2 py-0.5 rounded-full text-xs border border-amber-200">
                      {item.discount_percentage}
                    </span>
                  </TableCell>
                  <TableCell>
                    <span className="font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full text-xs border border-emerald-200">
                      {item.margin_percentage}
                    </span>
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <div className="w-6 h-6 rounded-full bg-slate-200 text-slate-700 flex items-center justify-center text-[10px] font-bold">
                        {item.requested_by.slice(0, 2).toUpperCase()}
                      </div>
                      <div>
                        <div className="text-xs font-semibold text-slate-900">{item.requested_by}</div>
                        <div className="text-[10px] text-slate-400">{item.requested_role}</div>
                      </div>
                    </div>
                  </TableCell>
                  <TableCell>
                    <StatusBadge status={item.status} />
                  </TableCell>
                  <TableCell className="text-slate-500 text-xs">{item.submitted_date}</TableCell>
                  <TableCell className="text-right">
                    {item.status === "PENDING" ? (
                      <div className="flex items-center justify-end gap-1.5">
                        <Button
                          variant="success"
                          size="sm"
                          icon={<Check size={13} />}
                          onClick={() => handleApprove(item.id)}
                        >
                          Approve
                        </Button>
                        <Button
                          variant="danger"
                          size="sm"
                          icon={<X size={13} />}
                          onClick={() => handleReject(item.id)}
                        >
                          Reject
                        </Button>
                      </div>
                    ) : (
                      <span className="text-xs text-slate-400 font-medium">Completed</span>
                    )}
                  </TableCell>
                </TableRow>
              ))
            )}
          </tbody>
        </DataTable>
      </Card>
    </div>
  );
}
