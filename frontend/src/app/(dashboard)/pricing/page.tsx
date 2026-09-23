"use client";

import React, { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  DollarSign,
  Percent,
  Sliders,
  Settings,
  HelpCircle,
  Plus,
  Trash2,
  X,
  AlertCircle,
  TrendingUp,
  Layers,
  ShieldCheck,
  Scale,
  Calculator as CalcIcon,
  Info,
  Calendar,
  CheckCircle2,
  ArrowRight,
  BookOpen,
  Package
} from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import { useDemoTour } from "@/components/demo/DemoTourProvider";
import { DEMO_LATITUDE_ID } from "@/lib/demoMockData";
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
  Tabs,
  MetricCard
} from "@/components/ui";

interface EnrichedProduct {
  id: number;
  sku: string;
  name: string;
  description?: string | null;
  base_price: string;
  cost_price?: string | null;
  currency: string;
  is_active: boolean;
  billing_type: string;
  category_name?: string | null;
  pricing_method: string;
  markup_percent: string;
  discount_percent?: string;
  status?: string;
  effective_from?: string | null;
  effective_until?: string | null;
  has_tiers: boolean;
}

interface TierConfig {
  min_quantity: number;
  max_quantity: number | null;
  price: string;
}

interface CalculateResponse {
  product_id: number;
  product_name: string;
  sku: string;
  quantity: number;
  pricing_method: string;
  billing_type: string;
  base_unit_price: string;
  discount_percent: string;
  discount_amount: string;
  final_unit_price: string;
  total_price: string;
  unit_cost?: string | null;
  total_cost?: string | null;
  margin_amount?: string | null;
  margin_percentage?: string | null;
  currency: string;
  calculation_breakdown: any[];
}

interface PricingRule {
  id: number;
  name: string;
  rule_type: string;
  is_active: boolean;
  conditions: Record<string, any>;
  actions: Record<string, any>;
  description?: string | null;
  status?: string;
}

