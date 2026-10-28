"use client";

import React, { useState, useEffect, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  CheckSquare,
  Clock,
  CheckCircle2,
  XCircle,
  ShieldAlert,
  ArrowRight,
  TrendingUp,
  User,
  Check,
  X,
  Eye,
  Sliders,
  DollarSign,
  AlertTriangle,
  FileText,
  Search,
  Building,
  RefreshCw
} from "lucide-react";
import { api } from "@/lib/api";
import { DealInsightsCard } from "../quotes/ai-panels";
import { useAuth } from "@/hooks/useAuth";
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
  Tabs,
  Modal,
  MetricCard
} from "@/components/ui";

export interface ApprovalQuoteItem {
  id: number;
  product_name?: string;
  sku?: string;
  quantity: number;
  unit_price: string;
  discount_percentage: string;
  discount_amount: string;
  total_price: string;
  margin_percentage?: string;
}

export interface ApprovalPolicyItem {
  id: number;
  name: string;
  discount_threshold: number;
  role_required: string;
  is_active: boolean;
}

export interface ApprovalItem {
  id: number;
  quote_id?: number;
  quote_number: string;
  customer_name: string;
  amount: string;
  subtotal?: string;
  discount_percentage: string;
  discount_amount?: string;
  margin_percentage: string;
  requested_by: string;
  requested_role: string;
  status: "PENDING" | "APPROVED" | "REJECTED";
  submitted_date: string;
  reason: string;
  comments?: string;
  policy?: ApprovalPolicyItem;
  items?: ApprovalQuoteItem[];
}

