"use client";

import React, { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Users,
  Search,
  Plus,
  Download,
  Upload,
  RefreshCw,
  BarChart3,
  X,
  Edit2,
  Trash2,
  Mail,
  Phone,
  Globe,
  MapPin,
  ChevronLeft,
  ChevronRight,
  PlusCircle,
  FileText,
  Calendar,
  Sparkles,
  Archive,
  RotateCcw,
  MoreHorizontal,
  Eye,
  CheckCircle,
  Building
} from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import { useDemoTour } from "@/components/demo/DemoTourProvider";
import { DEMO_ACME_ID, DEMO_CUSTOMER_LIST } from "@/lib/demoMockData";
import type {
  CustomerRead,
  CustomerCreate,
  CustomerUpdate,
  CustomerListResponse,
  ContactCreate,
  CustomerAddressCreate,
  AddressType
} from "@/types/customer";
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
  SearchBar,
  FilterSelect,
  Modal,
  Tabs
} from "@/components/ui";

export default function CustomersPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const { isActive: isDemoActive, flags: demoFlags, mockCustomers } = useDemoTour();

  // Role permissions
  const isManager = user?.role === "manager" || user?.role === "admin";
  const isExecutive = user?.role === "executive";
  const isSalesRep = user?.role === "sales_rep";
  const isAdmin = user?.role === "admin";

  const canCreate = isManager || isSalesRep;
  const canImport = isManager;
  const canExport = isManager || isExecutive;
  const canSyncSalesforce = isManager;
  const canViewAnalytics = isManager || isExecutive;
  const canAssign = isManager;

  // Page, filter, and search states
  const [page, setPage] = useState(1);
  const [pageSize] = useState(10);
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("ACTIVE");
  const [typeFilter, setTypeFilter] = useState<string>("");

  // UI Selection states
  const [selectedCustomerId, setSelectedCustomerId] = useState<number | null>(null);
  const [activeTab, setActiveTab] = useState<string>("overview");

  // Modals state
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [isAddContactModalOpen, setIsAddContactModalOpen] = useState(false);
  const [isAddAddressModalOpen, setIsAddAddressModalOpen] = useState(false);

  // Archive / Restore / Delete confirmation states
  const [archiveConfirmId, setArchiveConfirmId] = useState<number | null>(null);
  const [restoreConfirmId, setRestoreConfirmId] = useState<number | null>(null);
  const [deleteConfirmId, setDeleteConfirmId] = useState<number | null>(null);

  // Row action menu dropdown state
  const [activeMenuId, setActiveMenuId] = useState<number | null>(null);

  // Note text state
  const [noteText, setNoteText] = useState("");
  const [sessionNotes, setSessionNotes] = useState<Record<number, { id: number; text: string; date: string }[]>>({});

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedSearch(searchQuery);
      setPage(1);
    }, 300);
    return () => clearTimeout(handler);
  }, [searchQuery]);

  // Main list query
  const {
    data: liveCustomersData,
    isLoading: isLiveLoading,
    isError: isLiveError,
    error,
  } = useQuery<CustomerListResponse>({
    queryKey: ["customers", page, pageSize, debouncedSearch, statusFilter, typeFilter],
    queryFn: () => {
      const params = new URLSearchParams();
      params.append("page", page.toString());
      params.append("page_size", pageSize.toString());
      if (debouncedSearch) params.append("search", debouncedSearch);
      if (statusFilter) params.append("status", statusFilter);
      if (typeFilter) params.append("customer_type", typeFilter);
      return api.get<CustomerListResponse>(`/customers/?${params.toString()}`);
    },
    enabled: !isDemoActive,
  });

  const customersData: CustomerListResponse | undefined = isDemoActive
    ? DEMO_CUSTOMER_LIST
    : liveCustomersData;
  const isLoading = isDemoActive ? false : isLiveLoading;
  const isError = isDemoActive ? false : isLiveError;

  useEffect(() => {
    if (!isDemoActive) return;
    if (demoFlags.openCustomerRecord) {
      setSelectedCustomerId(DEMO_ACME_ID);
      setActiveTab("overview");
    } else {
      setSelectedCustomerId(null);
    }
  }, [isDemoActive, demoFlags.openCustomerRecord]);

  // Selected customer details
  const { data: liveSelectedCustomer } = useQuery<CustomerRead>({
    queryKey: ["customer", selectedCustomerId],
    queryFn: () => api.get<CustomerRead>(`/customers/${selectedCustomerId}`),
    enabled: selectedCustomerId !== null && !isDemoActive
  });

  const selectedCustomer = isDemoActive
    ? mockCustomers.find((c) => c.id === selectedCustomerId) ??
      (demoFlags.openCustomerRecord ? mockCustomers[0] : undefined)
    : liveSelectedCustomer;

  // Mutations
  const createCustomerMutation = useMutation({
    mutationFn: (data: CustomerCreate) => api.post<CustomerRead>("/customers/", data),
    onSuccess: (newCust) => {
      queryClient.invalidateQueries({ queryKey: ["customers"] });
      setIsCreateModalOpen(false);
      setSelectedCustomerId(newCust.id);
      setActiveTab("overview");
    },
    onError: (err: any) => {
      alert(err?.detail || "Failed to create customer");
    }
  });

  const updateCustomerMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: CustomerUpdate }) =>
      api.put<CustomerRead>(`/customers/${id}`, data),
    onSuccess: (updatedCust) => {
      queryClient.invalidateQueries({ queryKey: ["customers"] });
      queryClient.invalidateQueries({ queryKey: ["customer", updatedCust.id] });
      setIsEditModalOpen(false);
    },
    onError: (err: any) => {
      alert(err?.detail || "Failed to update customer");
    }
  });

  const archiveCustomerMutation = useMutation({
    mutationFn: (id: number) => api.delete(`/customers/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["customers"] });
      queryClient.invalidateQueries({ queryKey: ["customer", archiveConfirmId] });
      setArchiveConfirmId(null);
    }
  });

  const restoreCustomerMutation = useMutation({
    mutationFn: (id: number) => api.post(`/customers/${id}/restore`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["customers"] });
      queryClient.invalidateQueries({ queryKey: ["customer", restoreConfirmId] });
      setRestoreConfirmId(null);
    }
  });

  const hardDeleteCustomerMutation = useMutation({
    mutationFn: (id: number) => api.delete(`/customers/${id}/hard`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["customers"] });
      if (selectedCustomerId === deleteConfirmId) {
        setSelectedCustomerId(null);
      }
      setDeleteConfirmId(null);
    }
  });

  const addContactMutation = useMutation({
    mutationFn: ({ customerId, data }: { customerId: number; data: ContactCreate }) =>
      api.post(`/customers/${customerId}/contacts`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["customer", selectedCustomerId] });
      setIsAddContactModalOpen(false);
    }
  });

  const deleteContactMutation = useMutation({
    mutationFn: (contactId: number) => api.delete(`/contacts/${contactId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["customer", selectedCustomerId] });
    }
  });

  const addAddressMutation = useMutation({
    mutationFn: ({ customerId, data }: { customerId: number; data: CustomerAddressCreate }) =>
      api.post(`/customers/${customerId}/addresses`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["customer", selectedCustomerId] });
      setIsAddAddressModalOpen(false);
    }
  });

  const handleCreateCustomer = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (isDemoActive) return;
    const formData = new FormData(e.currentTarget);
    const data: CustomerCreate = {
      customer_number: formData.get("customer_number") as string,
      legal_name: formData.get("legal_name") as string,
      display_name: (formData.get("display_name") as string) || null,
      email: (formData.get("email") as string) || null,
      phone: (formData.get("phone") as string) || null,
      website: (formData.get("website") as string) || null,
      industry: (formData.get("industry") as string) || null,
      customer_type: (formData.get("customer_type") as any) || "BUSINESS",
      status: (formData.get("status") as any) || "PROSPECT",
      owner_id: (formData.get("owner_id") as string) || null
    };
    createCustomerMutation.mutate(data);
  };

  const handleUpdateCustomer = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!selectedCustomerId || isDemoActive) return;
    const formData = new FormData(e.currentTarget);
    const data: CustomerUpdate = {
      customer_number: formData.get("customer_number") as string,
      legal_name: formData.get("legal_name") as string,
      display_name: (formData.get("display_name") as string) || null,
      email: (formData.get("email") as string) || null,
      phone: (formData.get("phone") as string) || null,
      website: (formData.get("website") as string) || null,
      industry: (formData.get("industry") as string) || null,
      customer_type: (formData.get("customer_type") as any) || "BUSINESS",
      status: (formData.get("status") as any) || "PROSPECT",
      owner_id: (formData.get("owner_id") as string) || null
    };
    updateCustomerMutation.mutate({ id: selectedCustomerId, data });
  };

  const handleAddContact = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!selectedCustomerId || isDemoActive) return;
    const formData = new FormData(e.currentTarget);
    const data: ContactCreate = {
      first_name: formData.get("first_name") as string,
      last_name: formData.get("last_name") as string,
      email: formData.get("email") as string,
      phone: (formData.get("phone") as string) || null,
      is_primary: formData.get("is_primary") === "true"
    };
    addContactMutation.mutate({ customerId: selectedCustomerId, data });
  };

  const handleAddAddress = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!selectedCustomerId || isDemoActive) return;
    const formData = new FormData(e.currentTarget);
    const data: CustomerAddressCreate = {
      address_type: formData.get("address_type") as AddressType,
      line1: formData.get("line1") as string,
      line2: (formData.get("line2") as string) || null,
      city: formData.get("city") as string,
      state: formData.get("state") as string,
      postal_code: formData.get("postal_code") as string,
      country: formData.get("country") as string,
      is_primary: formData.get("is_primary") === "true"
    };
    addAddressMutation.mutate({ customerId: selectedCustomerId, data });
  };

  const handleAddNote = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedCustomerId || !noteText.trim()) return;
    const newNote = {
      id: Date.now(),
      text: noteText,
      date: new Date().toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })
    };
    setSessionNotes((prev) => ({
      ...prev,
      [selectedCustomerId]: [newNote, ...(prev[selectedCustomerId] || [])]
    }));
    setNoteText("");
  };

  const getAvatarInitials = (name: string) => {
    if (!name) return "??";
    return name
      .split(" ")
      .map((n) => n[0])
      .join("")
      .toUpperCase()
      .slice(0, 2);
  };

  const activeNotes = selectedCustomerId ? sessionNotes[selectedCustomerId] || [] : [];

  const customerTabs = [
    { id: "overview", label: "Overview" },
    { id: "contacts", label: "Contacts", count: selectedCustomer?.contacts?.length || 0 },
    { id: "notes", label: "Notes", count: activeNotes.length },
    { id: "quotes", label: "Quotes" },
    { id: "activity", label: "Activity" }
  ];

  return (
    <div className="space-y-6">
      {/* ─── Page Header ────────────────────────────────────────── */}
      <div data-demo="customers-header">
      <PageHeader
        title="Customers"
        description="Manage and view your customer profiles"
        actions={
          <>
            {canExport && (
              <Button
                variant="secondary"
                size="sm"
                icon={<Download size={14} />}
                onClick={() => alert("Export list (Coming Soon)")}
              >
                Export
              </Button>
            )}
            {canImport && (
              <Button
                variant="secondary"
                size="sm"
                icon={<Upload size={14} />}
                onClick={() => alert("Import Excel (Coming Soon)")}
              >
                Import Excel
              </Button>
            )}
            {canSyncSalesforce && (
              <Button
                variant="secondary"
                size="sm"
                icon={<RefreshCw size={14} />}
                onClick={() => alert("Salesforce Sync (Coming Soon)")}
              >
                Salesforce Sync
              </Button>
            )}
            {canViewAnalytics && (
              <Button
                variant="secondary"
                size="sm"
                icon={<BarChart3 size={14} />}
                onClick={() => alert("Analytics Dashboard (Coming Soon)")}
              >
                Analytics
              </Button>
            )}
            {canCreate && (
              <Button
                variant="primary"
                size="sm"
                icon={<Plus size={14} />}
                onClick={() => setIsCreateModalOpen(true)}
              >
                Add Customer
              </Button>
            )}
          </>
        }
      />
      </div>

      {/* ─── Filter Bar ─────────────────────────────────────────── */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-white p-3 rounded-xl border border-slate-200/80 shadow-xs">
        <SearchBar
          value={searchQuery}
          onChangeValue={setSearchQuery}
          placeholder="Search customers by name, email, phone..."
          className="w-full sm:w-80"
        />

        <div className="flex items-center gap-2.5 w-full sm:w-auto">
          <FilterSelect
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            label="Status"
          >
            <option value="">All Statuses</option>
            <option value="ACTIVE">Active Only</option>
            <option value="ARCHIVED">Archived Only</option>
          </FilterSelect>

          <FilterSelect
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            label="Type"
          >
            <option value="">Type: All</option>
            <option value="BUSINESS">Business</option>
            <option value="INDIVIDUAL">Individual</option>
          </FilterSelect>

          {(statusFilter || typeFilter || searchQuery) && (
            <button
              onClick={() => {
                setStatusFilter("");
                setTypeFilter("");
                setSearchQuery("");
              }}
              className="text-xs text-slate-500 hover:text-slate-800 font-medium px-2 py-1.5 transition-colors cursor-pointer"
            >
              Clear
            </button>
          )}
        </div>
      </div>

      {/* ─── Main Content Split (Table + Detail Drawer) ─────────── */}
      <div className="flex gap-6 items-start">
        {/* Left: Customers Data Table */}
        <div className={`transition-all duration-200 ${selectedCustomerId ? "w-full lg:w-7/12" : "w-full"}`}>
          <Card data-demo="customers-table">
            <DataTable className="border-0 rounded-none">
              <TableHead>
                <TableRow>
                  <TableHeader>Customer</TableHeader>
                  <TableHeader>Industry</TableHeader>
                  <TableHeader>Owner</TableHeader>
                  <TableHeader>Status</TableHeader>
                  <TableHeader>Created</TableHeader>
                  <TableHeader className="w-16 text-right">Actions</TableHeader>
                </TableRow>
              </TableHead>
              <tbody>
                {isLoading ? (
                  <TableRow>
                    <TableCell colSpan={6} className="text-center py-12 text-slate-500">
                      <RefreshCw size={18} className="animate-spin inline-block mr-2 text-blue-600" />
                      Loading customers...
                    </TableCell>
                  </TableRow>
                ) : isError ? (
                  <TableRow>
                    <TableCell colSpan={6} className="text-center py-8 text-rose-500">
                      Error loading customers: {(error as any)?.detail || "Check your network connection."}
                    </TableCell>
                  </TableRow>
                ) : !customersData || customersData.items.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} className="text-center py-12 text-slate-500">
                      No customers found. Click &quot;Add Customer&quot; to onboard one.
                    </TableCell>
                  </TableRow>
                ) : (
                  customersData.items.map((cust) => (
                    <TableRow
                      key={cust.id}
                      data-demo={
                        /acme/i.test(cust.legal_name || "") || /acme/i.test(cust.display_name || "")
                          ? "customer-acme"
                          : undefined
                      }
                      onClick={() => {
                        setSelectedCustomerId(cust.id);
                        setActiveTab("overview");
                      }}
                      className={`cursor-pointer ${selectedCustomerId === cust.id ? "bg-blue-50/60" : ""}`}
                    >
                      <TableCell>
                        <div className="flex items-center gap-3">
                          <div className="w-8 h-8 rounded-lg bg-blue-100 text-blue-700 font-bold flex items-center justify-center text-xs shrink-0">
                            {getAvatarInitials(cust.legal_name)}
                          </div>
                          <div>
                            <div className="font-semibold text-slate-900 text-xs">{cust.legal_name}</div>
                            <div className="text-[11px] text-slate-400">{cust.email || cust.customer_number || "—"}</div>
                          </div>
                        </div>
                      </TableCell>
                      <TableCell className="text-slate-600 font-medium">{cust.industry || "—"}</TableCell>
                      <TableCell>
                        <span className="inline-flex items-center gap-1.5 text-xs text-slate-600">
                          <span className="w-4 h-4 rounded-full bg-slate-100 border border-slate-300 text-slate-700 text-[9px] font-bold flex items-center justify-center">
                            {cust.owner_id ? "O" : "S"}
                          </span>
                          <span className="truncate max-w-[80px]">
                            {cust.owner_id ? cust.owner_id.slice(0, 8) : "System"}
                          </span>
                        </span>
                      </TableCell>
                      <TableCell>
                        <StatusBadge status={cust.status} />
                      </TableCell>
                      <TableCell className="text-slate-500">
                        {new Date(cust.created_at).toLocaleDateString("en-US", {
                          month: "short",
                          day: "numeric",
                          year: "numeric"
                        })}
                      </TableCell>
                      <TableCell className="text-right" onClick={(e) => e.stopPropagation()}>
                        <div className="relative inline-block text-left">
                          <button
                            onClick={() => setActiveMenuId(activeMenuId === cust.id ? null : cust.id)}
                            className="p-1 rounded hover:bg-slate-100 text-slate-400 hover:text-slate-700 transition-colors cursor-pointer"
                          >
                            <MoreHorizontal size={15} />
                          </button>

                          {activeMenuId === cust.id && (
                            <div className="absolute right-0 mt-1 w-36 bg-white border border-slate-200 rounded-lg shadow-lg z-20 py-1 text-xs text-left">
                              <button
                                onClick={() => {
                                  setSelectedCustomerId(cust.id);
                                  setActiveTab("overview");
                                  setActiveMenuId(null);
                                }}
                                className="w-full px-3 py-1.5 text-slate-700 hover:bg-slate-50 flex items-center gap-2 cursor-pointer"
                              >
                                <Eye size={12} />
                                <span>View Details</span>
                              </button>
                              {canCreate && (
                                <button
                                  onClick={() => {
                                    setSelectedCustomerId(cust.id);
                                    setIsEditModalOpen(true);
                                    setActiveMenuId(null);
                                  }}
                                  className="w-full px-3 py-1.5 text-slate-700 hover:bg-slate-50 flex items-center gap-2 cursor-pointer"
                                >
                                  <Edit2 size={12} />
                                  <span>Edit</span>
                                </button>
                              )}
                              {isManager && (
                                <>
                                  {cust.status !== "ARCHIVED" ? (
                                    <button
                                      onClick={() => {
                                        setArchiveConfirmId(cust.id);
                                        setActiveMenuId(null);
                                      }}
                                      className="w-full px-3 py-1.5 text-amber-600 hover:bg-amber-50 flex items-center gap-2 cursor-pointer"
                                    >
                                      <Archive size={12} />
                                      <span>Archive</span>
                                    </button>
                                  ) : (
                                    <button
                                      onClick={() => {
                                        setRestoreConfirmId(cust.id);
                                        setActiveMenuId(null);
                                      }}
                                      className="w-full px-3 py-1.5 text-emerald-600 hover:bg-emerald-50 flex items-center gap-2 cursor-pointer"
                                    >
                                      <RotateCcw size={12} />
                                      <span>Restore</span>
                                    </button>
                                  )}
                                </>
                              )}
                              {isAdmin && (
                                <button
                                  onClick={() => {
                                    setDeleteConfirmId(cust.id);
                                    setActiveMenuId(null);
                                  }}
                                  className="w-full px-3 py-1.5 text-rose-600 hover:bg-rose-50 flex items-center gap-2 cursor-pointer border-t border-slate-100"
                                >
                                  <Trash2 size={12} />
                                  <span>Delete</span>
                                </button>
                              )}
                            </div>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </tbody>
            </DataTable>

            {/* Pagination Controls */}
            {customersData && customersData.total > 0 && (
              <div className="border-t border-slate-100 p-3.5 flex items-center justify-between text-xs text-slate-500 bg-slate-50/50 rounded-b-xl">
                <div>
                  Showing <span className="font-semibold text-slate-700">{(page - 1) * pageSize + 1}</span> to{" "}
                  <span className="font-semibold text-slate-700">
                    {Math.min(page * pageSize, customersData.total)}
                  </span>{" "}
                  of <span className="font-semibold text-slate-700">{customersData.total}</span> customers
                </div>
                <div className="flex items-center gap-1.5">
                  <button
                    onClick={() => setPage((p) => Math.max(p - 1, 1))}
                    disabled={page === 1}
                    className="p-1.5 rounded-lg border border-slate-200 bg-white text-slate-600 hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed shadow-2xs cursor-pointer"
                  >
                    <ChevronLeft size={14} />
                  </button>
                  <span className="px-2 font-semibold text-slate-700">
                    Page {page} of {customersData.pages || 1}
                  </span>
                  <button
                    onClick={() => setPage((p) => Math.min(p + 1, customersData.pages))}
                    disabled={page >= customersData.pages}
                    className="p-1.5 rounded-lg border border-slate-200 bg-white text-slate-600 hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed shadow-2xs cursor-pointer"
                  >
                    <ChevronRight size={14} />
                  </button>
                </div>
              </div>
            )}
          </Card>
        </div>

        {/* Right: Selected Customer Details Drawer */}
        {selectedCustomerId && selectedCustomer && (
          <div data-demo="customer-drawer" className="w-full lg:w-5/12 animate-in slide-in-from-right duration-200">
            <Card>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between w-full">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-blue-600 text-white font-bold flex items-center justify-center text-sm shadow-xs">
                      {getAvatarInitials(selectedCustomer.legal_name)}
                    </div>
                    <div>
                      <CardTitle className="text-sm">{selectedCustomer.legal_name}</CardTitle>
                      <CardDescription>
                        {selectedCustomer.customer_number || "CUST"} • {selectedCustomer.industry || "General"}
                      </CardDescription>
                    </div>
                  </div>
                  <div className="flex items-center gap-1">
                    <StatusBadge status={selectedCustomer.status} />
                    <button
                      onClick={() => setSelectedCustomerId(null)}
                      className="p-1 text-slate-400 hover:text-slate-700 rounded-lg hover:bg-slate-100 transition-colors cursor-pointer ml-1"
                    >
                      <X size={16} />
                    </button>
                  </div>
                </div>
              </CardHeader>

              {/* Tabs */}
              <div className="px-6 pt-1">
                <Tabs
                  tabs={customerTabs}
                  activeTab={activeTab}
                  onChange={setActiveTab}
                />
              </div>

              {/* Tab Contents */}
              <CardContent className="space-y-4 pt-4 text-xs">
                {activeTab === "overview" && (
                  <div className="space-y-4">
                    <div className="grid grid-cols-2 gap-3 p-3 bg-slate-50 rounded-lg border border-slate-100">
                      <div>
                        <span className="text-[10px] text-slate-400 uppercase font-semibold block">Email</span>
                        <span className="text-slate-800 font-medium truncate block">{selectedCustomer.email || "—"}</span>
                      </div>
                      <div>
                        <span className="text-[10px] text-slate-400 uppercase font-semibold block">Phone</span>
                        <span className="text-slate-800 font-medium block">{selectedCustomer.phone || "—"}</span>
                      </div>
                      <div>
                        <span className="text-[10px] text-slate-400 uppercase font-semibold block">Website</span>
                        <span className="text-slate-800 font-medium truncate block">{selectedCustomer.website || "—"}</span>
                      </div>
                      <div>
                        <span className="text-[10px] text-slate-400 uppercase font-semibold block">Type</span>
                        <span className="text-slate-800 font-medium block">{selectedCustomer.customer_type}</span>
                      </div>
                    </div>

                    {/* Addresses */}
                    <div className="space-y-2">
                      <div className="flex justify-between items-center">
                        <span className="font-semibold text-slate-800">Billing Address</span>
                        {canCreate && (
                          <button
                            onClick={() => setIsAddAddressModalOpen(true)}
                            className="text-blue-600 font-semibold hover:underline cursor-pointer"
                          >
                            + Add
                          </button>
                        )}
                      </div>
                      {selectedCustomer.addresses && selectedCustomer.addresses.length > 0 ? (
                        selectedCustomer.addresses.map((addr) => (
                          <div key={addr.id} className="p-2.5 bg-slate-50 rounded-lg border border-slate-100 text-slate-600 space-y-0.5">
                            <div className="font-semibold text-slate-900">{addr.address_type} Address</div>
                            <div>{addr.line1}</div>
                            {addr.line2 && <div>{addr.line2}</div>}
                            <div>{addr.city}, {addr.state} {addr.postal_code}</div>
                            <div>{addr.country}</div>
                          </div>
                        ))
                      ) : (
                        <p className="text-slate-400 italic">No addresses recorded.</p>
                      )}
                    </div>
                  </div>
                )}

                {activeTab === "contacts" && (
                  <div className="space-y-3">
                    <div className="flex justify-between items-center">
                      <span className="font-semibold text-slate-800">Stakeholder Contacts</span>
                      {canCreate && (
                        <Button size="sm" variant="secondary" onClick={() => setIsAddContactModalOpen(true)}>
                          + Add Contact
                        </Button>
                      )}
                    </div>
                    {selectedCustomer.contacts && selectedCustomer.contacts.length > 0 ? (
                      selectedCustomer.contacts.map((contact) => (
                        <div key={contact.id} className="p-3 bg-slate-50 rounded-lg border border-slate-100 flex items-start justify-between">
                          <div>
                            <div className="font-semibold text-slate-900">
                              {contact.first_name} {contact.last_name}
                              {contact.is_primary && (
                                <span className="ml-2 text-[10px] bg-blue-50 text-blue-700 px-1.5 py-0.5 rounded font-bold">
                                  Primary
                                </span>
                              )}
                            </div>
                            <div className="text-slate-500 mt-0.5">{contact.email}</div>
                            {contact.phone && <div className="text-slate-400 text-[11px]">{contact.phone}</div>}
                          </div>
                          {isManager && (
                            <button
                              onClick={() => deleteContactMutation.mutate(contact.id)}
                              className="text-slate-400 hover:text-rose-600 p-1 cursor-pointer"
                            >
                              <Trash2 size={13} />
                            </button>
                          )}
                        </div>
                      ))
                    ) : (
                      <p className="text-slate-400 italic text-center py-6">No contacts registered.</p>
                    )}
                  </div>
                )}

                {activeTab === "notes" && (
                  <div className="space-y-3">
                    <form onSubmit={handleAddNote} className="space-y-2">
                      <textarea
                        value={noteText}
                        onChange={(e) => setNoteText(e.target.value)}
                        placeholder="Add a customer note..."
                        rows={2}
                        className="w-full p-2 bg-white border border-slate-200 rounded-lg text-xs text-slate-800 focus:outline-none focus:border-blue-500"
                      />
                      <div className="flex justify-end">
                        <Button size="sm" variant="primary" type="submit">
                          Post Note
                        </Button>
                      </div>
                    </form>
                    <div className="space-y-2 pt-2">
                      {activeNotes.map((note) => (
                        <div key={note.id} className="p-2.5 bg-slate-50 border border-slate-100 rounded-lg">
                          <p className="text-slate-800">{note.text}</p>
                          <span className="text-[10px] text-slate-400 mt-1 block">{note.date}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {activeTab === "quotes" && (
                  <div className="text-center py-8 text-slate-500 space-y-2">
                    <FileText size={24} className="mx-auto text-slate-300" />
                    <p className="font-semibold text-slate-700">No active quotes linked</p>
                    <p className="text-[11px] text-slate-400">Create a quote for this customer in the Quote Builder.</p>
                  </div>
                )}

                {activeTab === "activity" && (
                  <div className="space-y-3 pl-2 border-l border-slate-200">
                    <div className="relative pl-3">
                      <span className="w-2 h-2 rounded-full bg-blue-600 absolute -left-[5px] top-1" />
                      <div className="font-semibold text-slate-800">Account Viewed</div>
                      <div className="text-[10px] text-slate-400">Just now</div>
                    </div>
                    <div className="relative pl-3">
                      <span className="w-2 h-2 rounded-full bg-slate-300 absolute -left-[5px] top-1" />
                      <div className="font-semibold text-slate-800">Created in CRM</div>
                      <div className="text-[10px] text-slate-400">
                        {new Date(selectedCustomer.created_at).toLocaleDateString()}
                      </div>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        )}
      </div>

      {/* ─── MODAL: CREATE CUSTOMER ─── */}
      <Modal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        title="Onboard New Customer"
        description="Enter the legal entity information and account credentials."
        maxWidth="lg"
      >
        <form onSubmit={handleCreateCustomer} className="space-y-3.5 text-xs">
          <div className="grid grid-cols-2 gap-3.5">
            <div>
              <label className="font-semibold text-slate-700 block mb-1">Customer Number *</label>
              <input
                type="text"
                name="customer_number"
                required
                placeholder="e.g. CUST-1002"
                className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-slate-800 focus:outline-none focus:border-blue-500"
              />
            </div>
            <div>
              <label className="font-semibold text-slate-700 block mb-1">Legal Name *</label>
              <input
                type="text"
                name="legal_name"
                required
                placeholder="e.g. Acme Corporation"
                className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-slate-800 focus:outline-none focus:border-blue-500"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3.5">
            <div>
              <label className="font-semibold text-slate-700 block mb-1">Display Name</label>
              <input
                type="text"
                name="display_name"
                placeholder="e.g. Acme"
                className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-slate-800 focus:outline-none focus:border-blue-500"
              />
            </div>
            <div>
              <label className="font-semibold text-slate-700 block mb-1">Email Address</label>
              <input
                type="email"
                name="email"
                placeholder="contact@acme.com"
                className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-slate-800 focus:outline-none focus:border-blue-500"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3.5">
            <div>
              <label className="font-semibold text-slate-700 block mb-1">Phone</label>
              <input
                type="text"
                name="phone"
                placeholder="+1 555-0199"
                className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-slate-800 focus:outline-none focus:border-blue-500"
              />
            </div>
            <div>
              <label className="font-semibold text-slate-700 block mb-1">Industry</label>
              <input
                type="text"
                name="industry"
                placeholder="e.g. Technology"
                className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-slate-800 focus:outline-none focus:border-blue-500"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3.5">
            <div>
              <label className="font-semibold text-slate-700 block mb-1">Customer Type</label>
              <select
                name="customer_type"
                className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-slate-800 focus:outline-none focus:border-blue-500"
              >
                <option value="BUSINESS">Business</option>
                <option value="INDIVIDUAL">Individual</option>
              </select>
            </div>
            <div>
              <label className="font-semibold text-slate-700 block mb-1">Status</label>
              <select
                name="status"
                className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-slate-800 focus:outline-none focus:border-blue-500"
              >
                <option value="PROSPECT">Prospect</option>
                <option value="ACTIVE">Active</option>
                <option value="INACTIVE">Inactive</option>
              </select>
            </div>
          </div>

          <div className="flex justify-end gap-2.5 pt-4 border-t border-slate-100">
            <Button variant="secondary" onClick={() => setIsCreateModalOpen(false)}>
              Cancel
            </Button>
            <Button variant="primary" type="submit" isLoading={createCustomerMutation.isPending}>
              Create Customer
            </Button>
          </div>
        </form>
      </Modal>

      {/* ─── MODAL: EDIT CUSTOMER ─── */}
      {isEditModalOpen && selectedCustomer && (
        <Modal
          isOpen={isEditModalOpen}
          onClose={() => setIsEditModalOpen(false)}
          title="Modify Customer Account"
          description={`Update details for ${selectedCustomer.legal_name}.`}
          maxWidth="lg"
        >
          <form onSubmit={handleUpdateCustomer} className="space-y-3.5 text-xs">
            <div className="grid grid-cols-2 gap-3.5">
              <div>
                <label className="font-semibold text-slate-700 block mb-1">Customer Number *</label>
                <input
                  type="text"
                  name="customer_number"
                  defaultValue={selectedCustomer.customer_number || ""}
                  required
                  className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-slate-800 focus:outline-none focus:border-blue-500"
                />
              </div>
              <div>
                <label className="font-semibold text-slate-700 block mb-1">Legal Name *</label>
                <input
                  type="text"
                  name="legal_name"
                  defaultValue={selectedCustomer.legal_name}
                  required
                  className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-slate-800 focus:outline-none focus:border-blue-500"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3.5">
              <div>
                <label className="font-semibold text-slate-700 block mb-1">Email</label>
                <input
                  type="email"
                  name="email"
                  defaultValue={selectedCustomer.email || ""}
                  className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-slate-800 focus:outline-none focus:border-blue-500"
                />
              </div>
              <div>
                <label className="font-semibold text-slate-700 block mb-1">Phone</label>
                <input
                  type="text"
                  name="phone"
                  defaultValue={selectedCustomer.phone || ""}
                  className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-slate-800 focus:outline-none focus:border-blue-500"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3.5">
              <div>
                <label className="font-semibold text-slate-700 block mb-1">Industry</label>
                <input
                  type="text"
                  name="industry"
                  defaultValue={selectedCustomer.industry || ""}
                  className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-slate-800 focus:outline-none focus:border-blue-500"
                />
              </div>
              <div>
                <label className="font-semibold text-slate-700 block mb-1">Status</label>
                <select
                  name="status"
                  defaultValue={selectedCustomer.status}
                  className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-slate-800 focus:outline-none focus:border-blue-500"
                >
                  <option value="PROSPECT">Prospect</option>
                  <option value="ACTIVE">Active</option>
                  <option value="INACTIVE">Inactive</option>
                </select>
              </div>
            </div>

            <div className="flex justify-end gap-2.5 pt-4 border-t border-slate-100">
              <Button variant="secondary" onClick={() => setIsEditModalOpen(false)}>
                Cancel
              </Button>
              <Button variant="primary" type="submit" isLoading={updateCustomerMutation.isPending}>
                Save Changes
              </Button>
            </div>
          </form>
        </Modal>
      )}

      {/* ─── MODAL: ADD CONTACT ─── */}
      {isAddContactModalOpen && (
        <Modal
          isOpen={isAddContactModalOpen}
          onClose={() => setIsAddContactModalOpen(false)}
          title="Add Stakeholder Contact"
          maxWidth="sm"
        >
          <form onSubmit={handleAddContact} className="space-y-3.5 text-xs">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="font-semibold text-slate-700 block mb-1">First Name *</label>
                <input
                  type="text"
                  name="first_name"
                  required
                  className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-slate-800 focus:outline-none focus:border-blue-500"
                />
              </div>
              <div>
                <label className="font-semibold text-slate-700 block mb-1">Last Name *</label>
                <input
                  type="text"
                  name="last_name"
                  required
                  className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-slate-800 focus:outline-none focus:border-blue-500"
                />
              </div>
            </div>
            <div>
              <label className="font-semibold text-slate-700 block mb-1">Email *</label>
              <input
                type="email"
                name="email"
                required
                className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-slate-800 focus:outline-none focus:border-blue-500"
              />
            </div>
            <div>
              <label className="font-semibold text-slate-700 block mb-1">Phone</label>
              <input
                type="text"
                name="phone"
                className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-slate-800 focus:outline-none focus:border-blue-500"
              />
            </div>
            <div className="flex justify-end gap-2 pt-3 border-t border-slate-100">
              <Button variant="secondary" onClick={() => setIsAddContactModalOpen(false)}>
                Cancel
              </Button>
              <Button variant="primary" type="submit" isLoading={addContactMutation.isPending}>
                Save Contact
              </Button>
            </div>
          </form>
        </Modal>
      )}

      {/* ─── MODAL: ADD ADDRESS ─── */}
      {isAddAddressModalOpen && (
        <Modal
          isOpen={isAddAddressModalOpen}
          onClose={() => setIsAddAddressModalOpen(false)}
          title="Add Customer Address"
          maxWidth="sm"
        >
          <form onSubmit={handleAddAddress} className="space-y-3 text-xs">
            <div>
              <label className="font-semibold text-slate-700 block mb-1">Address Type</label>
              <select
                name="address_type"
                className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-slate-800 focus:outline-none focus:border-blue-500"
              >
                <option value="BILLING">Billing</option>
                <option value="SHIPPING">Shipping</option>
              </select>
            </div>
            <div>
              <label className="font-semibold text-slate-700 block mb-1">Line 1 *</label>
              <input
                type="text"
                name="line1"
                required
                placeholder="123 Enterprise Blvd"
                className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-slate-800 focus:outline-none focus:border-blue-500"
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="font-semibold text-slate-700 block mb-1">City *</label>
                <input
                  type="text"
                  name="city"
                  required
                  className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-slate-800 focus:outline-none focus:border-blue-500"
                />
              </div>
              <div>
                <label className="font-semibold text-slate-700 block mb-1">State *</label>
                <input
                  type="text"
                  name="state"
                  required
                  className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-slate-800 focus:outline-none focus:border-blue-500"
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="font-semibold text-slate-700 block mb-1">Postal Code *</label>
                <input
                  type="text"
                  name="postal_code"
                  required
                  className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-slate-800 focus:outline-none focus:border-blue-500"
                />
              </div>
              <div>
                <label className="font-semibold text-slate-700 block mb-1">Country *</label>
                <input
                  type="text"
                  name="country"
                  defaultValue="United States"
                  required
                  className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-slate-800 focus:outline-none focus:border-blue-500"
                />
              </div>
            </div>
            <div className="flex justify-end gap-2 pt-3 border-t border-slate-100">
              <Button variant="secondary" onClick={() => setIsAddAddressModalOpen(false)}>
                Cancel
              </Button>
              <Button variant="primary" type="submit" isLoading={addAddressMutation.isPending}>
                Save Address
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