export default function PricingEnginePage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const {
    isActive: isDemoActive,
    flags: demoFlags,
    mockPricingProducts,
    mockPricingRules,
    mockPricingWaterfall,
  } = useDemoTour();

  const isSalesRep = user?.role === "sales_rep";
  const isManager = user?.role === "manager";
  const isExecutive = user?.role === "executive" || user?.role === "admin";
  const canOpenConfig = isManager || isExecutive;
  const canEditConfig = isExecutive;

  // Tabs: Overview, Price Lists, Pricing Configurations, Pricing Rules, Calculator
  const [activeTab, setActiveTab] = useState<string>("configurations");

  // Filter & Search
  const [searchQuery, setSearchQuery] = useState("");
  const [methodFilter, setMethodFilter] = useState("ALL");

  // Configuration Modal States
  const [selectedProduct, setSelectedProduct] = useState<EnrichedProduct | null>(null);
  const [isConfigModalOpen, setIsConfigModalOpen] = useState(false);
  const [pricingMethod, setPricingMethod] = useState<string>("STANDARD");
  const [markupPercent, setMarkupPercent] = useState<string>("0.00");
  const [tieredMode, setTieredMode] = useState<string>("VOLUME");
  const [tiers, setTiers] = useState<TierConfig[]>([
    { min_quantity: 1, max_quantity: null, price: "0.00" }
  ]);
  const [configError, setConfigError] = useState<string | null>(null);

  // Live Price Preview states in Modal
  const [previewQuantity, setPreviewQuantity] = useState<number>(1);
  const [previewResult, setPreviewResult] = useState<CalculateResponse | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [isPreviewLoading, setIsPreviewLoading] = useState(false);

  // Interactive Calculator Tab States
  const [calcProductId, setCalcProductId] = useState<string>("");
  const [calcQuantity, setCalcQuantity] = useState<number>(10);
  const [calcDiscount, setCalcDiscount] = useState<string>("5.00");
  const [calcResult, setCalcResult] = useState<CalculateResponse | null>(null);
  const [calcError, setCalcError] = useState<string | null>(null);
  const [isCalcLoading, setIsCalcLoading] = useState(false);

  // Queries
  const { data: liveEnrichedProducts = [], isLoading: isLoadingLiveProducts } = useQuery<EnrichedProduct[]>({
    queryKey: ["enriched-products"],
    queryFn: () => api.get<EnrichedProduct[]>("/pricing/products"),
    enabled: !isDemoActive,
  });
  const enrichedProducts = isDemoActive ? (mockPricingProducts as EnrichedProduct[]) : liveEnrichedProducts;
  const isLoadingProducts = isDemoActive ? false : isLoadingLiveProducts;

  const { data: liveRules = [] } = useQuery<PricingRule[]>({
    queryKey: ["pricing-rules"],
    queryFn: () => api.get<PricingRule[]>("/pricing/rules"),
    enabled: !isDemoActive,
  });
  const rules = isDemoActive ? (mockPricingRules as PricingRule[]) : liveRules;

  const { data: livePriceBooks = [] } = useQuery<any[]>({
    queryKey: ["price-books"],
    queryFn: () => api.get<any[]>("/price-books"),
    enabled: !isDemoActive,
  });
  const priceBooks = isDemoActive ? [{ id: 1, name: "Standard Enterprise", is_active: true }] : livePriceBooks;

  // Set default product for calculator
  useEffect(() => {
    if (enrichedProducts.length > 0 && !calcProductId) {
      setCalcProductId(enrichedProducts[0].id.toString());
    }
  }, [enrichedProducts, calcProductId]);

  // Mutations
  const updateConfigMutation = useMutation({
    mutationFn: (payload: { id: number; data: any }) => {
      if (isDemoActive) return Promise.resolve({});
      return api.post(`/pricing/products/${payload.id}/configuration`, payload.data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["enriched-products"] });
      setIsConfigModalOpen(false);
      alert("Pricing configuration saved successfully!");
    },
    onError: (err: any) => {
      setConfigError(err?.detail || "Failed to update pricing configuration.");
    }
  });

  const activateMutation = useMutation({
    mutationFn: (id: number) => {
      if (isDemoActive) return Promise.resolve({});
      return api.post(`/pricing/products/${id}/configuration/activate`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["enriched-products"] });
    }
  });

  const deactivateMutation = useMutation({
    mutationFn: (id: number) => {
      if (isDemoActive) return Promise.resolve({});
      return api.post(`/pricing/products/${id}/configuration/deactivate`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["enriched-products"] });
    }
  });

  // Run Calculator
  const handleRunCalculator = async () => {
    if (!calcProductId) return;
    if (isDemoActive) {
      setCalcResult(mockPricingWaterfall as CalculateResponse);
      setIsCalcLoading(false);
      return;
    }
    setIsCalcLoading(true);
    setCalcError(null);
    try {
      const selected = enrichedProducts.find((p) => p.id === parseInt(calcProductId));
      const payload = {
        product_id: parseInt(calcProductId),
        quantity: calcQuantity,
        pricing_method: selected?.pricing_method || "STANDARD",
        discount_percent: parseFloat(calcDiscount) || 0,
      };
      const res = await api.post<CalculateResponse>("/pricing/calculate", payload);
      setCalcResult(res);
    } catch (err: any) {
      setCalcError(err?.detail || "Calculation failed.");
    } finally {
      setIsCalcLoading(false);
    }
  };

  useEffect(() => {
    if (isDemoActive && demoFlags.showPricingWaterfall) {
      setActiveTab("calculator");
      setCalcProductId(String(DEMO_LATITUDE_ID));
      setCalcQuantity(10);
      setCalcDiscount("10.00");
      setCalcResult(mockPricingWaterfall as CalculateResponse);
      return;
    }
    if (isDemoActive && demoFlags.pricingTab === "configurations") {
      setActiveTab("configurations");
    }
  }, [isDemoActive, demoFlags.showPricingWaterfall, demoFlags.pricingTab, mockPricingWaterfall]);

  useEffect(() => {
    if (isDemoActive) return;
    if (calcProductId) {
      handleRunCalculator();
    }
  }, [calcProductId, calcQuantity, calcDiscount, isDemoActive]);

  // Filtered Products
  const filteredProducts = enrichedProducts.filter((p) => {
    const matchesSearch =
      searchQuery === "" ||
      p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      p.sku.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesMethod = methodFilter === "ALL" || p.pricing_method === methodFilter;
    return matchesSearch && matchesMethod;
  });

  const pageTabs = [
    { id: "overview", label: "Overview", icon: <TrendingUp size={14} /> },
    { id: "pricelists", label: "Price Lists", icon: <BookOpen size={14} />, count: priceBooks.length },
    { id: "configurations", label: "Pricing Configurations", icon: <DollarSign size={14} />, count: enrichedProducts.length },
    { id: "rules", label: "Pricing Rules", icon: <Scale size={14} />, count: rules.length },
    { id: "calculator", label: "Calculator", icon: <CalcIcon size={14} /> },
  ];

  return (
    <div className="space-y-6">
      {/* ─── Page Header ────────────────────────────────────────── */}
      <div data-demo="pricing-header">
      <PageHeader
        title="Pricing Engine"
        description="Configure pricing methods, price lists and pricing rules."
      />
      </div>

      {/* ─── Navigation Tabs ────────────────────────────────────── */}
      <div className="bg-white px-4 border border-slate-200/80 rounded-xl shadow-xs">
        <Tabs tabs={pageTabs} activeTab={activeTab} onChange={setActiveTab} />
      </div>

      {/* ─── TAB 1: OVERVIEW ────────────────────────────────────── */}
      {activeTab === "overview" && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <MetricCard
              title="Configured Products"
              value={enrichedProducts.length}
              subtext="Enriched catalog items"
              icon={<Package size={18} />}
            />
            <MetricCard
              title="Active Price Books"
              value={priceBooks.length || 1}
              subtext="Standard Enterprise Catalog"
              icon={<BookOpen size={18} />}
            />
            <MetricCard
              title="Dynamic Rules"
              value={rules.length}
              subtext="Discount policies"
              icon={<Scale size={18} />}
            />
            <MetricCard
              title="Average Target Margin"
              value="34.2%"
              subtext="Across active quotes"
              icon={<TrendingUp size={18} />}
            />
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Supported Enterprise Pricing Methods</CardTitle>
              <CardDescription>
                Backend-authoritative calculation rules evaluated by the CPQ Cognitive engine.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
                <div className="p-4 rounded-xl border border-slate-200 bg-slate-50/50 space-y-1.5">
                  <div className="font-bold text-slate-900 flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-blue-600" />
                    Standard / List Pricing
                  </div>
                  <p className="text-slate-500 leading-relaxed">
                    Direct multiplication of units by base catalog price. Baseline configuration for off-the-shelf items.
                  </p>
                </div>

                <div className="p-4 rounded-xl border border-slate-200 bg-slate-50/50 space-y-1.5">
                  <div className="font-bold text-slate-900 flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-emerald-600" />
                    Tiered Volume & Graduated
                  </div>
                  <p className="text-slate-500 leading-relaxed">
                    Volume brackets dynamically scale unit prices. Cumulative graduated pricing calculates brackets sequentially.
                  </p>
                </div>

                <div className="p-4 rounded-xl border border-slate-200 bg-slate-50/50 space-y-1.5">
                  <div className="font-bold text-slate-900 flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-purple-600" />
                    Cost-Plus Markup
                  </div>
                  <p className="text-slate-500 leading-relaxed">
                    Enforces corporate gross margin targets by automatically applying markup multipliers atop supplier unit cost.
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* ─── TAB 2: PRICE LISTS ─────────────────────────────────── */}
      {activeTab === "pricelists" && (
        <Card>
          <CardHeader>
            <CardTitle>Enterprise Price Books</CardTitle>
            <CardDescription>Multi-currency price lists for regional and customer tier pricing.</CardDescription>
          </CardHeader>
          <CardContent className="p-0">
            <DataTable className="border-0 rounded-none">
              <TableHead>
                <TableRow>
                  <TableHeader>Price Book Name</TableHeader>
                  <TableHeader>Currency</TableHeader>
                  <TableHeader>Type</TableHeader>
                  <TableHeader>Status</TableHeader>
                  <TableHeader>Effective Dates</TableHeader>
                </TableRow>
              </TableHead>
              <tbody>
                {priceBooks.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={5} className="text-center py-8 text-slate-500">
                      Standard Global USD Price Book (Active)
                    </TableCell>
                  </TableRow>
                ) : (
                  priceBooks.map((pb) => (
                    <TableRow key={pb.id}>
                      <TableCell className="font-semibold text-slate-900">{pb.name}</TableCell>
                      <TableCell className="font-mono text-slate-600">{pb.currency || "USD"}</TableCell>
                      <TableCell>{pb.is_standard ? "Standard Default" : "Custom Tier"}</TableCell>
                      <TableCell>
                        <StatusBadge status={pb.is_active ? "ACTIVE" : "INACTIVE"} />
                      </TableCell>
                      <TableCell className="text-slate-500">2026-01-01 to 2026-12-31</TableCell>
                    </TableRow>
                  ))
                )}
              </tbody>
            </DataTable>
          </CardContent>
        </Card>
      )}

      {/* ─── TAB 3: PRICING CONFIGURATIONS ──────────────────────── */}
      {activeTab === "configurations" && (
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-white p-3 rounded-xl border border-slate-200/80 shadow-xs">
            <SearchBar
              value={searchQuery}
              onChangeValue={setSearchQuery}
              placeholder="Search product SKU or name..."
              className="w-full sm:w-80"
            />
            <div className="flex items-center gap-2">
              <FilterSelect
                value={methodFilter}
                onChange={(e) => setMethodFilter(e.target.value)}
                label="Pricing Method"
              >
                <option value="ALL">All Methods</option>
                <option value="STANDARD">Standard</option>
                <option value="TIERED">Tiered</option>
                <option value="BLOCK">Block</option>
                <option value="COST_PLUS_MARKUP">Cost Plus</option>
              </FilterSelect>
            </div>
          </div>

          <Card data-demo="pricing-table">
            <DataTable className="border-0 rounded-none">
              <TableHead>
                <TableRow>
                  <TableHeader>Product</TableHeader>
                  <TableHeader>SKU</TableHeader>
                  <TableHeader>Billing Type</TableHeader>
                  <TableHeader>Pricing Method</TableHeader>
                  <TableHeader>Base Price</TableHeader>
                  <TableHeader>Status</TableHeader>
                  <TableHeader>Effective Date</TableHeader>
                  <TableHeader className="text-right">Actions</TableHeader>
                </TableRow>
              </TableHead>
              <tbody>
                {isLoadingProducts ? (
                  <TableRow>
                    <TableCell colSpan={8} className="text-center py-12 text-slate-500">
                      Loading pricing configurations...
                    </TableCell>
                  </TableRow>
                ) : filteredProducts.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={8} className="text-center py-12 text-slate-500">
                      No pricing configurations found.
                    </TableCell>
                  </TableRow>
                ) : (
                  filteredProducts.map((p) => (
                    <TableRow
                      key={p.id}
                      data-demo={p.sku === "DEV-LAP-001" ? "pricing-latitude" : undefined}
                    >
                      <TableCell className="font-semibold text-slate-900">{p.name}</TableCell>
                      <TableCell className="font-mono text-slate-500 text-[11px]">{p.sku}</TableCell>
                      <TableCell>
                        <span className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-700 text-[10px] font-semibold">
                          {p.billing_type}
                        </span>
                      </TableCell>
                      <TableCell>
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase bg-blue-50 text-blue-700 border border-blue-200">
                          {p.pricing_method || "STANDARD"}
                        </span>
                      </TableCell>
                      <TableCell className="font-bold text-slate-900">
                        ${Number(p.base_price).toLocaleString("en-US", { minimumFractionDigits: 2 })}
                      </TableCell>
                      <TableCell>
                        <StatusBadge status={p.is_active ? "ACTIVE" : "INACTIVE"} />
                      </TableCell>
                      <TableCell className="text-slate-500 text-[11px]">
                        {p.effective_from || "Always Active"}
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => {
                            setSelectedProduct(p);
                            setPricingMethod(p.pricing_method || "STANDARD");
                            setMarkupPercent(p.markup_percent || "0.00");
                            setIsConfigModalOpen(true);
                          }}
                        >
                          Configure
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </tbody>
            </DataTable>
          </Card>
        </div>
      )}

      {/* ─── TAB 4: PRICING RULES ───────────────────────────────── */}
      {activeTab === "rules" && (
        <Card>
          <CardHeader>
            <CardTitle>Dynamic Pricing Rules</CardTitle>
            <CardDescription>Rules applied conditionally based on customer segment, volume, or geometry.</CardDescription>
          </CardHeader>
          <CardContent className="p-0">
            <DataTable className="border-0 rounded-none">
              <TableHead>
                <TableRow>
                  <TableHeader>Rule Name</TableHeader>
                  <TableHeader>Type</TableHeader>
                  <TableHeader>Status</TableHeader>
                  <TableHeader>Description</TableHeader>
                </TableRow>
              </TableHead>
              <tbody>
                {rules.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={4} className="text-center py-8 text-slate-500">
                      Enterprise Tier Rule: 10% volume discount on hardware orders exceeding 5 units.
                    </TableCell>
                  </TableRow>
                ) : (
                  rules.map((r) => (
                    <TableRow key={r.id}>
                      <TableCell className="font-semibold text-slate-900">{r.name}</TableCell>
                      <TableCell className="font-mono text-slate-600">{r.rule_type}</TableCell>
                      <TableCell>
                        <StatusBadge status={r.is_active ? "ACTIVE" : "INACTIVE"} />
                      </TableCell>
                      <TableCell className="text-slate-500">{r.description || "Automatic rule"}</TableCell>
                    </TableRow>
                  ))
                )}
              </tbody>
            </DataTable>
          </CardContent>
        </Card>
      )}

      {/* ─── TAB 5: CALCULATOR & WATERFALL ──────────────────────── */}
      {activeTab === "calculator" && (
        <div data-demo="pricing-calculator" className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          {/* Step 1: Input section (4 cols) */}
          <div className="lg:col-span-4">
            <Card>
              <CardHeader>
                <div className="flex items-center gap-2">
                  <div className="w-6 h-6 rounded-full bg-blue-600 text-white flex items-center justify-center text-xs font-bold">
                    1
                  </div>
                  <CardTitle className="text-sm">Input Parameters</CardTitle>
                </div>
              </CardHeader>
              <CardContent className="space-y-4 text-xs">
                <div>
                  <label className="font-semibold text-slate-700 block mb-1">Select Product</label>
                  <select
                    value={calcProductId}
                    onChange={(e) => setCalcProductId(e.target.value)}
                    className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-slate-800 focus:outline-none focus:border-blue-500"
                  >
                    {enrichedProducts.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name} ({p.sku}) - ${Number(p.base_price).toFixed(2)}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="font-semibold text-slate-700 block mb-1">Quantity</label>
                  <input
                    type="number"
                    min={1}
                    value={calcQuantity}
                    onChange={(e) => setCalcQuantity(parseInt(e.target.value) || 1)}
                    className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-slate-800 focus:outline-none focus:border-blue-500 font-semibold"
                  />
                </div>

                <div>
                  <label className="font-semibold text-slate-700 block mb-1">Manual Discount (%)</label>
                  <input
                    type="number"
                    min={0}
                    max={100}
                    value={calcDiscount}
                    onChange={(e) => setCalcDiscount(e.target.value)}
                    className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-slate-800 focus:outline-none focus:border-blue-500 font-semibold text-amber-700"
                  />
                </div>

                <Button
                  variant="primary"
                  className="w-full mt-2"
                  onClick={handleRunCalculator}
                  isLoading={isCalcLoading}
                >
                  Recalculate Price
                </Button>
              </CardContent>
            </Card>
          </div>

          {/* Step 2: Price Waterfall (4 cols) */}
          <div className="lg:col-span-4">
            <Card>
              <CardHeader>
                <div className="flex items-center gap-2">
                  <div className="w-6 h-6 rounded-full bg-blue-600 text-white flex items-center justify-center text-xs font-bold">
                    2
                  </div>
                  <CardTitle className="text-sm">Price Waterfall</CardTitle>
                </div>
              </CardHeader>
              <CardContent className="space-y-3 text-xs">
                {calcResult ? (
                  <div className="space-y-3">
                    <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 flex justify-between items-center">
                      <div>
                        <span className="font-semibold text-slate-800 block">1. Catalog Base Price</span>
                        <span className="text-[11px] text-slate-400">Standard unit rate</span>
                      </div>
                      <span className="font-bold text-slate-900">${calcResult.base_unit_price}</span>
                    </div>

                    <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 flex justify-between items-center">
                      <div>
                        <span className="font-semibold text-slate-800 block">2. Units Evaluated</span>
                        <span className="text-[11px] text-slate-400">Total volume bracket</span>
                      </div>
                      <span className="font-bold text-slate-900">× {calcResult.quantity}</span>
                    </div>

                    <div className="p-3 bg-amber-50 rounded-lg border border-amber-200 flex justify-between items-center">
                      <div>
                        <span className="font-semibold text-amber-900 block">3. Line Discount</span>
                        <span className="text-[11px] text-amber-700">{calcResult.discount_percent}% reduction</span>
                      </div>
                      <span className="font-bold text-amber-700">-${calcResult.discount_amount}</span>
                    </div>

                    <div className="p-3 bg-blue-50 rounded-lg border border-blue-200 flex justify-between items-center">
                      <div>
                        <span className="font-semibold text-blue-900 block">4. Effective Unit Price</span>
                        <span className="text-[11px] text-blue-700">Net price per seat/unit</span>
                      </div>
                      <span className="font-bold text-blue-700">${calcResult.final_unit_price}</span>
                    </div>
                  </div>
                ) : (
                  <p className="text-slate-400 py-6 text-center">Enter inputs to view calculation waterfall.</p>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Step 3: Final Result (4 cols) */}
          <div className="lg:col-span-4">
            <Card>
              <CardHeader>
                <div className="flex items-center gap-2">
                  <div className="w-6 h-6 rounded-full bg-emerald-600 text-white flex items-center justify-center text-xs font-bold">
                    3
                  </div>
                  <CardTitle className="text-sm">Final Result</CardTitle>
                </div>
              </CardHeader>
              <CardContent className="space-y-4 text-xs">
                {calcResult ? (
                  <div className="space-y-4">
                    <div className="p-4 bg-slate-900 text-white rounded-xl">
                      <span className="text-[10px] uppercase font-semibold text-slate-400 block mb-1">
                        Total Quote Price (USD)
                      </span>
                      <div className="text-2xl font-bold tracking-tight">
                        ${Number(calcResult.total_price).toLocaleString("en-US", { minimumFractionDigits: 2 })}
                      </div>
                    </div>

                    {calcResult.margin_percentage && (
                      <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-xl flex items-center justify-between">
                        <div className="flex items-center gap-1.5 text-emerald-800 font-semibold">
                          <TrendingUp size={14} className="text-emerald-600" />
                          <span>Expected Gross Margin</span>
                        </div>
                        <span className="font-bold text-emerald-800">{calcResult.margin_percentage}%</span>
                      </div>
                    )}

                    <div className="p-3 bg-slate-50 rounded-xl border border-slate-100 text-slate-500 space-y-1">
                      <div className="flex justify-between">
                        <span>Method:</span>
                        <span className="font-semibold text-slate-800">{calcResult.pricing_method}</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Currency:</span>
                        <span className="font-semibold text-slate-800">{calcResult.currency}</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Billing:</span>
                        <span className="font-semibold text-slate-800">{calcResult.billing_type}</span>
                      </div>
                    </div>
                  </div>
                ) : (
                  <p className="text-slate-400 py-6 text-center">No calculation result yet.</p>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      )}

      {/* ─── MODAL: PRICING CONFIGURATION ───────────────────────── */}
      {isConfigModalOpen && selectedProduct && (
        <Modal
          isOpen={isConfigModalOpen}
          onClose={() => setIsConfigModalOpen(false)}
          title={`Configure Pricing: ${selectedProduct.name}`}
          description={`Set up backend calculation formulas for SKU ${selectedProduct.sku}.`}
          maxWidth="lg"
        >
          <div className="space-y-4 text-xs">
            <div>
              <label className="font-semibold text-slate-700 block mb-1">Pricing Method</label>
              <select
                value={pricingMethod}
                onChange={(e) => setPricingMethod(e.target.value)}
                className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-slate-800 focus:outline-none focus:border-blue-500 font-medium"
              >
                <option value="STANDARD">Standard List Price</option>
                <option value="LINE_DISCOUNT">Line Discount</option>
                <option value="TIERED">Tiered Volume Pricing</option>
                <option value="BLOCK">Block Bracket Pricing</option>
                <option value="COST_PLUS_MARKUP">Cost Plus Markup</option>
              </select>
            </div>

            {pricingMethod === "COST_PLUS_MARKUP" && (
              <div>
                <label className="font-semibold text-slate-700 block mb-1">Target Markup (%)</label>
                <input
                  type="number"
                  value={markupPercent}
                  onChange={(e) => setMarkupPercent(e.target.value)}
                  className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-slate-800 focus:outline-none focus:border-blue-500"
                />
              </div>
            )}

            {configError && (
              <div className="p-3 bg-rose-50 border border-rose-200 rounded-lg text-rose-700">
                {configError}
              </div>
            )}

            <div className="flex justify-end gap-2.5 pt-4 border-t border-slate-100">
              <Button variant="secondary" onClick={() => setIsConfigModalOpen(false)}>
                Cancel
              </Button>
              <Button
                variant="primary"
                onClick={() =>
                  updateConfigMutation.mutate({
                    id: selectedProduct.id,
                    data: {
                      pricing_method: pricingMethod,
                      markup_percent: parseFloat(markupPercent) || 0,
                    }
                  })
                }
                isLoading={updateConfigMutation.isPending}
              >
                Save Configuration
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