export default function ApprovalsPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<string>("pending");
  const [searchQuery, setSearchQuery] = useState("");

  // Modals state
  const [selectedReviewItem, setSelectedReviewItem] = useState<ApprovalItem | null>(null);
  const [rejectingItem, setRejectingItem] = useState<ApprovalItem | null>(null);
  const [reviewComments, setReviewComments] = useState("");
  const [rejectionComments, setRejectionComments] = useState("");
  const [isPoliciesModalOpen, setIsPoliciesModalOpen] = useState(false);
  const [toastMessage, setToastMessage] = useState<{ text: string; type: "success" | "error" } | null>(null);


  // Live Query from backend
  const { data: dbRequests, isLoading: isLoadingRequests, refetch: refetchRequests } = useQuery<ApprovalItem[]>({
    queryKey: ["approval-requests"],
    queryFn: () => api.get<ApprovalItem[]>("/approvals/requests"),
    retry: 1,
  });

  // Query active policies
  const { data: policiesData } = useQuery<ApprovalPolicyItem[]>({
    queryKey: ["approval-policies"],
    queryFn: () => api.get<ApprovalPolicyItem[]>("/approvals/policies"),
    retry: 1,
  });

  // Decide Mutation
  const decideMutation = useMutation({
    mutationFn: ({ id, status, comments }: { id: number; status: "APPROVED" | "REJECTED"; comments?: string }) =>
      api.post<ApprovalItem>(`/approvals/requests/${id}/decide`, { status, comments }),
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["approval-requests"] });
      queryClient.invalidateQueries({ queryKey: ["quotes"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard-stats"] });

      const actionText = variables.status === "APPROVED" ? "approved" : "rejected";
      showToast(`Quote request ${actionText} successfully. Parent quote updated.`, "success");
      setSelectedReviewItem(null);
      setRejectingItem(null);
      setReviewComments("");
      setRejectionComments("");
    },
    onError: (err: any) => {
      showToast(err?.detail || "Failed to submit approval decision.", "error");
    },
  });

  const showToast = (text: string, type: "success" | "error") => {
    setToastMessage({ text, type });
    setTimeout(() => setToastMessage(null), 4500);
  };

  const handleApprove = (id: number, comments?: string) => {
    decideMutation.mutate({ id, status: "APPROVED", comments: comments || reviewComments });
  };

  const handleOpenReject = (item: ApprovalItem) => {
    setRejectingItem(item);
    setRejectionComments("");
  };

  const handleConfirmReject = () => {
    if (!rejectingItem) return;
    decideMutation.mutate({
      id: rejectingItem.id,
      status: "REJECTED",
      comments: rejectionComments || "Quote discount exceeds approved threshold.",
    });
  };

  // Synchronize items source
  const sourceItems: ApprovalItem[] = useMemo(() => dbRequests ?? [], [dbRequests]);

  const filteredItems = useMemo(() => {
    return sourceItems.filter((item) => {
      const matchSearch =
        searchQuery === "" ||
        item.quote_number.toLowerCase().includes(searchQuery.toLowerCase()) ||
        item.customer_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        item.requested_by.toLowerCase().includes(searchQuery.toLowerCase());
      return matchSearch;
    });
  }, [sourceItems, searchQuery]);

  const pendingItems = filteredItems.filter((i) => i.status === "PENDING");
  const historyItems = filteredItems.filter((i) => i.status !== "PENDING");

  // Financial aggregates for metric cards
  const pendingTotalValue = useMemo(() => {
    return pendingItems.reduce((acc, curr) => {
      const num = Number(curr.amount.replace(/[^0-9.-]+/g, "")) || 0;
      return acc + num;
    }, 0);
  }, [pendingItems]);

  const approvedTotalValue = useMemo(() => {
    return filteredItems
      .filter((i) => i.status === "APPROVED")
      .reduce((acc, curr) => {
        const num = Number(curr.amount.replace(/[^0-9.-]+/g, "")) || 0;
        return acc + num;
      }, 0);
  }, [filteredItems]);

  const tabs = [
    { id: "pending", label: "Pending Review", count: pendingItems.length },
    { id: "history", label: "Completed History", count: historyItems.length },
  ];

  return (
    <div className="space-y-6">
      {/* ─── Notification Toast ──────────────────────────────────── */}
      {toastMessage && (
        <div
          className={`fixed top-5 right-5 z-50 flex items-center gap-2.5 px-4 py-3 rounded-xl shadow-lg border text-sm font-medium animate-in fade-in slide-in-from-top-2 ${
            toastMessage.type === "success"
              ? "bg-emerald-50 text-emerald-800 border-emerald-200"
              : "bg-rose-50 text-rose-800 border-rose-200"
          }`}
        >
          {toastMessage.type === "success" ? (
            <CheckCircle2 size={18} className="text-emerald-600" />
          ) : (
            <AlertTriangle size={18} className="text-rose-600" />
          )}
          <span>{toastMessage.text}</span>
          <button
            onClick={() => setToastMessage(null)}
            className="ml-2 text-slate-400 hover:text-slate-600"
          >
            <X size={14} />
          </button>
        </div>
      )}

      {/* ─── Page Header ────────────────────────────────────────── */}
      <div>
        <PageHeader
          title="Approvals"
          description="Review, sign off on, or reject quotes flagged for discount overrides or low margins."
          actions={
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                icon={<Sliders size={14} />}
                onClick={() => setIsPoliciesModalOpen(true)}
              >
                Governance Policies
              </Button>
              <Button
                variant="outline"
                size="sm"
                icon={<RefreshCw size={14} className={isLoadingRequests ? "animate-spin" : ""} />}
                onClick={() => refetchRequests()}
              >
                Refresh
              </Button>
            </div>
          }
        />
      </div>

      {/* ─── Executive Summary KPI Cards ────────────────────────── */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <MetricCard
          title="Pending Queue Value"
          value={`$${pendingTotalValue.toLocaleString("en-US", { minimumFractionDigits: 2 })}`}
          subtext={`${pendingItems.length} quotes requiring executive authorization`}
          icon={<Clock size={16} className="text-amber-600" />}
        />
        <MetricCard
          title="Authorized Value"
          value={`$${approvedTotalValue.toLocaleString("en-US", { minimumFractionDigits: 2 })}`}
          subtext="Total revenue released from approval reviews"
          icon={<CheckCircle2 size={16} className="text-emerald-600" />}
        />
        <MetricCard
          title="Active Routing Rules"
          value={policiesData?.length ? `${policiesData.length} Policies` : "3 Rules Active"}
          subtext="Thresholds: 10% Hardware, 15% Margin, 20% Board"
          icon={<ShieldAlert size={16} className="text-blue-600" />}
        />
      </div>

      {/* ─── Tabs & Filter Controls ─────────────────────────────── */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 bg-white px-4 py-2 border border-slate-200/80 rounded-xl shadow-xs">
        <Tabs tabs={tabs} activeTab={activeTab} onChange={setActiveTab} />
        <div className="relative max-w-xs w-full">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="Search by quote, account, rep..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-3 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-lg text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-emerald-500 focus:bg-white transition-all"
          />
        </div>
      </div>

      {/* ─── Approvals Table ────────────────────────────────────── */}
      <Card>
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
                <TableCell colSpan={9} className="text-center py-16 text-slate-500">
                  <CheckSquare size={40} className="mx-auto text-slate-300 mb-2.5" />
                  <p className="font-semibold text-slate-800 text-sm">
                    {activeTab === "pending" ? "Approval queue is clear" : "No completed approvals found"}
                  </p>
                  <p className="text-xs text-slate-400 mt-1 max-w-md mx-auto">
                    {activeTab === "pending"
                      ? "No discount overrides or threshold violations currently require your sign-off."
                      : "Quotes previously evaluated will appear in this history audit log."}
                  </p>
                </TableCell>
              </TableRow>
            ) : (
              (activeTab === "pending" ? pendingItems : historyItems).map((item) => (
                <TableRow
                  key={item.id}
                 
                  className="hover:bg-slate-50/80 transition-colors"
                >
                  <TableCell className="font-semibold text-slate-900 font-mono text-xs">
                    <button
                      onClick={() => setSelectedReviewItem(item)}
                      className="text-emerald-700 hover:text-emerald-800 hover:underline flex items-center gap-1 font-bold"
                    >
                      {item.quote_number}
                    </button>
                  </TableCell>
                  <TableCell className="font-medium text-slate-800">
                    <div className="flex items-center gap-1.5">
                      <Building size={13} className="text-slate-400" />
                      <span>{item.customer_name}</span>
                    </div>
                  </TableCell>
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
                          variant="outline"
                          size="sm"
                          icon={<Eye size={12} />}
                          onClick={() => setSelectedReviewItem(item)}
                        >
                          Review
                        </Button>
                        <Button
                          variant="success"
                          size="sm"
                          icon={<Check size={13} />}
                          onClick={() => handleApprove(item.id)}
                          disabled={decideMutation.isPending}
                        >
                          Approve
                        </Button>
                        <Button
                          variant="danger"
                          size="sm"
                          icon={<X size={13} />}
                          onClick={() => handleOpenReject(item)}
                          disabled={decideMutation.isPending}
                        >
                          Reject
                        </Button>
                      </div>
                    ) : (
                      <div className="flex items-center justify-end gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          icon={<Eye size={12} />}
                          onClick={() => setSelectedReviewItem(item)}
                        >
                          Details
                        </Button>
                        <span className="text-xs text-slate-400 font-medium">Decided</span>
                      </div>
                    )}
                  </TableCell>
                </TableRow>
              ))
            )}
          </tbody>
        </DataTable>
      </Card>

      {/* ─── Quote Detailed Review & Sign-Off Modal ─────────────────── */}
      {selectedReviewItem && (
        <Modal
          isOpen={!!selectedReviewItem}
          onClose={() => setSelectedReviewItem(null)}
          title={`Review Quote: ${selectedReviewItem.quote_number}`}
          description={`Customer: ${selectedReviewItem.customer_name} • Requested by ${selectedReviewItem.requested_by}`}
          maxWidth="3xl"
          footer={
            selectedReviewItem.status === "PENDING" ? (
              <>
                <Button variant="outline" size="sm" onClick={() => setSelectedReviewItem(null)}>
                  Close
                </Button>
                <Button
                  variant="danger"
                  size="sm"
                  icon={<X size={14} />}
                  onClick={() => handleOpenReject(selectedReviewItem)}
                  disabled={decideMutation.isPending}
                >
                  Reject Quote
                </Button>
                <Button
                  variant="success"
                  size="sm"
                  icon={<Check size={14} />}
                  onClick={() => handleApprove(selectedReviewItem.id)}
                  disabled={decideMutation.isPending}
                >
                  Approve Quote
                </Button>
              </>
            ) : (
              <Button variant="outline" size="sm" onClick={() => setSelectedReviewItem(null)}>
                Close
              </Button>
            )
          }
        >
          <div className="space-y-5">
            {selectedReviewItem.quote_id != null && (
              <DealInsightsCard quoteId={selectedReviewItem.quote_id} version={String(selectedReviewItem.id)} />
            )}
            {/* Policy Trigger Banner */}
            <div className="bg-amber-50/80 border border-amber-200/90 rounded-xl p-3.5 flex items-start gap-3">
              <ShieldAlert size={18} className="text-amber-600 shrink-0 mt-0.5" />
              <div className="space-y-0.5 text-xs text-amber-900">
                <span className="font-semibold block text-amber-950">
                  Routing Trigger: {selectedReviewItem.reason}
                </span>
                <p className="text-amber-800 leading-relaxed">
                  Discount rate of {selectedReviewItem.discount_percentage} requires sign-off from{" "}
                  <strong>{selectedReviewItem.requested_role || "Executive leadership"}</strong> according to enterprise governance policies.
                </p>
              </div>
            </div>

            {/* Financial Overview Cards */}
            <div className="grid grid-cols-4 gap-3">
              <div className="bg-slate-50 border border-slate-200/70 rounded-lg p-3">
                <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block">
                  Quote Total
                </span>
                <span className="text-base font-bold text-slate-900 block mt-0.5">
                  {selectedReviewItem.amount}
                </span>
              </div>
              <div className="bg-slate-50 border border-slate-200/70 rounded-lg p-3">
                <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block">
                  Subtotal
                </span>
                <span className="text-base font-bold text-slate-900 block mt-0.5">
                  {selectedReviewItem.subtotal || selectedReviewItem.amount}
                </span>
              </div>
              <div className="bg-amber-50/50 border border-amber-200/60 rounded-lg p-3">
                <span className="text-[11px] font-semibold text-amber-700 uppercase tracking-wider block">
                  Total Discount
                </span>
                <span className="text-base font-bold text-amber-800 block mt-0.5">
                  {selectedReviewItem.discount_percentage}
                </span>
              </div>
              <div className="bg-emerald-50/50 border border-emerald-200/60 rounded-lg p-3">
                <span className="text-[11px] font-semibold text-emerald-700 uppercase tracking-wider block">
                  Gross Margin
                </span>
                <span className="text-base font-bold text-emerald-800 block mt-0.5">
                  {selectedReviewItem.margin_percentage}
                </span>
              </div>
            </div>

            {/* Line Items Breakdown */}
            <div>
              <h4 className="text-xs font-bold text-slate-900 uppercase tracking-wider mb-2 flex items-center justify-between">
                <span>Quotation Line Items</span>
                <span className="text-[11px] font-normal text-slate-500">
                  {selectedReviewItem.items?.length || 0} product(s)
                </span>
              </h4>
              <div className="border border-slate-200 rounded-lg overflow-hidden text-xs">
                <table className="w-full text-left">
                  <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 font-semibold">
                    <tr>
                      <th className="py-2 px-3">Product / SKU</th>
                      <th className="py-2 px-3 text-center">Qty</th>
                      <th className="py-2 px-3 text-right">Unit Price</th>
                      <th className="py-2 px-3 text-center">Line Discount</th>
                      <th className="py-2 px-3 text-center">Margin</th>
                      <th className="py-2 px-3 text-right">Total</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {selectedReviewItem.items && selectedReviewItem.items.length > 0 ? (
                      selectedReviewItem.items.map((line) => (
                        <tr key={line.id} className="hover:bg-slate-50/60">
                          <td className="py-2 px-3">
                            <div className="font-semibold text-slate-800">{line.product_name}</div>
                            <div className="text-[10px] text-slate-400 font-mono">{line.sku}</div>
                          </td>
                          <td className="py-2 px-3 text-center font-medium text-slate-700">
                            {line.quantity}
                          </td>
                          <td className="py-2 px-3 text-right text-slate-600 font-medium">
                            {line.unit_price}
                          </td>
                          <td className="py-2 px-3 text-center">
                            <span
                              className={`px-1.5 py-0.5 rounded text-[11px] font-semibold ${
                                line.discount_percentage !== "0.0%"
                                  ? "bg-amber-100 text-amber-800"
                                  : "bg-slate-100 text-slate-500"
                              }`}
                            >
                              {line.discount_percentage}
                            </span>
                          </td>
                          <td className="py-2 px-3 text-center font-medium text-emerald-700">
                            {line.margin_percentage || "N/A"}
                          </td>
                          <td className="py-2 px-3 text-right font-bold text-slate-900">
                            {line.total_price}
                          </td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan={6} className="py-4 text-center text-slate-400 italic">
                          Standard bundle pricing applied across items.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Review Notes / Decision comments */}
            {selectedReviewItem.status === "PENDING" && (
              <div>
                <label className="text-xs font-semibold text-slate-700 block mb-1">
                  Executive / Sign-off Comments (Optional)
                </label>
                <textarea
                  rows={2}
                  value={reviewComments}
                  onChange={(e) => setReviewComments(e.target.value)}
                  placeholder="Add approval comments or special contractual instructions for sales operations..."
                  className="w-full text-xs p-2.5 bg-slate-50 border border-slate-200 rounded-lg text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-emerald-500 focus:bg-white transition-all"
                />
              </div>
            )}

            {/* Display completed comments if decided */}
            {selectedReviewItem.comments && (
              <div className="bg-slate-50 border border-slate-200 rounded-lg p-3 text-xs">
                <span className="font-semibold text-slate-700 block mb-0.5">Approver Feedback:</span>
                <p className="text-slate-600">{selectedReviewItem.comments}</p>
              </div>
            )}
          </div>
        </Modal>
      )}

      {/* ─── Rejection Reason Modal ──────────────────────────────────── */}
      {rejectingItem && (
        <Modal
          isOpen={!!rejectingItem}
          onClose={() => setRejectingItem(null)}
          title={`Reject Quote ${rejectingItem.quote_number}`}
          description={`Please provide specific feedback for ${rejectingItem.customer_name}. The quote will return to REJECTED status.`}
          maxWidth="md"
          footer={
            <>
              <Button variant="outline" size="sm" onClick={() => setRejectingItem(null)}>
                Cancel
              </Button>
              <Button
                variant="danger"
                size="sm"
                icon={<X size={14} />}
                onClick={handleConfirmReject}
                disabled={decideMutation.isPending}
              >
                Confirm Rejection
              </Button>
            </>
          }
        >
          <div className="space-y-3">
            <div className="bg-rose-50 border border-rose-200 rounded-lg p-3 text-xs text-rose-800 flex items-start gap-2.5">
              <AlertTriangle size={16} className="text-rose-600 shrink-0 mt-0.5" />
              <span>
                Rejecting this quote will require the account team to revise pricing or discount terms before resubmitting.
              </span>
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-700 block mb-1">
                Reason for Rejection *
              </label>
              <textarea
                rows={3}
                value={rejectionComments}
                onChange={(e) => setRejectionComments(e.target.value)}
                placeholder="e.g. Target margin is below acceptable threshold. Cap discount at 5% or increase license seats."
                className="w-full text-xs p-2.5 bg-slate-50 border border-slate-200 rounded-lg text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-rose-500 focus:bg-white transition-all"
              />
            </div>
          </div>
        </Modal>
      )}

      {/* ─── Governance Policies Modal ───────────────────────────────── */}
      <Modal
        isOpen={isPoliciesModalOpen}
        onClose={() => setIsPoliciesModalOpen(false)}
        title="Approval Governance Policies"
        description="Active CPQ rules enforcing discount caps and multi-level authorization workflows."
        maxWidth="lg"
        footer={
          <Button variant="outline" size="sm" onClick={() => setIsPoliciesModalOpen(false)}>
            Close
          </Button>
        }
      >
        <div className="space-y-3">
          {(policiesData && policiesData.length > 0 ? policiesData : [
            {
              id: 1,
              name: "Volume Hardware Override Threshold",
              discount_threshold: 10.0,
              role_required: "Executive",
              is_active: true,
            },
            {
              id: 2,
              name: "Competitive Displacement Margin Review",
              discount_threshold: 15.0,
              role_required: "Executive",
              is_active: true,
            },
            {
              id: 3,
              name: "Deep Discount Board Approval",
              discount_threshold: 20.0,
              role_required: "Administrator",
              is_active: true,
            },
          ]).map((policy) => (
            <div
              key={policy.id}
              className="p-3.5 border border-slate-200 rounded-xl bg-slate-50/70 flex items-start justify-between gap-3"
            >
              <div className="space-y-1 text-xs">
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-slate-900">{policy.name}</span>
                  <span className="bg-emerald-100 text-emerald-800 px-1.5 py-0.5 rounded text-[10px] font-bold">
                    ACTIVE
                  </span>
                </div>
                <p className="text-slate-500">
                  Triggered when quote discount overrides exceed{" "}
                  <strong className="text-slate-800">{policy.discount_threshold}%</strong>.
                </p>
                <div className="text-[11px] text-slate-400">
                  Required Sign-Off Role:{" "}
                  <span className="text-slate-700 font-semibold">{policy.role_required}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </Modal>
    </div>
  );
}
