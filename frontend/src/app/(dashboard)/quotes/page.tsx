"use client";

import React, { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  FileText,
  Plus,
  Search,
  Filter,
  Eye,
  Trash2,
  CheckCircle,
  Clock,
  ArrowRight,
  ShieldCheck,
  ChevronDown,
  Info,
  Calendar,
  Building,
  Check,
  X,
  Share2,
  Save,
  Laptop,
  Cloud,
  Wrench,
  TrendingUp,
  MoreVertical,
  Edit,
  Sparkles,
  Package,
  Layers,
  ArrowLeft
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
  SearchBar,
  FilterSelect,
  HorizontalStepper,
  CircularProgress,
  Modal
} from "@/components/ui";

// ─── Interfaces ─────────────────────────────────────────────────────────────

interface CustomerSummary {
  id: number;
  name: string;
  legal_name?: string | null;
  display_name?: string | null;
  customer_number?: string | null;
  email?: string | null;
  phone?: string | null;
  industry?: string | null;
  customer_type?: string | null;
}

interface QuoteLineItem {
  id: number;
  quote_id?: number;
  product_id: number;
  product_name?: string | null;
  sku?: string | null;
  billing_type: string;
  currency: string;
  quantity: number;
  unit_price: string | number;
  discount_percentage: string | number;
  discount_amount?: string | number;
  total_price?: string | number;
  line_total: string | number;
  configuration_status?: "CONFIGURED" | "STANDARD";
  configuration_version?: string;
}

interface Quote {
  id: number;
  quote_number: string;
  version: number;
  customer_id: number;
  title?: string | null;
  description?: string | null;
  status: "DRAFT" | "SUBMITTED" | "APPROVED" | "REJECTED" | "EXPIRED" | "CANCELLED";
  currency: string;
  valid_until?: string | null;
  notes?: string | null;
  subtotal: string;
  discount_amount: string;
  discount_total: string;
  tax_amount: string;
  total_amount: string;
  grand_total: string;
  margin_percentage?: string | null;
  margin_amount?: string | null;
  created_by_id: string;
  customer?: CustomerSummary | null;
  created_at: string;
  items: QuoteLineItem[];
}

interface Product {
  id: number;
  sku: string;
  name: string;
  description?: string | null;
  base_price: string | number;
  currency: string;
  is_active: boolean;
  billing_type: string;
}

export default function QuoteBuilderPage() {
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const {
    isActive: isDemoActive,
    flags: demoFlags,
    mockQuotes,
    mockProducts,
    mockCustomers,
  } = useDemoTour();

  // Mode: "builder" (default to match reference image) or "list"
  const [viewMode, setViewMode] = useState<"builder" | "list">("builder");

  // Stepper state (1: Customer, 2: Add Products, 3: Configure, 4: Pricing, 5: Review)
  const [currentStep, setCurrentStep] = useState<number>(3);

  // Search & Filter State for List View
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");

  // Active Quote State for Builder
  const [activeQuoteId, setActiveQuoteId] = useState<number | null>(null);
  const [isCustomerModalOpen, setIsCustomerModalOpen] = useState(false);
  const [isProductPickerOpen, setIsProductPickerOpen] = useState(false);

  // Form Fields
  const [quoteName, setQuoteName] = useState("Acme IT Infrastructure Upgrade");
  const [quoteNumber, setQuoteNumber] = useState("Q-2026-0001");
  const [validUntil, setValidUntil] = useState("2026-09-30");
  const [currency, setCurrency] = useState("USD");
  const [description, setDescription] = useState(
    "IT infrastructure upgrade including hardware, software licenses, and professional services."
  );

  // Active Customer in Builder
  const [selectedCustomer, setSelectedCustomer] = useState<CustomerSummary>({
    id: 1,
    name: "Acme Corporation",
    customer_number: "CUST-001",
    email: "sarah.johnson@acme.com",
    phone: "+1 (415) 555-0123",
    industry: "Technology",
    customer_type: "Enterprise",
  });

  // Line Items in Builder (pre-populated with high-fidelity reference items)
  const [lineItems, setLineItems] = useState<QuoteLineItem[]>([
    {
      id: 1,
      product_id: 101,
      product_name: "Dell Latitude 7440",
      sku: "DEV-LAP-001",
      configuration_status: "CONFIGURED",
      configuration_version: "v1.0",
      billing_type: "NRC",
      currency: "USD",
      quantity: 10,
      unit_price: 1299.0,
      discount_percentage: 10,
      line_total: 11691.0,
    },
    {
      id: 2,
      product_id: 102,
      product_name: "Enterprise Cloud Subscription",
      sku: "SaaS-TIER-SEED",
      configuration_status: "STANDARD",
      billing_type: "MRC",
      currency: "USD",
      quantity: 50,
      unit_price: 49.0,
      discount_percentage: 0,
      line_total: 2450.0,
    },
    {
      id: 3,
      product_id: 103,
      product_name: "Implementation Service",
      sku: "DEV-SVC-IMP",
      configuration_status: "STANDARD",
      billing_type: "NRC",
      currency: "USD",
      quantity: 1,
      unit_price: 1500.0,
      discount_percentage: 0,
      line_total: 1500.0,
    },
  ]);

  // Queries
  const { data: liveQuotes = [], isLoading: isLoadingLiveQuotes } = useQuery<Quote[]>({
    queryKey: ["quotes", statusFilter, searchQuery],
    queryFn: () => {
      let path = "/quotes/";
      const params = new URLSearchParams();
      if (statusFilter !== "ALL") params.append("status", statusFilter);
      if (searchQuery.trim()) params.append("search", searchQuery.trim());
      const queryStr = params.toString();
      return api.get<Quote[]>(queryStr ? `${path}?${queryStr}` : path);
    },
    enabled: !isDemoActive,
  });
  const quotes = isDemoActive ? (mockQuotes as unknown as Quote[]) : liveQuotes;
  const isLoadingQuotes = isDemoActive ? false : isLoadingLiveQuotes;

  const { data: customersData } = useQuery<{ items: CustomerSummary[] } | CustomerSummary[]>({
    queryKey: ["customers-list"],
    queryFn: () => api.get<any>("/customers/"),
    enabled: !isDemoActive,
  });
  const customerList: CustomerSummary[] = isDemoActive
    ? mockCustomers.map((c) => ({
        id: c.id,
        name: c.legal_name,
        legal_name: c.legal_name,
        display_name: c.display_name,
        customer_number: c.customer_number,
        email: c.email,
        phone: c.phone,
        industry: c.industry,
        customer_type: c.customer_type,
      }))
    : Array.isArray(customersData)
      ? customersData
      : customersData?.items || [];

  const { data: productsData = [] } = useQuery<Product[]>({
    queryKey: ["products-list"],
    queryFn: () => api.get<Product[]>("/catalog/products/"),
    enabled: !isDemoActive,
  });
  const activeProducts = (isDemoActive ? mockProducts : productsData).filter((p) => p.is_active);

  useEffect(() => {
    if (!isDemoActive) return;
    setViewMode(demoFlags.quoteBuilder ? "builder" : "list");
    if (demoFlags.quoteLineCount <= 0) {
      setLineItems([]);
    } else {
      setLineItems(mockQuotes[0]?.items.slice(0, demoFlags.quoteLineCount) as QuoteLineItem[]);
    }
  }, [isDemoActive, demoFlags.quoteBuilder, demoFlags.quoteLineCount, mockQuotes]);

  // Mutations
  const createQuoteMutation = useMutation({
    mutationFn: (payload: any) => api.post<Quote>("/quotes/", payload),
    onSuccess: (newQuote) => {
      queryClient.invalidateQueries({ queryKey: ["quotes"] });
      setActiveQuoteId(newQuote.id);
      setQuoteNumber(newQuote.quote_number);
      alert(`Quote ${newQuote.quote_number} saved successfully!`);
    },
    onError: (err: any) => {
      alert(err?.detail || "Failed to save quote draft.");
    },
  });

  const submitQuoteMutation = useMutation({
    mutationFn: (quoteId: number) => api.post<Quote>(`/quotes/${quoteId}/submit`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["quotes"] });
      alert("Quote submitted for approval successfully!");
      setViewMode("list");
    },
    onError: (err: any) => {
      alert(err?.detail || "Failed to submit quote.");
    },
  });

  // Calculate totals
  const subtotal = lineItems.reduce((acc, item) => {
    const unit = Number(item.unit_price) || 0;
    const qty = Number(item.quantity) || 0;
    return acc + unit * qty;
  }, 0);

  const discountAmount = lineItems.reduce((acc, item) => {
    const unit = Number(item.unit_price) || 0;
    const qty = Number(item.quantity) || 0;
    const discPct = Number(item.discount_percentage) || 0;
    return acc + (unit * qty * discPct) / 100;
  }, 0);

  const totalUSD = subtotal - discountAmount;
  const expectedMarginPercent = 32.5;
  const expectedMarginAmount = 6834.0;

  // Actions
  const handleQuantityChange = (id: number, newQty: number) => {
    setLineItems((prev) =>
      prev.map((item) => {
        if (item.id === id) {
          const qty = Math.max(1, newQty);
          const unit = Number(item.unit_price) || 0;
          const discPct = Number(item.discount_percentage) || 0;
          const total = qty * unit * (1 - discPct / 100);
          return { ...item, quantity: qty, line_total: total };
        }
        return item;
      })
    );
  };

  const handleDiscountChange = (id: number, newDisc: number) => {
    setLineItems((prev) =>
      prev.map((item) => {
        if (item.id === id) {
          const disc = Math.min(100, Math.max(0, newDisc));
          const unit = Number(item.unit_price) || 0;
          const qty = Number(item.quantity) || 0;
          const total = qty * unit * (1 - disc / 100);
          return { ...item, discount_percentage: disc, line_total: total };
        }
        return item;
      })
    );
  };

  const handleRemoveLine = (id: number) => {
    setLineItems((prev) => prev.filter((item) => item.id !== id));
  };

  const handleAddProduct = (product: Product) => {
    const newItem: QuoteLineItem = {
      id: Date.now(),
      product_id: product.id,
      product_name: product.name,
      sku: product.sku,
      configuration_status: "STANDARD",
      billing_type: product.billing_type || "NRC",
      currency: product.currency || "USD",
      quantity: 1,
      unit_price: Number(product.base_price) || 100,
      discount_percentage: 0,
      line_total: Number(product.base_price) || 100,
    };
    setLineItems((prev) => [...prev, newItem]);
    setIsProductPickerOpen(false);
  };

  const handleSaveDraft = () => {
    if (isDemoActive) return;
    const payload = {
      customer_id: selectedCustomer.id || 1,
      title: quoteName,
      currency,
      valid_until: validUntil || undefined,
      description,
      notes: "Saved from CPQ Cognitive Quote Builder",
      items: lineItems.map((item) => ({
        product_id: item.product_id,
        quantity: item.quantity,
        discount_percentage: item.discount_percentage,
      })),
    };
    createQuoteMutation.mutate(payload);
  };

  const handleSubmit = () => {
    if (isDemoActive) return;
    if (activeQuoteId) {
      submitQuoteMutation.mutate(activeQuoteId);
    } else {
      // First save draft, then submit
      const payload = {
        customer_id: selectedCustomer.id || 1,
        title: quoteName,
        currency,
        valid_until: validUntil || undefined,
        description,
        items: lineItems.map((item) => ({
          product_id: item.product_id,
          quantity: item.quantity,
          discount_percentage: item.discount_percentage,
        })),
      };
      createQuoteMutation.mutate(payload, {
        onSuccess: (newQuote) => {
          submitQuoteMutation.mutate(newQuote.id);
        },
      });
    }
  };

  const stepsList = [
    { id: 1, label: "Customer" },
    { id: 2, label: "Add Products" },
    { id: 3, label: "Configure" },
    { id: 4, label: "Pricing" },
    { id: 5, label: "Review" },
  ];

  // ─── LIST VIEW ─────────────────────────────────────────────────────────────
  if (viewMode === "list") {
    return (
      <div className="space-y-6">
        <div data-demo="quotes-header">
        <PageHeader
          title="Quotes"
          description="Manage, build, and track enterprise customer quotes."
          actions={
            <Button
              variant="primary"
              icon={<Plus size={15} />}
              onClick={() => {
                setActiveQuoteId(null);
                setViewMode("builder");
              }}
            >
              Create Quote
            </Button>
          }
        />
        </div>

        <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-white p-3 rounded-xl border border-slate-200/80 shadow-xs">
          <SearchBar
            value={searchQuery}
            onChangeValue={setSearchQuery}
            placeholder="Search quotes by number, title, or customer..."
            className="w-full sm:w-80"
          />
          <div className="flex items-center gap-2">
            <FilterSelect
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              label="Status"
            >
              <option value="ALL">All Statuses</option>
              <option value="DRAFT">Draft</option>
              <option value="SUBMITTED">Submitted</option>
              <option value="APPROVED">Approved</option>
              <option value="REJECTED">Rejected</option>
              <option value="EXPIRED">Expired</option>
            </FilterSelect>
          </div>
        </div>

        <DataTable data-demo="quotes-list">
          <TableHead>
            <TableRow>
              <TableHeader>Quote #</TableHeader>
              <TableHeader>Title</TableHeader>
              <TableHeader>Customer</TableHeader>
              <TableHeader>Status</TableHeader>
              <TableHeader>Total</TableHeader>
              <TableHeader>Valid Until</TableHeader>
              <TableHeader className="text-right">Actions</TableHeader>
            </TableRow>
          </TableHead>
          <tbody>
            {isLoadingQuotes ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center py-8 text-slate-500">
                  Loading quotes...
                </TableCell>
              </TableRow>
            ) : quotes.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center py-8 text-slate-500">
                  No quotes found. Click &quot;Create Quote&quot; to build one.
                </TableCell>
              </TableRow>
            ) : (
              quotes.map((q) => (
                <TableRow key={q.id} data-demo={q.quote_number === "Q-2026-0001" ? "quotes-list-acme" : undefined}>
                  <TableCell className="font-semibold text-slate-900">{q.quote_number}</TableCell>
                  <TableCell className="font-medium text-slate-800">{q.title || "Untitled Quote"}</TableCell>
                  <TableCell className="text-slate-600">{q.customer?.name || `Customer #${q.customer_id}`}</TableCell>
                  <TableCell>
                    <StatusBadge status={q.status} />
                  </TableCell>
                  <TableCell className="font-semibold text-slate-900">
                    ${Number(q.total_amount || q.grand_total || 0).toLocaleString("en-US", { minimumFractionDigits: 2 })}
                  </TableCell>
                  <TableCell className="text-slate-500">{q.valid_until || "—"}</TableCell>
                  <TableCell className="text-right">
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => {
                        setActiveQuoteId(q.id);
                        setQuoteNumber(q.quote_number);
                        setQuoteName(q.title || "Quote " + q.quote_number);
                        if (q.customer) setSelectedCustomer(q.customer);
                        if (q.valid_until) setValidUntil(q.valid_until);
                        if (q.description) setDescription(q.description);
                        if (q.items && q.items.length > 0) setLineItems(q.items);
                        setViewMode("builder");
                      }}
                    >
                      Open
                    </Button>
                  </TableCell>
                </TableRow>
              ))
            )}
          </tbody>
        </DataTable>
      </div>
    );
  }

  // ─── BUILDER VIEW (MATCHES REFERENCE IMAGE DIRECTLY) ────────────────────────
  return (
    <div className="space-y-6">
      {/* ─── Top Page Header ────────────────────────────────────── */}
      <div data-demo="quotes-header">
      <PageHeader
        title="Create Quote"
        description="Configure products, apply pricing, and generate a professional quote."
        onBack={() => setViewMode("list")}
        backLabel="Back to Quotes"
        actions={
          <>
            <Button
              variant="secondary"
              icon={<Save size={15} />}
              onClick={handleSaveDraft}
              isLoading={createQuoteMutation.isPending}
            >
              Save Draft
            </Button>
            <Button
              variant="secondary"
              icon={<Share2 size={15} />}
              onClick={() => alert("Share link copied to clipboard!")}
            >
              Share
            </Button>
            <Button
              variant="primary"
              data-demo="quotes-submit"
              icon={<ArrowRight size={15} />}
              iconPosition="right"
              onClick={handleSubmit}
              isLoading={submitQuoteMutation.isPending}
            >
              Review & Submit
            </Button>
          </>
        }
      />
      </div>

      {/* ─── Horizontal Stepper ─────────────────────────────────── */}
      <div className="bg-white border border-slate-200/80 rounded-xl p-3 shadow-2xs">
        <HorizontalStepper
          steps={stepsList}
          currentStep={currentStep}
          onStepClick={(step) => setCurrentStep(step)}
        />
      </div>

      {/* ─── Two-Column Enterprise Workspace ─────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* ─── Left Column (8 cols): Main Content ─────────────── */}
        <div className="lg:col-span-8 space-y-6">
          {/* Card 1: Customer Information */}
          <Card>
            <CardHeader>
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center border border-blue-100">
                  <Building size={17} />
                </div>
                <div>
                  <CardTitle>Customer Information</CardTitle>
                  <CardDescription>Select the customer for this quote.</CardDescription>
                </div>
              </div>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setIsCustomerModalOpen(true)}
              >
                Change Customer
              </Button>
            </CardHeader>
            <CardContent>
              <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                <div className="flex items-center gap-4">
                  {/* Purple/Blue Avatar */}
                  <div className="w-12 h-12 rounded-xl bg-indigo-600 text-white font-bold flex items-center justify-center text-sm shadow-xs">
                    AC
                  </div>
                  <div>
                    <h4 className="text-base font-bold text-slate-900 leading-tight">
                      {selectedCustomer.name}
                    </h4>
                    <div className="flex items-center gap-2 text-xs text-slate-500 mt-1 font-medium">
                      <span>{selectedCustomer.customer_number || "CUST-001"}</span>
                      <span>•</span>
                      <span>{selectedCustomer.industry || "Technology"}</span>
                      <span>•</span>
                      <span className="text-slate-600">{selectedCustomer.customer_type || "Enterprise"}</span>
                    </div>
                    <div className="flex items-center gap-4 text-xs text-slate-500 mt-2">
                      <span className="text-slate-600">{selectedCustomer.email || "sarah.johnson@acme.com"}</span>
                      <span className="text-slate-600">{selectedCustomer.phone || "+1 (415) 555-0123"}</span>
                    </div>
                  </div>
                </div>

                <div className="text-xs space-y-1.5 border-t sm:border-t-0 sm:border-l border-slate-100 pt-3 sm:pt-0 sm:pl-6 text-slate-600">
                  <div>
                    <span className="text-slate-400">Account Manager:</span>{" "}
                    <span className="font-semibold text-slate-800">Sarah Johnson</span>
                  </div>
                  <div>
                    <span className="text-slate-400">Billing Address:</span>{" "}
                    <span className="font-medium text-slate-800">
                      123 Market Street, San Francisco, CA 94105, United States
                    </span>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Card 2: Quote Details */}
          <Card>
            <CardHeader>
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center border border-blue-100">
                  <FileText size={17} />
                </div>
                <div>
                  <CardTitle>Quote Details</CardTitle>
                  <CardDescription>Set up basic information for this quote.</CardDescription>
                </div>
              </div>
              <Button
                variant="secondary"
                size="sm"
                icon={<ChevronDown size={14} />}
                iconPosition="right"
                onClick={() => alert("Templates: Standard SaaS, Enterprise Hardware, Implementation Services")}
              >
                Load Template
              </Button>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Quote Name <span className="text-rose-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={quoteName}
                    onChange={(e) => setQuoteName(e.target.value)}
                    className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-xs text-slate-800 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/10 shadow-2xs font-medium"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Quote Number
                  </label>
                  <input
                    type="text"
                    readOnly
                    value={quoteNumber}
                    className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-xs text-slate-600 font-mono"
                  />
                  <span className="text-[10px] text-slate-400 mt-1 block">Auto-generated on save</span>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Valid Until <span className="text-rose-500">*</span>
                  </label>
                  <div className="relative flex items-center">
                    <input
                      type="date"
                      value={validUntil}
                      onChange={(e) => setValidUntil(e.target.value)}
                      className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-xs text-slate-800 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/10 shadow-2xs"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Currency <span className="text-rose-500">*</span>
                  </label>
                  <select
                    value={currency}
                    onChange={(e) => setCurrency(e.target.value)}
                    className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-xs text-slate-800 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/10 shadow-2xs cursor-pointer font-medium"
                  >
                    <option value="USD">USD - US Dollar</option>
                    <option value="EUR">EUR - Euro</option>
                    <option value="GBP">GBP - British Pound</option>
                  </select>
                </div>
              </div>

              <div>
                <div className="flex justify-between items-center mb-1">
                  <label className="block text-xs font-semibold text-slate-700">Description</label>
                  <span className="text-[11px] text-slate-400">{description.length}/500</span>
                </div>
                <textarea
                  rows={2}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  maxLength={500}
                  className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-xs text-slate-800 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/10 shadow-2xs leading-relaxed"
                />
              </div>
            </CardContent>
          </Card>

          {/* Card 3: Products in this Quote */}
          <Card data-demo="quotes-lines">
            <CardHeader>
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center border border-blue-100">
                  <Package size={17} />
                </div>
                <div>
                  <CardTitle>Products in this Quote</CardTitle>
                  <CardDescription>Add and configure products for your quote.</CardDescription>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  icon={<Plus size={14} className="text-blue-600" />}
                  onClick={() => setIsProductPickerOpen(true)}
                >
                  Add Products
                </Button>
                <Button
                  variant="primary"
                  size="sm"
                  icon={<Layers size={14} />}
                  onClick={() => alert("Opening Bundle Configurator...")}
                >
                  Configure Bundle
                </Button>
              </div>
            </CardHeader>
            <CardContent className="p-0">
              <DataTable className="border-0 rounded-none">
                <TableHead>
                  <TableRow>
                    <TableHeader className="w-10">#</TableHeader>
                    <TableHeader>Product</TableHeader>
                    <TableHeader>Configuration</TableHeader>
                    <TableHeader>Billing Type</TableHeader>
                    <TableHeader className="w-20">Qty</TableHeader>
                    <TableHeader>Unit Price</TableHeader>
                    <TableHeader className="w-24">Discount</TableHeader>
                    <TableHeader>Total</TableHeader>
                    <TableHeader className="w-20 text-right">Actions</TableHeader>
                  </TableRow>
                </TableHead>
                <tbody>
                  {lineItems.map((item, index) => {
                    const isConfigured = item.configuration_status === "CONFIGURED";
                    return (
                      <TableRow key={item.id} data-demo={item.sku === "DEV-LAP-001" ? "quote-line-latitude" : undefined}>
                        <TableCell className="text-slate-400 font-medium">{index + 1}</TableCell>
                        <TableCell>
                          <div className="flex items-center gap-3">
                            <div className="w-7 h-7 rounded-lg bg-slate-100 border border-slate-200/80 flex items-center justify-center text-slate-600">
                              {item.sku?.includes("LAP") ? (
                                <Laptop size={14} />
                              ) : item.sku?.includes("SaaS") || item.sku?.includes("TIER") ? (
                                <Cloud size={14} className="text-blue-600" />
                              ) : (
                                <Wrench size={14} className="text-teal-600" />
                              )}
                            </div>
                            <div>
                              <div className="font-semibold text-slate-900 text-xs">
                                {item.product_name}
                              </div>
                              <div className="text-[11px] text-slate-400 font-mono">{item.sku}</div>
                            </div>
                          </div>
                        </TableCell>
                        <TableCell>
                          {isConfigured ? (
                            <span className="inline-flex items-center text-xs font-semibold text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded-full">
                              <Check size={12} className="stroke-[3] mr-1" />
                              Configured {item.configuration_version || "v1.0"}
                            </span>
                          ) : (
                            <span className="inline-flex items-center text-xs text-slate-600">
                              <span className="w-1.5 h-1.5 rounded-full bg-slate-400 mr-1.5" />
                              Standard
                            </span>
                          )}
                        </TableCell>
                        <TableCell>
                          <span className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-700 font-semibold text-[10px] border border-slate-200">
                            {item.billing_type}
                          </span>
                        </TableCell>
                        <TableCell>
                          <input
                            type="number"
                            min={1}
                            value={item.quantity}
                            onChange={(e) => handleQuantityChange(item.id, Number(e.target.value))}
                            className="w-14 px-2 py-1 bg-white border border-slate-200 rounded text-xs text-center font-semibold text-slate-800 focus:outline-none focus:border-blue-500 shadow-2xs"
                          />
                        </TableCell>
                        <TableCell className="font-medium text-slate-800">
                          ${Number(item.unit_price).toLocaleString("en-US", { minimumFractionDigits: 2 })}
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-1">
                            <input
                              type="number"
                              min={0}
                              max={100}
                              value={item.discount_percentage}
                              onChange={(e) => handleDiscountChange(item.id, Number(e.target.value))}
                              className="w-12 px-1.5 py-1 bg-white border border-slate-200 rounded text-xs text-center font-semibold text-amber-700 focus:outline-none focus:border-blue-500 shadow-2xs"
                            />
                            <span className="text-xs font-bold text-amber-600">%</span>
                          </div>
                        </TableCell>
                        <TableCell className="font-bold text-slate-900">
                          ${Number(item.line_total).toLocaleString("en-US", { minimumFractionDigits: 2 })}
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="flex items-center justify-end gap-1">
                            <button
                              onClick={() => alert(`Edit configuration for ${item.product_name}`)}
                              className="p-1 rounded text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors cursor-pointer"
                              title="Edit item"
                            >
                              <Edit size={14} />
                            </button>
                            <button
                              onClick={() => handleRemoveLine(item.id)}
                              className="p-1 rounded text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-colors cursor-pointer"
                              title="Remove item"
                            >
                              <Trash2 size={14} />
                            </button>
                          </div>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </tbody>
              </DataTable>
            </CardContent>
          </Card>
        </div>

        {/* ─── Right Column (4 cols): Sidebar & Metrics ───────────── */}
        <div className="lg:col-span-4 space-y-6">
          <Card data-demo="quotes-summary">
            <CardHeader className="pb-3">
              <div className="flex items-center gap-2">
                <div className="w-7 h-7 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center border border-blue-100">
                  <TrendingUp size={15} />
                </div>
                <CardTitle className="text-sm">Quote Summary</CardTitle>
              </div>
            </CardHeader>
            <CardContent className="space-y-4 pt-2">
              <div className="space-y-2.5 text-xs">
                <div className="flex justify-between items-center text-slate-600">
                  <span>Subtotal</span>
                  <span className="font-semibold text-slate-900">
                    ${subtotal.toLocaleString("en-US", { minimumFractionDigits: 2 })}
                  </span>
                </div>
                <div className="flex justify-between items-center text-slate-600">
                  <span>Discount</span>
                  <span className="font-semibold text-emerald-600">
                    -${discountAmount.toLocaleString("en-US", { minimumFractionDigits: 2 })}
                  </span>
                </div>
                <div className="flex justify-between items-center text-slate-400">
                  <span>Tax (Not included)</span>
                  <span>—</span>
                </div>
              </div>

              <div className="border-t border-slate-100 pt-3 flex justify-between items-baseline">
                <span className="text-xs font-bold text-slate-700">Total (USD)</span>
                <span className="text-xl font-extrabold text-slate-900 tracking-tight">
                  ${totalUSD.toLocaleString("en-US", { minimumFractionDigits: 2 })}
                </span>
              </div>

              {/* Expected Margin Banner Pill */}
              <div className="bg-emerald-50/90 border border-emerald-200/80 rounded-xl p-3 flex items-center justify-between text-xs">
                <div className="flex items-center gap-1.5 text-emerald-800 font-semibold">
                  <TrendingUp size={14} className="text-emerald-600" />
                  <span>Expected Margin</span>
                  <Info size={12} className="text-emerald-500 cursor-pointer" />
                </div>
                <div className="text-right">
                  <div className="font-bold text-emerald-800">{expectedMarginPercent}%</div>
                  <div className="text-[10px] text-emerald-600 font-medium">
                    ${expectedMarginAmount.toLocaleString("en-US", { minimumFractionDigits: 2 })}
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Card 2: Quote Progress */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">Quote Progress</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center gap-5">
                <CircularProgress current={3} total={5} size={70} strokeWidth={6} />
                <div className="space-y-2 text-xs">
                  <div className="flex items-center gap-2 text-slate-700 font-medium">
                    <CheckCircle size={14} className="text-emerald-600" />
                    <span>Customer Selected</span>
                  </div>
                  <div className="flex items-center gap-2 text-slate-700 font-medium">
                    <CheckCircle size={14} className="text-emerald-600" />
                    <span>Products Added</span>
                  </div>
                  <div className="flex items-center gap-2 text-slate-700 font-medium">
                    <CheckCircle size={14} className="text-emerald-600" />
                    <span>Configuration Complete</span>
                  </div>
                  <div className="flex items-center gap-2 text-slate-400">
                    <span className="w-3.5 h-3.5 rounded-full border border-slate-300" />
                    <span>Pricing Calculated</span>
                  </div>
                  <div className="flex items-center gap-2 text-slate-400">
                    <span className="w-3.5 h-3.5 rounded-full border border-slate-300" />
                    <span>Ready to Submit</span>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Card 3: Recent Activity */}
          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between w-full">
                <div className="flex items-center gap-2">
                  <Clock size={15} className="text-slate-500" />
                  <CardTitle className="text-sm">Recent Activity</CardTitle>
                </div>
                <button
                  onClick={() => alert("Viewing audit timeline...")}
                  className="text-xs font-semibold text-blue-600 hover:text-blue-800 transition-colors cursor-pointer"
                >
                  View All
                </button>
              </div>
            </CardHeader>
            <CardContent className="space-y-3.5 pt-1 text-xs">
              <div className="flex items-start gap-3">
                <div className="w-7 h-7 rounded-lg bg-slate-100 flex items-center justify-center text-slate-600 shrink-0 mt-0.5">
                  <Laptop size={14} />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-semibold text-slate-800 leading-tight">Product configured</p>
                  <p className="text-[11px] text-slate-500 truncate">Dell Latitude 7440</p>
                </div>
                <span className="text-[10px] text-slate-400 whitespace-nowrap">2 mins ago</span>
              </div>

              <div className="flex items-start gap-3">
                <div className="w-7 h-7 rounded-lg bg-slate-100 flex items-center justify-center text-slate-600 shrink-0 mt-0.5">
                  <Building size={14} />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-semibold text-slate-800 leading-tight">Customer selected</p>
                  <p className="text-[11px] text-slate-500 truncate">Acme Corporation</p>
                </div>
                <span className="text-[10px] text-slate-400 whitespace-nowrap">5 mins ago</span>
              </div>

              <div className="flex items-start gap-3">
                <div className="w-7 h-7 rounded-lg bg-slate-100 flex items-center justify-center text-slate-600 shrink-0 mt-0.5">
                  <FileText size={14} />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-semibold text-slate-800 leading-tight">Quote created</p>
                  <p className="text-[11px] text-slate-500 truncate">by Aarav lunkad</p>
                </div>
                <span className="text-[10px] text-slate-400 whitespace-nowrap">10 mins ago</span>
              </div>
            </CardContent>
          </Card>

          {/* Card 4: Next Steps Callout */}
          <div className="bg-blue-50/70 border border-blue-100 rounded-xl p-4 shadow-2xs">
            <div className="flex items-center gap-2 text-blue-900 font-bold text-xs mb-3">
              <Sparkles size={15} className="text-blue-600" />
              <span>Next Steps</span>
            </div>
            <div className="space-y-2 text-xs text-slate-700">
              <label className="flex items-center gap-2.5 cursor-pointer">
                <input
                  type="checkbox"
                  defaultChecked
                  className="rounded border-slate-300 text-blue-600 focus:ring-blue-500 w-3.5 h-3.5"
                />
                <span className="font-medium text-slate-700">Review pricing and margins</span>
              </label>
              <label className="flex items-center gap-2.5 cursor-pointer">
                <input
                  type="checkbox"
                  className="rounded border-slate-300 text-blue-600 focus:ring-blue-500 w-3.5 h-3.5"
                />
                <span className="text-slate-600">Add optional products</span>
              </label>
              <label className="flex items-center gap-2.5 cursor-pointer">
                <input
                  type="checkbox"
                  className="rounded border-slate-300 text-blue-600 focus:ring-blue-500 w-3.5 h-3.5"
                />
                <span className="text-slate-600">Generate PDF quote</span>
              </label>
              <label className="flex items-center gap-2.5 cursor-pointer">
                <input
                  type="checkbox"
                  className="rounded border-slate-300 text-blue-600 focus:ring-blue-500 w-3.5 h-3.5"
                />
                <span className="text-slate-600">Submit for approval</span>
              </label>
            </div>
          </div>
        </div>
      </div>

      {/* ─── Modal: Customer Picker ─────────────────────────────── */}
      <Modal
        isOpen={isCustomerModalOpen}
        onClose={() => setIsCustomerModalOpen(false)}
        title="Select Customer"
        description="Choose an existing account from your CRM database."
        maxWidth="lg"
      >
        <div className="space-y-3">
          {customerList.map((cust) => (
            <div
              key={cust.id}
              onClick={() => {
                setSelectedCustomer(cust);
                setIsCustomerModalOpen(false);
              }}
              className="p-3 border border-slate-200 rounded-lg hover:border-blue-500 hover:bg-blue-50/50 cursor-pointer flex items-center justify-between transition-all"
            >
              <div>
                <div className="font-semibold text-xs text-slate-900">{cust.name}</div>
                <div className="text-[11px] text-slate-500">{cust.email || "No email"} • {cust.customer_number || "CUST"}</div>
              </div>
              <Button size="sm" variant="secondary">Select</Button>
            </div>
          ))}
          {customerList.length === 0 && (
            <p className="text-xs text-slate-500 text-center py-4">No customers found.</p>
          )}
        </div>
      </Modal>

      {/* ─── Modal: Product Picker ──────────────────────────────── */}
      <Modal
        isOpen={isProductPickerOpen}
        onClose={() => setIsProductPickerOpen(false)}
        title="Add Products to Quote"
        description="Select products from the catalog to add to this quote."
        maxWidth="xl"
      >
        <div className="space-y-2 max-h-96 overflow-y-auto pr-1">
          {activeProducts.map((prod) => (
            <div
              key={prod.id}
              className="p-3 border border-slate-200 rounded-lg flex items-center justify-between hover:bg-slate-50 transition-colors"
            >
              <div>
                <div className="font-semibold text-xs text-slate-900">{prod.name}</div>
                <div className="text-[11px] text-slate-400 font-mono">
                  {prod.sku} • {prod.billing_type}
                </div>
              </div>
              <div className="flex items-center gap-3">
                <span className="font-bold text-xs text-slate-900">
                  ${Number(prod.base_price).toLocaleString("en-US", { minimumFractionDigits: 2 })}
                </span>
                <Button size="sm" variant="primary" onClick={() => handleAddProduct(prod)}>
                  Add
                </Button>
              </div>
            </div>
          ))}
          {activeProducts.length === 0 && (
            <p className="text-xs text-slate-500 text-center py-4">No active catalog products available.</p>
          )}
        </div>
      </Modal>
    </div>
  );
}
