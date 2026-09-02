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
  Calculator,
  Info
} from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";

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
  currency: string;
  calculation_breakdown: any[];
}

export default function PricingEnginePage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();

  // Toast feedback state
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" } | null>(null);

  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(null), 3000);
      return () => clearTimeout(timer);
    }
  }, [toast]);

  // Role permissions
  const isSalesRep = user?.role === "sales_rep";
  const isManager = user?.role === "manager";
  const isExecutive = user?.role === "executive" || user?.role === "admin";
  
  const canOpenConfig = isManager || isExecutive;
  const canEditConfig = isExecutive;

  // Navigation states: "config" or "preview"
  const [activeTab, setActiveTab] = useState<"config" | "preview">("config");

  // --- Configuration Manager States ---
  const [selectedProduct, setSelectedProduct] = useState<EnrichedProduct | null>(null);
  const [isConfigModalOpen, setIsConfigModalOpen] = useState(false);
  const [pricingMethod, setPricingMethod] = useState<string>("STANDARD");
  const [markupPercent, setMarkupPercent] = useState<string>("0.00");
  const [tieredMode, setTieredMode] = useState<string>("VOLUME");
  const [tiers, setTiers] = useState<TierConfig[]>([
    { min_quantity: 1, max_quantity: null, price: "0.00" }
  ]);
  const [configError, setConfigError] = useState<string | null>(null);

  // States to track initial pricing configuration to detect unsaved changes
  const [initialPricingMethod, setInitialPricingMethod] = useState<string>("STANDARD");
  const [initialMarkupPercent, setInitialMarkupPercent] = useState<string>("0.00");
  const [initialTieredMode, setInitialTieredMode] = useState<string>("VOLUME");
  const [initialTiers, setInitialTiers] = useState<TierConfig[]>([]);
  const [isDiscardConfirmOpen, setIsDiscardConfirmOpen] = useState(false);

  // Live Price Preview states inside the modal
  const [previewQuantity, setPreviewQuantity] = useState<number>(1);
  const [previewResult, setPreviewResult] = useState<CalculateResponse | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [isPreviewLoading, setIsPreviewLoading] = useState(false);

  // --- Interactive Calculator (Price Preview) States ---
  const [calcProductId, setCalcProductId] = useState<string>("");
  const [calcQuantity, setCalcQuantity] = useState<number>(1);
  const [calcMethod, setCalcMethod] = useState<string>("STANDARD");
  const [calcTieredMode, setCalcTieredMode] = useState<string>("VOLUME");
  const [calcDiscount, setCalcDiscount] = useState<string>("0.00");
  const [calcResult, setCalcResult] = useState<CalculateResponse | null>(null);
  const [calcError, setCalcError] = useState<string | null>(null);

  // Query: enriched products list
  const { data: products = [], isLoading, isError, refetch } = useQuery<EnrichedProduct[]>({
    queryKey: ["enriched_products"],
    queryFn: () => api.get<EnrichedProduct[]>("/pricing/products")
  });

  // Autofill pricing method in calculator tab when selected product changes
  useEffect(() => {
    if (calcProductId) {
      const prod = products.find((p) => p.id.toString() === calcProductId);
      if (prod) {
        setCalcMethod(prod.pricing_method);
      }
    }
  }, [calcProductId, products]);

  // Tiers Query
  const fetchTiers = async (productId: number) => {
    try {
      const res = await api.get<any[]>(`/pricing/products/${productId}/tiers`);
      if (res && res.length > 0) {
        const formatted = res.map((t) => ({
          min_quantity: t.min_quantity,
          max_quantity: t.max_quantity,
          price: parseFloat(t.price).toFixed(2)
        }));
        setTiers(formatted);
        setInitialTiers(formatted);
        if (res[0].tiered_mode) {
          setTieredMode(res[0].tiered_mode);
          setInitialTieredMode(res[0].tiered_mode);
        } else {
          setTieredMode("VOLUME");
          setInitialTieredMode("VOLUME");
        }
      } else {
        const defTiers = [{ min_quantity: 1, max_quantity: null, price: "0.00" }];
        setTiers(defTiers);
        setInitialTiers(defTiers);
        setTieredMode("VOLUME");
        setInitialTieredMode("VOLUME");
      }
    } catch (err) {
      const defTiers = [{ min_quantity: 1, max_quantity: null, price: "0.00" }];
      setTiers(defTiers);
      setInitialTiers(defTiers);
      setTieredMode("VOLUME");
      setInitialTieredMode("VOLUME");
    }
  };

  // Mutations
  const configMutation = useMutation({
    mutationFn: async (payload: {
      productId: number;
      method: string;
      markup: number;
      tiers?: any[];
    }) => {
      await api.post(`/pricing/products/${payload.productId}/configuration`, {
        pricing_method: payload.method,
        markup_percent: payload.markup
      });

      if (payload.method === "TIERED" || payload.method === "BLOCK") {
        if (payload.tiers) {
          await api.post(`/pricing/products/${payload.productId}/tiers`, payload.tiers);
        }
      } else {
        try {
          await api.delete(`/pricing/products/${payload.productId}/tiers`);
        } catch (e) {}
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["enriched_products"] });
      setIsConfigModalOpen(false);
      setSelectedProduct(null);
      setToast({ message: "Pricing configuration saved successfully.", type: "success" });
    },
    onError: (err: any) => {
      const msg = err.detail || "Failed to save pricing configuration.";
      setConfigError(msg);
      setToast({ message: msg, type: "error" });
    }
  });

  const archiveMutation = useMutation({
    mutationFn: (productId: number) => api.patch(`/products/${productId}/archive`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["enriched_products"] });
    }
  });

  const restoreMutation = useMutation({
    mutationFn: (productId: number) => api.patch(`/products/${productId}/restore`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["enriched_products"] });
    }
  });

  const calculateMutation = useMutation({
    mutationFn: (payload: any) => api.post<CalculateResponse>("/pricing/calculate", payload),
    onSuccess: (data) => {
      setCalcResult(data);
      setCalcError(null);
    },
    onError: (err: any) => {
      setCalcResult(null);
      setCalcError(err.detail || "Pricing calculation failed. Verify quantity or pricing configurations.");
    }
  });

  // Event handlers
  const handleOpenConfig = (prod: EnrichedProduct) => {
    setSelectedProduct(prod);
    setPricingMethod(prod.pricing_method);
    setMarkupPercent(parseFloat(prod.markup_percent).toFixed(2));
    setInitialPricingMethod(prod.pricing_method);
    setInitialMarkupPercent(parseFloat(prod.markup_percent).toFixed(2));
    setTieredMode("VOLUME");
    setInitialTieredMode("VOLUME");
    setPreviewQuantity(1);
    setPreviewResult(null);
    setPreviewError(null);
    setConfigError(null);
    setIsConfigModalOpen(true);
    fetchTiers(prod.id);
  };

  // Helper to detect unsaved modifications
  const hasUnsavedChanges =
    pricingMethod !== initialPricingMethod ||
    markupPercent !== initialMarkupPercent ||
    tieredMode !== initialTieredMode ||
    JSON.stringify(tiers) !== JSON.stringify(initialTiers);

  // Unsaved changes confirmation / discard handlers
  const handleCancelOrClose = () => {
    if (hasUnsavedChanges) {
      setIsDiscardConfirmOpen(true);
    } else {
      setIsConfigModalOpen(false);
      setSelectedProduct(null);
    }
  };

  // Trigger preview calculation via the backend API when inputs in the modal change
  useEffect(() => {
    if (!isConfigModalOpen || !selectedProduct) {
      setPreviewResult(null);
      setPreviewError(null);
      return;
    }

    const runPreviewCalculation = async () => {
      if (previewQuantity <= 0) {
        setPreviewError("Quantity must be a positive integer greater than zero.");
        setPreviewResult(null);
        return;
      }

      const discountNum = parseFloat(markupPercent);
      if (pricingMethod === "LINE_DISCOUNT") {
        if (isNaN(discountNum) || discountNum < 0 || discountNum > 100) {
          setPreviewError("Discount percentage must be between 0 and 100.");
          setPreviewResult(null);
          return;
        }
      }

      if (pricingMethod === "COST_PLUS_MARKUP") {
        if (isNaN(discountNum) || discountNum < 0) {
          setPreviewError("Markup percentage must be a positive number.");
          setPreviewResult(null);
          return;
        }
      }

      if (pricingMethod === "TIERED" || pricingMethod === "BLOCK") {
        for (let i = 0; i < tiers.length; i++) {
          const t = tiers[i];
          const priceNum = parseFloat(t.price);
          if (isNaN(priceNum) || priceNum < 0) {
            setPreviewError(`Tier ${i + 1} has an invalid price.`);
            setPreviewResult(null);
            return;
          }
          if (t.max_quantity !== null && t.max_quantity < t.min_quantity) {
            setPreviewError(`Tier ${i + 1} max quantity cannot be less than its min quantity.`);
            setPreviewResult(null);
            return;
          }
          if (t.max_quantity === null && i < tiers.length - 1) {
            setPreviewError("Only the final tier can be set to unlimited.");
            setPreviewResult(null);
            return;
          }
        }
      }

      setIsPreviewLoading(true);
      setPreviewError(null);
      try {
        const payload: any = {
          product_id: selectedProduct.id,
          quantity: previewQuantity,
          pricing_method: pricingMethod,
          discount_percent: pricingMethod === "LINE_DISCOUNT" ? (parseFloat(markupPercent) || 0) : 0,
          tiered_mode: pricingMethod === "TIERED" ? tieredMode : null,
          custom_markup_percent: (pricingMethod === "COST_PLUS_MARKUP" || pricingMethod === "LINE_DISCOUNT") ? (parseFloat(markupPercent) || 0) : null,
          custom_tiers: (pricingMethod === "TIERED" || pricingMethod === "BLOCK") ? tiers.map(t => ({
            min_quantity: t.min_quantity,
            max_quantity: t.max_quantity,
            price: parseFloat(t.price) || 0,
            pricing_method: pricingMethod,
            tiered_mode: pricingMethod === "TIERED" ? tieredMode : null
          })) : null
        };

        const data = await api.post<CalculateResponse>("/pricing/calculate", payload);
        setPreviewResult(data);
        setPreviewError(null);
      } catch (err: any) {
        setPreviewResult(null);
        setPreviewError(err.detail || "Pricing calculation preview failed.");
      } finally {
        setIsPreviewLoading(false);
      }
    };

    const timer = setTimeout(() => {
      runPreviewCalculation();
    }, 250);

    return () => clearTimeout(timer);
  }, [isConfigModalOpen, selectedProduct, pricingMethod, markupPercent, tiers, tieredMode, previewQuantity]);

  const handleAddTier = () => {
    const lastTier = tiers[tiers.length - 1];
    if (lastTier.max_quantity === null) {
      setConfigError("Please define a maximum quantity for the last tier before adding a new range.");
      return;
    }
    setConfigError(null);
    setTiers([
      ...tiers,
      {
        min_quantity: lastTier.max_quantity + 1,
        max_quantity: null,
        price: "0.00"
      }
    ]);
  };

  const handleRemoveTier = (index: number) => {
    if (tiers.length === 1) return;
    const newTiers = [...tiers];
    newTiers.splice(index, 1);
    
    let currentMin = 1;
    const adjusted = newTiers.map((t, idx) => {
      const min = currentMin;
      const isLast = idx === newTiers.length - 1;
      const max = isLast ? null : (t.max_quantity && t.max_quantity >= min ? t.max_quantity : min + 9);
      if (max !== null) {
        currentMin = max + 1;
      }
      return { ...t, min_quantity: min, max_quantity: max };
    });
    setTiers(adjusted);
  };

  const handleTierChange = (index: number, field: keyof TierConfig, value: string) => {
    setConfigError(null);
    const newTiers = [...tiers];
    if (field === "price") {
      newTiers[index].price = value;
    } else if (field === "max_quantity") {
      const maxVal = value === "" ? null : parseInt(value, 10);
      newTiers[index].max_quantity = maxVal;
      
      if (maxVal !== null && index < newTiers.length - 1) {
        let currentMin = maxVal + 1;
        for (let i = index + 1; i < newTiers.length; i++) {
          newTiers[i].min_quantity = currentMin;
          const nextMax = newTiers[i].max_quantity;
          if (nextMax !== null) {
            if (nextMax < currentMin) {
              newTiers[i].max_quantity = currentMin + 9;
            }
            currentMin = (newTiers[i].max_quantity || 0) + 1;
          }
        }
      }
    }
    setTiers(newTiers);
  };

  const handleSave = () => {
    if (!selectedProduct) return;
    
    if (pricingMethod === "COST_PLUS_MARKUP") {
      if (!selectedProduct.cost_price) {
        setConfigError("This product must have a valid cost configured in the catalog to use Cost + Markup.");
        return;
      }
      const markupNum = parseFloat(markupPercent);
      if (isNaN(markupNum) || markupNum < 0) {
        setConfigError("Markup percentage must be a positive number.");
        return;
      }
    }

    let tierPayload = null;
    if (pricingMethod === "TIERED" || pricingMethod === "BLOCK") {
      for (let i = 0; i < tiers.length; i++) {
        const t = tiers[i];
        const priceNum = parseFloat(t.price);
        if (isNaN(priceNum) || priceNum < 0) {
          setConfigError(`Tier ${i + 1} has an invalid price.`);
          return;
        }
        if (t.max_quantity !== null && t.max_quantity < t.min_quantity) {
          setConfigError(`Tier ${i + 1} max quantity cannot be less than its min quantity.`);
          return;
        }
        if (t.max_quantity === null && i < tiers.length - 1) {
          setConfigError("Only the final tier can be set to unlimited.");
          return;
        }
      }
      
      tierPayload = tiers.map((t) => ({
        min_quantity: t.min_quantity,
        max_quantity: t.max_quantity,
        price: parseFloat(t.price),
        pricing_method: pricingMethod,
        tiered_mode: pricingMethod === "TIERED" ? tieredMode : null
      }));
    }

    configMutation.mutate({
      productId: selectedProduct.id,
      method: pricingMethod,
      markup: parseFloat(markupPercent) || 0,
      tiers: tierPayload || undefined
    });
  };

  const handleCalculate = (e: React.FormEvent) => {
    e.preventDefault();
    setCalcError(null);
    if (!calcProductId) {
      setCalcError("Please select a product.");
      return;
    }
    if (calcQuantity <= 0) {
      setCalcError("Quantity must be a positive integer greater than zero.");
      return;
    }
    const discountNum = parseFloat(calcDiscount);
    if (calcMethod === "LINE_DISCOUNT" && (isNaN(discountNum) || discountNum < 0 || discountNum > 100)) {
      setCalcError("Discount percentage must be between 0 and 100.");
      return;
    }

    calculateMutation.mutate({
      product_id: parseInt(calcProductId, 10),
      quantity: calcQuantity,
      pricing_method: calcMethod,
      discount_percent: calcMethod === "LINE_DISCOUNT" ? discountNum : 0.00,
      tiered_mode: calcMethod === "TIERED" ? calcTieredMode : null
    });
  };

  const getMethodBadgeClass = (method: string) => {
    switch (method) {
      case "STANDARD":
        return "bg-zinc-800 text-zinc-300 border border-zinc-700";
      case "LINE_DISCOUNT":
        return "bg-amber-950 text-amber-300 border border-amber-800";
      case "TIERED":
        return "bg-blue-950 text-blue-300 border border-blue-800";
      case "BLOCK":
        return "bg-purple-950 text-purple-300 border border-purple-800";
      case "COST_PLUS_MARKUP":
        return "bg-emerald-950 text-emerald-300 border border-emerald-800";
      default:
        return "bg-zinc-800 text-zinc-300";
    }
  };

  const formatBillingPrice = (amount: string | number, billingType: string, currency: string) => {
    const numericVal = typeof amount === "string" ? parseFloat(amount) : amount;
    const formattedAmount = `${currency} ${numericVal.toFixed(2)}`;
    if (billingType === "MRC") return `${formattedAmount}/month`;
    if (billingType === "NRC") return `${formattedAmount} one-time`;
    if (billingType === "USAGE") return `${formattedAmount}/unit`;
    return formattedAmount;
  };

  return (
    <div className="space-y-8 pb-12">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight text-zinc-100 mb-2 flex items-center gap-2">
            <DollarSign size={28} className="text-teal-400" />
            <span>Pricing Engine</span>
          </h1>
          <p className="text-sm text-zinc-400">
            Configure pricing methods, quantity tiers, and pricing strategies.
          </p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-zinc-850 gap-4">
        <button
          onClick={() => setActiveTab("config")}
          className={`pb-4 px-2 text-sm font-bold border-b-2 transition flex items-center gap-2 ${
            activeTab === "config"
              ? "border-teal-500 text-teal-400"
              : "border-transparent text-zinc-400 hover:text-zinc-200"
          }`}
        >
          <Settings size={16} />
          <span>Configuration Manager</span>
        </button>
        <button
          onClick={() => setActiveTab("preview")}
          className={`pb-4 px-2 text-sm font-bold border-b-2 transition flex items-center gap-2 ${
            activeTab === "preview"
              ? "border-teal-500 text-teal-400"
              : "border-transparent text-zinc-400 hover:text-zinc-200"
          }`}
        >
          <Calculator size={16} />
          <span>Price Preview & Calculator</span>
        </button>
      </div>

      {activeTab === "config" ? (
        <div className="grid grid-cols-1 gap-8">
          {/* Products List Table */}
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden shadow-2xl">
            <div className="p-6 border-b border-zinc-800 flex justify-between items-center">
              <h2 className="text-lg font-bold text-zinc-200 flex items-center gap-2">
                <TrendingUp size={20} className="text-teal-400" />
                <span>Catalog Pricing Settings</span>
              </h2>
              <button
                onClick={() => refetch()}
                className="p-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-400 hover:text-zinc-200 rounded-lg text-xs flex items-center gap-1 transition"
              >
                Refresh
              </button>
            </div>

            {isLoading ? (
              <div className="p-12 text-center text-zinc-500 text-sm">Loading products and pricing settings...</div>
            ) : isError ? (
              <div className="p-12 text-center text-red-400 text-sm">Failed to load catalog products.</div>
            ) : products.length === 0 ? (
              <div className="p-12 text-center text-zinc-500 text-sm">No catalog products found. Seed products to begin.</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm text-zinc-400">
                  <thead className="bg-zinc-950 text-zinc-300 uppercase text-xs font-bold border-b border-zinc-800">
                    <tr>
                      <th className="py-4 px-6">Product</th>
                      <th className="py-4 px-6">SKU</th>
                      <th className="py-4 px-6">Billing Type</th>
                      <th className="py-4 px-6">Pricing Method</th>
                      <th className="py-4 px-6 text-right">Base Price</th>
                      <th className="py-4 px-6 text-center">Status</th>
                      <th className="py-4 px-6 text-center">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-800">
                    {products.map((prod) => (
                      <tr key={prod.id} className="hover:bg-zinc-900/50 transition">
                        <td className="py-4 px-6 font-medium text-zinc-200">
                          <div>
                            <p>{prod.name}</p>
                            <span className="text-[10px] text-zinc-500 bg-zinc-950 px-2 py-0.5 rounded-full border border-zinc-850">
                              {prod.category_name || "Uncategorized"}
                            </span>
                          </div>
                        </td>
                        <td className="py-4 px-6 text-zinc-300 font-mono text-xs">{prod.sku}</td>
                        <td className="py-4 px-6 text-xs font-semibold">{prod.billing_type}</td>
                        <td className="py-4 px-6">
                          <span className={`text-[10px] font-bold uppercase px-2 py-1 rounded-md ${getMethodBadgeClass(prod.pricing_method)}`}>
                            {prod.pricing_method.replace(/_/g, " ")}
                          </span>
                          {prod.pricing_method === "COST_PLUS_MARKUP" && (
                            <span className="text-[10px] text-zinc-500 ml-1 font-mono">
                              (+{parseFloat(prod.markup_percent).toFixed(1)}%)
                            </span>
                          )}
                          {prod.has_tiers && (
                            <span className="text-[10px] text-blue-400 ml-1 bg-blue-950/40 border border-blue-900/30 px-1 py-0.2 rounded font-mono">
                              Tiers Configured
                            </span>
                          )}
                        </td>
                        <td className="py-4 px-6 text-right font-mono text-zinc-200">
                          {formatBillingPrice(prod.base_price, prod.billing_type, prod.currency)}
                        </td>
                        <td className="py-4 px-6 text-center">
                          <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${
                            prod.is_active 
                              ? "bg-emerald-950 text-emerald-400 border border-emerald-900" 
                              : "bg-zinc-950 text-zinc-500 border border-zinc-850"
                          }`}>
                            {prod.is_active ? "Active" : "Inactive"}
                          </span>
                        </td>
                        <td className="py-4 px-6">
                          <div className="flex items-center justify-center gap-2">
                            {canOpenConfig && (
                              <button
                                onClick={() => handleOpenConfig(prod)}
                                className="px-3 py-1 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-semibold rounded-lg border border-zinc-750 transition"
                              >
                                Configure
                              </button>
                            )}
                            {isExecutive && (
                              prod.is_active ? (
                                <button
                                  onClick={() => {
                                    if (confirm(`Deactivate ${prod.sku}?`)) {
                                      archiveMutation.mutate(prod.id);
                                    }
                                  }}
                                  className="px-3 py-1 bg-red-950/20 text-red-400 hover:bg-red-950/40 border border-red-900/30 text-xs font-semibold rounded-lg transition disabled:opacity-40"
                                >
                                  Deactivate
                                </button>
                              ) : (
                                <button
                                  onClick={() => {
                                    restoreMutation.mutate(prod.id);
                                  }}
                                  className="px-3 py-1 bg-emerald-950/20 text-emerald-400 hover:bg-emerald-950/40 border border-emerald-900/30 text-xs font-semibold rounded-lg transition disabled:opacity-40"
                                >
                                  Activate
                                </button>
                              )
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Pricing Rules Placeholder */}
          <div className="bg-zinc-900 border border-zinc-850 p-6 rounded-xl space-y-4 shadow-xl">
            <h3 className="text-lg font-bold text-zinc-200 flex items-center gap-2">
              <Scale size={20} className="text-teal-400" />
              <span>Pricing Rules</span>
            </h3>
            <div className="flex items-center gap-2 bg-zinc-950/50 border border-zinc-800 p-6 rounded-lg text-center justify-center text-zinc-500 font-semibold text-sm">
              Coming Soon (Pricing Policy Rule engine placeholder)
            </div>
          </div>
        </div>
      ) : (
        /* Interactive Calculator & Price Preview Panel */
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
          {/* Left panel: form */}
          <div className="lg:col-span-5 bg-zinc-900 border border-zinc-800 p-6 rounded-xl space-y-6 shadow-2xl h-fit">
            <h3 className="text-lg font-bold text-zinc-200 flex items-center gap-2">
              <Calculator size={20} className="text-teal-400" />
              <span>Calculator Inputs</span>
            </h3>

            {calcError && (
              <div className="flex items-start gap-3 bg-red-950/20 border border-red-900/30 p-4 rounded-xl text-red-300">
                <AlertCircle size={20} className="mt-0.5 shrink-0" />
                <p className="text-xs">{calcError}</p>
              </div>
            )}

            <form onSubmit={handleCalculate} className="space-y-4">
              <div className="space-y-1">
                <label className="block text-xs font-bold uppercase tracking-wider text-zinc-500">
                  Select Product
                </label>
                <select
                  value={calcProductId}
                  onChange={(e) => {
                    setCalcProductId(e.target.value);
                    setCalcResult(null);
                  }}
                  className="w-full bg-zinc-950 border border-zinc-850 rounded-xl px-4 py-2.5 text-zinc-200 focus:outline-none focus:border-teal-500 transition text-sm"
                >
                  <option value="">-- Choose Product --</option>
                  {products.map((p) => (
                    <option key={p.id} value={p.id.toString()}>
                      {p.name} ({p.sku})
                    </option>
                  ))}
                </select>
              </div>

              <div className="space-y-1">
                <label className="block text-xs font-bold uppercase tracking-wider text-zinc-500">
                  Quantity
                </label>
                <input
                  type="number"
                  min="1"
                  value={calcQuantity}
                  onChange={(e) => {
                    setCalcQuantity(Math.max(1, parseInt(e.target.value, 10) || 1));
                    setCalcResult(null);
                  }}
                  className="w-full bg-zinc-950 border border-zinc-850 rounded-xl px-4 py-2.5 text-zinc-200 font-mono focus:outline-none focus:border-teal-500 transition text-sm"
                />
              </div>

              <div className="space-y-1">
                <label className="block text-xs font-bold uppercase tracking-wider text-zinc-500">
                  Pricing Method
                </label>
                <select
                  value={calcMethod}
                  onChange={(e) => {
                    setCalcMethod(e.target.value);
                    setCalcResult(null);
                  }}
                  className="w-full bg-zinc-950 border border-zinc-850 rounded-xl px-4 py-2.5 text-zinc-200 focus:outline-none focus:border-teal-500 transition text-sm"
                >
                  <option value="STANDARD">Standard Base Pricing</option>
                  <option value="LINE_DISCOUNT">Line-Based percentage discount</option>
                  <option value="TIERED">Tier-Based pricing</option>
                  <option value="BLOCK">Block pricing</option>
                  <option value="COST_PLUS_MARKUP">Cost + Markup pricing</option>
                </select>
              </div>

              {calcMethod === "TIERED" && (
                <div className="space-y-1">
                  <label className="block text-xs font-bold uppercase tracking-wider text-zinc-500">
                    Tiered Mode
                  </label>
                  <select
                    value={calcTieredMode}
                    onChange={(e) => {
                      setCalcTieredMode(e.target.value);
                      setCalcResult(null);
                    }}
                    className="w-full bg-zinc-950 border border-zinc-850 rounded-xl px-4 py-2.5 text-zinc-200 focus:outline-none focus:border-teal-500 transition text-sm"
                  >
                    <option value="VOLUME">Volume Pricing</option>
                    <option value="CUMULATIVE">Cumulative Pricing</option>
                  </select>
                </div>
              )}

              {calcMethod === "LINE_DISCOUNT" && (
                <div className="space-y-1">
                  <label className="block text-xs font-bold uppercase tracking-wider text-zinc-500">
                    Discount Percentage (%)
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    max="100"
                    value={calcDiscount}
                    onChange={(e) => {
                      setCalcDiscount(e.target.value);
                      setCalcResult(null);
                    }}
                    className="w-full bg-zinc-950 border border-zinc-850 rounded-xl px-4 py-2.5 text-zinc-200 font-mono focus:outline-none focus:border-teal-500 transition text-sm"
                  />
                </div>
              )}

              <button
                type="submit"
                disabled={calculateMutation.isPending}
                className="w-full py-3 bg-teal-500 hover:bg-teal-400 text-zinc-950 rounded-xl font-bold transition shadow-lg shadow-teal-500/10 mt-2 disabled:opacity-50"
              >
                {calculateMutation.isPending ? "Calculating..." : "Calculate Price"}
              </button>
            </form>
          </div>

          {/* Right panel: results */}
          <div className="lg:col-span-7 bg-zinc-900 border border-zinc-800 p-6 rounded-xl space-y-6 shadow-2xl flex flex-col min-h-[400px]">
            <h3 className="text-lg font-bold text-zinc-200 flex items-center gap-2">
              <ShieldCheck size={20} className="text-teal-400" />
              <span>Calculated Price Preview</span>
            </h3>

            {calcResult ? (
              <div className="space-y-6 flex-1 flex flex-col justify-between">
                
                {/* Result header details */}
                <div className="grid grid-cols-2 md:grid-cols-3 gap-6 bg-zinc-950 border border-zinc-850 p-6 rounded-xl">
                  <div>
                    <span className="block text-[10px] text-zinc-500 font-bold uppercase">Product</span>
                    <span className="text-zinc-200 font-semibold text-sm">{calcResult.product_name}</span>
                  </div>
                  <div>
                    <span className="block text-[10px] text-zinc-500 font-bold uppercase">SKU</span>
                    <span className="text-zinc-300 font-mono text-xs">{calcResult.sku}</span>
                  </div>
                  <div>
                    <span className="block text-[10px] text-zinc-500 font-bold uppercase">Billing Type</span>
                    <span className="text-teal-400 font-bold text-xs uppercase bg-teal-950/40 border border-teal-900/30 px-2 py-0.5 rounded-full inline-block mt-0.5">
                      {calcResult.billing_type}
                    </span>
                  </div>
                  <div>
                    <span className="block text-[10px] text-zinc-500 font-bold uppercase">Pricing Method</span>
                    <span className="text-zinc-300 text-xs font-semibold">{calcResult.pricing_method.replace(/_/g, " ")}</span>
                  </div>
                  <div>
                    <span className="block text-[10px] text-zinc-500 font-bold uppercase">Quantity Requested</span>
                    <span className="text-zinc-200 font-semibold text-sm">{calcResult.quantity}</span>
                  </div>
                  <div>
                    <span className="block text-[10px] text-zinc-500 font-bold uppercase">Currency</span>
                    <span className="text-zinc-300 font-semibold text-sm">{calcResult.currency}</span>
                  </div>
                </div>

                {/* Mathematical price details */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  
                  {/* Unit Level breakdown */}
                  <div className="border border-zinc-850 p-5 rounded-xl space-y-3">
                    <h4 className="text-xs font-bold text-zinc-400 uppercase tracking-wider">Unit level pricing</h4>
                    <div className="space-y-1.5 text-xs">
                      <div className="flex justify-between">
                        <span className="text-zinc-500">Base Unit Price:</span>
                        <span className="font-mono text-zinc-300">{formatBillingPrice(calcResult.base_unit_price, calcResult.billing_type, calcResult.currency)}</span>
                      </div>
                      {parseFloat(calcResult.discount_percent) > 0 && (
                        <>
                          <div className="flex justify-between">
                            <span className="text-zinc-500">Discount Percent:</span>
                            <span className="font-mono text-amber-400">-{parseFloat(calcResult.discount_percent).toFixed(2)}%</span>
                          </div>
                          <div className="flex justify-between border-b border-zinc-850 pb-1.5">
                            <span className="text-zinc-500">Discount Amount:</span>
                            <span className="font-mono text-amber-400">-{calcResult.currency} {parseFloat(calcResult.discount_amount).toFixed(2)}</span>
                          </div>
                        </>
                      )}
                      <div className="flex justify-between pt-1.5">
                        <span className="text-zinc-400 font-semibold">Final Unit Price:</span>
                        <span className="font-mono text-teal-400 font-bold">{formatBillingPrice(calcResult.final_unit_price, calcResult.billing_type, calcResult.currency)}</span>
                      </div>
                    </div>
                  </div>

                  {/* Line Total pricing */}
                  <div className="bg-zinc-950/60 border border-zinc-850 p-5 rounded-xl flex flex-col justify-center space-y-2">
                    <span className="text-xs font-bold text-zinc-500 uppercase tracking-wider text-center block">Calculated Line Total</span>
                    <div className="text-center">
                      <span className="text-3xl font-extrabold text-teal-400 font-mono">
                        {calcResult.currency} {parseFloat(calcResult.total_price).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </span>
                      <span className="block text-[10px] text-zinc-500 uppercase mt-1">
                        {calcResult.quantity} unit{calcResult.quantity > 1 ? "s" : ""} × {calcResult.currency} {parseFloat(calcResult.final_unit_price).toFixed(2)}
                      </span>
                    </div>
                  </div>

                </div>

                {/* Calculation breakdown */}
                <div className="border border-zinc-850 p-5 rounded-xl space-y-3">
                  <h4 className="text-xs font-bold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
                    <Info size={14} className="text-teal-500" />
                    <span>Calculation Breakdown Details</span>
                  </h4>
                  <div className="max-h-[160px] overflow-y-auto bg-zinc-950 p-3 rounded-lg border border-zinc-850 text-xs text-zinc-400 font-mono space-y-2">
                    {Array.isArray(calcResult.calculation_breakdown) && calcResult.calculation_breakdown.length > 0 ? (
                      calcResult.calculation_breakdown.map((item, idx) => {
                        if (typeof item === "string") {
                          return <div key={idx} className="border-b border-zinc-900/50 pb-1 last:border-0 last:pb-0">{item}</div>;
                        }
                        return (
                          <div key={idx} className="flex justify-between items-center border-b border-zinc-900/50 pb-1.5 last:border-0 last:pb-0">
                            <div>
                              <span className="text-teal-400 font-semibold">Tier {item.tier}</span>
                              <span className="text-zinc-500 ml-2">({item.quantity} units)</span>
                            </div>
                            <div>
                              <span className="text-zinc-500">@ {calcResult.currency}{parseFloat(item.unit_price).toFixed(2)}</span>
                              <span className="text-zinc-300 ml-3 font-semibold">= {calcResult.currency}{parseFloat(item.amount).toFixed(2)}</span>
                            </div>
                          </div>
                        );
                      })
                    ) : (
                      <div className="text-zinc-500 italic text-center py-2">Standard base pricing multiplication rules applied.</div>
                    )}
                  </div>
                </div>

              </div>
            ) : (
              <div className="flex-1 flex flex-col items-center justify-center text-zinc-500 border-2 border-dashed border-zinc-800 rounded-xl p-8 text-center space-y-2">
                <Calculator size={40} className="text-zinc-700" />
                <p className="text-sm">Select a product and parameters, then execute a calculation to view the live preview breakdown.</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Configuration Modal */}
      {isConfigModalOpen && selectedProduct && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-zinc-950 border border-zinc-800 w-full max-w-2xl rounded-2xl overflow-hidden flex flex-col max-h-[90vh] shadow-2xl">
            {/* Modal Header */}
            <div className="p-6 border-b border-zinc-900 flex justify-between items-center bg-zinc-950">
              <div>
                <h3 className="text-lg font-bold text-zinc-100">
                  Pricing Settings: {selectedProduct.name}
                </h3>
                <p className="text-xs text-zinc-500 font-mono mt-0.5">SKU: {selectedProduct.sku}</p>
              </div>
              <button
                onClick={handleCancelOrClose}
                className="p-1 hover:bg-zinc-900 rounded-lg text-zinc-500 hover:text-zinc-200 transition"
              >
                <X size={20} />
              </button>
            </div>

            {/* Modal Content */}
            <div className="p-6 overflow-y-auto space-y-6 flex-1 bg-zinc-950/90 text-sm text-zinc-400">
              
              {/* Product Pricing Summary */}
              {(() => {
                const basePriceNum = parseFloat(selectedProduct.base_price);
                const costPriceNum = selectedProduct.cost_price ? parseFloat(selectedProduct.cost_price) : null;
                const marginPercentage = (selectedProduct as any).margin_percentage !== null && (selectedProduct as any).margin_percentage !== undefined
                  ? parseFloat((selectedProduct as any).margin_percentage).toFixed(2)
                  : (costPriceNum !== null && basePriceNum > 0)
                  ? (((basePriceNum - costPriceNum) / basePriceNum) * 100).toFixed(2)
                  : null;
                const billingTypeLabel = 
                  selectedProduct.billing_type === "MRC" ? "Monthly" :
                  selectedProduct.billing_type === "NRC" ? "One-time" :
                  selectedProduct.billing_type === "USAGE" ? "Usage Based" :
                  selectedProduct.billing_type;

                return (
                  <div className="grid grid-cols-4 gap-4 bg-zinc-900/40 p-4 border border-zinc-850 rounded-xl font-mono text-center">
                    <div>
                      <span className="block text-[10px] text-zinc-500 font-bold uppercase tracking-wider">Base Price</span>
                      <span className="text-zinc-200 text-xs font-bold">{selectedProduct.currency} {basePriceNum.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
                    </div>
                    <div>
                      <span className="block text-[10px] text-zinc-500 font-bold uppercase tracking-wider">Product Cost</span>
                      <span className="text-zinc-200 text-xs font-bold">
                        {costPriceNum !== null ? `${selectedProduct.currency} ${costPriceNum.toLocaleString(undefined, { minimumFractionDigits: 2 })}` : "Not Available"}
                      </span>
                    </div>
                    <div>
                      <span className="block text-[10px] text-zinc-500 font-bold uppercase tracking-wider">Billing Type</span>
                      <span className="text-zinc-200 text-xs font-bold">{billingTypeLabel}</span>
                    </div>
                    <div>
                      <span className="block text-[10px] text-zinc-500 font-bold uppercase tracking-wider">Current Margin</span>
                      <span className="text-zinc-200 text-xs font-bold">{marginPercentage !== null ? `${marginPercentage}%` : "N/A"}</span>
                    </div>
                  </div>
                );
              })()}

              {/* Existing Configuration Warning */}
              {pricingMethod !== selectedProduct.pricing_method && (
                <div className="flex items-start gap-3 bg-amber-950/20 border border-amber-900/30 p-4 rounded-xl text-amber-300">
                  <AlertCircle size={20} className="mt-0.5 shrink-0" />
                  <div>
                    <p className="text-xs">
                      Changing the pricing method will affect future pricing calculations for this product.
                    </p>
                  </div>
                </div>
              )}

              {/* Unauthorized warning */}
              {!canEditConfig && (
                <div className="flex items-start gap-3 bg-amber-950/20 border border-amber-900/30 p-4 rounded-xl text-amber-300">
                  <AlertCircle size={20} className="mt-0.5 shrink-0" />
                  <div>
                    <h4 className="font-bold text-sm">View Only Mode</h4>
                    <p className="text-xs text-amber-400/80 mt-1">
                      You do not have the required permissions (`pricing.config.update`) to save pricing settings.
                    </p>
                  </div>
                </div>
              )}

              {/* Error Box */}
              {configError && (
                <div className="flex items-start gap-3 bg-red-950/20 border border-red-900/30 p-4 rounded-xl text-red-300">
                  <AlertCircle size={20} className="mt-0.5 shrink-0" />
                  <p className="text-xs">{configError}</p>
                </div>
              )}

              {/* Method Selector */}
              <div className="space-y-2">
                <label className="block text-xs font-bold uppercase tracking-wider text-zinc-500">
                  Pricing Method
                </label>
                <select
                  disabled={!canEditConfig}
                  value={pricingMethod}
                  onChange={(e) => {
                    setPricingMethod(e.target.value);
                    setConfigError(null);
                  }}
                  className="w-full bg-zinc-900 border border-zinc-800 rounded-xl px-4 py-3 text-zinc-200 focus:outline-none focus:border-teal-500 transition"
                >
                  <option value="STANDARD">Standard Base Pricing</option>
                  <option value="LINE_DISCOUNT">Line-Based Percentage Discount</option>
                  <option value="TIERED">Tier-Based Pricing</option>
                  <option value="BLOCK">Block Pricing</option>
                  <option value="COST_PLUS_MARKUP">Cost + Markup Pricing</option>
                </select>
              </div>

              {/* Standard pricing info */}
              {pricingMethod === "STANDARD" && (
                <div className="p-4 bg-zinc-900/50 border border-zinc-850 rounded-xl space-y-1">
                  <p className="text-xs text-zinc-300 font-bold">Standard Pricing Applied</p>
                  <p className="text-xs text-zinc-500">
                    Product selling price equals the catalog base price.
                  </p>
                  <p className="text-xs text-zinc-400 mt-2 font-mono">
                    Current Base Price: {selectedProduct.currency} {parseFloat(selectedProduct.base_price).toFixed(2)}
                  </p>
                </div>
              )}

              {/* Line Discount pricing configuration */}
              {pricingMethod === "LINE_DISCOUNT" && (
                <div className="space-y-4 bg-zinc-900/30 p-4 border border-zinc-850 rounded-xl">
                  <div className="space-y-1">
                    <label className="block text-xs font-bold uppercase tracking-wider text-zinc-500">
                      Default Discount Percentage (%)
                    </label>
                    <div className="relative">
                      <input
                        disabled={!canEditConfig}
                        type="number"
                        step="0.01"
                        min="0"
                        max="100"
                        value={markupPercent}
                        onChange={(e) => {
                          setMarkupPercent(e.target.value);
                          setConfigError(null);
                        }}
                        className="w-full bg-zinc-900 border border-zinc-800 rounded-xl pl-4 pr-12 py-2.5 text-zinc-200 font-mono focus:outline-none focus:border-teal-500 transition"
                      />
                      <div className="absolute right-4 top-1/2 -translate-y-1/2 text-zinc-500 font-mono text-sm">%</div>
                    </div>
                  </div>

                  {/* Calculation Example */}
                  <div className="bg-zinc-950/60 p-3 rounded-lg border border-zinc-850/50 space-y-1 text-xs">
                    <span className="block text-[10px] text-zinc-500 font-bold uppercase">Calculation Example</span>
                    <p className="text-zinc-400">
                      At standard base price <span className="font-mono text-zinc-200">{selectedProduct.currency} {parseFloat(selectedProduct.base_price).toFixed(2)}</span>:
                    </p>
                    <p className="font-mono text-teal-400">
                      Discount Applied: {parseFloat(markupPercent) || 0}% (-{selectedProduct.currency} {((parseFloat(selectedProduct.base_price) * (parseFloat(markupPercent) || 0)) / 100).toFixed(2)})
                    </p>
                    <p className="font-mono text-zinc-200">
                      Selling price: {selectedProduct.currency} {(parseFloat(selectedProduct.base_price) * (1 - (parseFloat(markupPercent) || 0) / 100)).toFixed(2)}
                    </p>
                  </div>
                </div>
              )}

              {/* Cost Plus Markup Settings */}
              {pricingMethod === "COST_PLUS_MARKUP" && (
                <div className="space-y-4 bg-zinc-900/30 p-4 border border-zinc-850 rounded-xl">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <span className="block text-xs text-zinc-500 font-bold uppercase">Product Cost</span>
                      <span className="text-lg font-mono text-zinc-200">
                        {selectedProduct.cost_price 
                          ? `${selectedProduct.currency} ${parseFloat(selectedProduct.cost_price).toFixed(2)}` 
                          : "None configured"}
                      </span>
                    </div>
                    <div>
                      <span className="block text-xs text-zinc-500 font-bold uppercase">Selling Unit Price Preview</span>
                      <span className="text-lg font-mono text-teal-400 font-extrabold">
                        {selectedProduct.cost_price 
                          ? `${selectedProduct.currency} ${(parseFloat(selectedProduct.cost_price) * (1 + (parseFloat(markupPercent) || 0) / 100)).toFixed(2)}` 
                          : "N/A"}
                      </span>
                    </div>
                  </div>

                  <div className="space-y-1 border-t border-zinc-850 pt-4">
                    <label className="block text-xs font-bold uppercase tracking-wider text-zinc-500">
                      Markup Percentage (%)
                    </label>
                    <input
                      disabled={!canEditConfig}
                      type="number"
                      step="0.01"
                      min="0"
                      value={markupPercent}
                      onChange={(e) => {
                        setMarkupPercent(e.target.value);
                        setConfigError(null);
                      }}
                      className="w-full bg-zinc-900 border border-zinc-800 rounded-xl px-4 py-2.5 text-zinc-200 font-mono focus:outline-none focus:border-teal-500 transition"
                    />
                  </div>
                </div>
              )}

              {/* TIERED / BLOCK configurations */}
              {(pricingMethod === "TIERED" || pricingMethod === "BLOCK") && (
                <div className="space-y-4">
                  {pricingMethod === "TIERED" && (
                    <div className="space-y-2">
                      <label className="block text-xs font-bold uppercase tracking-wider text-zinc-500">
                        Tier Pricing Mode
                      </label>
                      <div className="grid grid-cols-2 gap-2 bg-zinc-900 border border-zinc-850 p-1.5 rounded-xl">
                        <button
                          type="button"
                          disabled={!canEditConfig}
                          onClick={() => setTieredMode("VOLUME")}
                          className={`py-2 rounded-lg text-xs font-bold transition ${
                            tieredMode === "VOLUME" 
                              ? "bg-zinc-800 text-teal-400 shadow-md" 
                              : "text-zinc-500 hover:text-zinc-300"
                          }`}
                        >
                          Volume Pricing
                        </button>
                        <button
                          type="button"
                          disabled={!canEditConfig}
                          onClick={() => setTieredMode("CUMULATIVE")}
                          className={`py-2 rounded-lg text-xs font-bold transition ${
                            tieredMode === "CUMULATIVE" 
                              ? "bg-zinc-800 text-teal-400 shadow-md" 
                              : "text-zinc-500 hover:text-zinc-300"
                          }`}
                        >
                          Cumulative Pricing
                        </button>
                      </div>
                    </div>
                  )}

                  {pricingMethod === "BLOCK" && (
                    <div className="p-3 bg-zinc-900/30 border border-zinc-850 rounded-xl text-xs text-zinc-400">
                      <p className="font-bold text-zinc-300 mb-1">Block Pricing Applied</p>
                      <p>
                        Block price is a fixed price for the selected quantity range.
                        Do <span className="text-teal-400 font-semibold">NOT</span> multiply block price by quantity.
                      </p>
                    </div>
                  )}

                  <div className="space-y-3">
                    <div className="flex justify-between items-center">
                      <label className="block text-xs font-bold uppercase tracking-wider text-zinc-500">
                        {pricingMethod === "BLOCK" ? "Quantity Blocks" : "Pricing Tiers"}
                      </label>
                      {canEditConfig && (
                        <button
                          type="button"
                          onClick={handleAddTier}
                          className="px-2 py-1 bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 rounded text-xs text-teal-400 hover:text-teal-300 flex items-center gap-1 transition"
                        >
                          <Plus size={14} /> Add Tier
                        </button>
                      )}
                    </div>

                    <div className="space-y-2.5">
                      {tiers.map((t, idx) => (
                        <div key={idx} className="flex items-center gap-3 bg-zinc-900 border border-zinc-850 px-4 py-3 rounded-xl">
                          <div className="w-12 text-center text-xs font-mono font-bold text-zinc-500">
                            #{idx + 1}
                          </div>
                          <div className="flex items-center gap-2">
                            <span className="text-xs text-zinc-500 font-mono">Min:</span>
                            <span className="text-zinc-200 font-mono text-sm w-12 text-center bg-zinc-950 py-1 border border-zinc-850 rounded">
                              {t.min_quantity}
                            </span>
                          </div>
                          <div className="flex items-center gap-2 flex-1">
                            <span className="text-xs text-zinc-500 font-mono">Max:</span>
                            <input
                              disabled={!canEditConfig || idx === tiers.length - 1}
                              type="number"
                              min="1"
                              placeholder="Unlimited"
                              value={t.max_quantity === null ? "" : t.max_quantity}
                              onChange={(e) => handleTierChange(idx, "max_quantity", e.target.value)}
                              className="bg-zinc-950 border border-zinc-850 text-zinc-200 font-mono text-sm w-full px-2 py-1 rounded text-center focus:outline-none focus:border-teal-500 transition disabled:opacity-40"
                            />
                          </div>
                          <div className="flex items-center gap-2 flex-1">
                            <span className="text-xs text-zinc-500 font-mono">
                              {pricingMethod === "BLOCK" ? "Block Price" : "Unit Price"}:
                            </span>
                            <input
                              disabled={!canEditConfig}
                              type="number"
                              step="0.01"
                              min="0"
                              value={t.price}
                              onChange={(e) => handleTierChange(idx, "price", e.target.value)}
                              className="bg-zinc-950 border border-zinc-850 text-zinc-200 font-mono text-sm w-full px-2 py-1 rounded text-right focus:outline-none focus:border-teal-500 transition"
                            />
                          </div>
                          {canEditConfig && tiers.length > 1 && (
                            <button
                              type="button"
                              onClick={() => handleRemoveTier(idx)}
                              className="p-1 hover:bg-zinc-800 text-zinc-500 hover:text-red-400 rounded transition"
                            >
                              <Trash2 size={16} />
                            </button>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {/* Live Price Preview Section */}
              <div className="bg-zinc-900/50 border border-zinc-850 p-4 rounded-xl space-y-3">
                <div className="flex justify-between items-center">
                  <h4 className="text-xs font-bold text-zinc-400 uppercase tracking-wider">Price Preview</h4>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-zinc-500 font-mono">Quantity:</span>
                    <input
                      type="number"
                      min="1"
                      value={previewQuantity}
                      onChange={(e) => setPreviewQuantity(Math.max(1, parseInt(e.target.value, 10) || 1))}
                      className="bg-zinc-950 border border-zinc-850 text-zinc-200 font-mono text-xs w-16 px-2 py-1 rounded text-center focus:outline-none focus:border-teal-500"
                    />
                  </div>
                </div>

                {isPreviewLoading ? (
                  <div className="text-xs text-zinc-500 text-center py-4 italic">Calculating preview...</div>
                ) : previewError ? (
                  <div className="text-xs text-red-400 bg-red-950/20 border border-red-900/30 p-3 rounded-lg">{previewError}</div>
                ) : previewResult ? (
                  <div className="space-y-2.5">
                    <div className="grid grid-cols-2 gap-y-1.5 text-xs text-zinc-400 border-b border-zinc-850 pb-2">
                      <span>Base Price</span>
                      <span className="text-right font-mono text-zinc-300">
                        {previewResult.currency} {parseFloat(previewResult.base_unit_price).toFixed(2)}
                      </span>
                      
                      <span>Pricing Method</span>
                      <span className="text-right text-zinc-300 font-semibold">
                        {pricingMethod === "STANDARD" ? "Standard Pricing" :
                         pricingMethod === "LINE_DISCOUNT" ? "Line Discount Pricing" :
                         pricingMethod === "TIERED" ? `Tiered Pricing (${tieredMode === "VOLUME" ? "Volume" : "Cumulative"})` :
                         pricingMethod === "BLOCK" ? "Block Pricing" :
                         pricingMethod === "COST_PLUS_MARKUP" ? "Cost + Markup Pricing" :
                         pricingMethod.replace(/_/g, " ")}
                      </span>

                      <span>Final Unit Price</span>
                      <span className="text-right font-mono text-teal-400 font-semibold">
                        {previewResult.currency} {parseFloat(previewResult.final_unit_price).toFixed(2)}
                      </span>

                      <span>Billing</span>
                      <span className="text-right text-zinc-300">
                        {previewResult.billing_type === "MRC" ? "Monthly" :
                         previewResult.billing_type === "NRC" ? "One-time" :
                         previewResult.billing_type === "USAGE" ? "Usage Based" :
                         previewResult.billing_type}
                      </span>
                    </div>

                    <div className="flex justify-between items-center pt-1">
                      <span className="text-xs font-bold uppercase text-zinc-400">Total</span>
                      <span className="text-lg font-extrabold text-teal-400 font-mono">
                        {previewResult.currency} {parseFloat(previewResult.total_price).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                        <span className="text-[10px] text-zinc-500 font-normal ml-1">
                          {previewResult.billing_type === "MRC" ? "one-time" : // standard formatted string rules
                           previewResult.billing_type === "NRC" ? "one-time" :
                           previewResult.billing_type === "USAGE" ? "/ unit" : ""}
                        </span>
                        {/* Format MRC as per-month, NRC as one-time, USAGE as per-unit */}
                        <span className="block text-[10px] text-zinc-500 font-normal text-right mt-0.5">
                          {previewResult.billing_type === "MRC" && `(${previewResult.currency} ${parseFloat(previewResult.final_unit_price).toFixed(2)} / month)`}
                          {previewResult.billing_type === "NRC" && `(${previewResult.currency} ${parseFloat(previewResult.final_unit_price).toFixed(2)} one-time)`}
                          {previewResult.billing_type === "USAGE" && `(${previewResult.currency} ${parseFloat(previewResult.final_unit_price).toFixed(2)} / unit)`}
                        </span>
                      </span>
                    </div>
                  </div>
                ) : (
                  <div className="text-xs text-zinc-500 text-center py-4 italic">No preview available.</div>
                )}
              </div>

            </div>

            {/* Modal Footer */}
            <div className="p-6 border-t border-zinc-900 flex justify-end gap-3 bg-zinc-950">
              <button
                type="button"
                onClick={handleCancelOrClose}
                className="px-4 py-2 bg-zinc-900 border border-zinc-800 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-850 rounded-xl text-sm font-semibold transition"
              >
                Cancel
              </button>
              {canEditConfig && (
                <button
                  type="button"
                  onClick={handleSave}
                  disabled={configMutation.isPending || !hasUnsavedChanges}
                  className="px-5 py-2 bg-teal-500 hover:bg-teal-400 text-zinc-950 rounded-xl text-sm font-bold shadow-lg shadow-teal-500/10 transition disabled:opacity-50"
                >
                  {configMutation.isPending ? "Saving..." : "Save Configuration"}
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Discard Changes Confirmation Dialog */}
      {isDiscardConfirmOpen && (
        <div className="fixed inset-0 bg-black/90 backdrop-blur-md z-[100] flex items-center justify-center p-4">
          <div className="bg-zinc-950 border border-zinc-800 p-6 rounded-2xl max-w-sm w-full space-y-4 shadow-2xl text-center">
            <AlertCircle size={32} className="text-amber-500 mx-auto" />
            <div className="space-y-1">
              <h4 className="text-zinc-200 font-bold text-lg">Discard unsaved pricing changes?</h4>
              <p className="text-xs text-zinc-500">All modifications made to this configuration will be lost.</p>
            </div>
            <div className="grid grid-cols-2 gap-3 pt-2">
              <button
                type="button"
                onClick={() => setIsDiscardConfirmOpen(false)}
                className="py-2.5 px-4 bg-zinc-900 border border-zinc-800 hover:bg-zinc-850 text-zinc-300 font-semibold rounded-xl text-xs transition"
              >
                Keep Editing
              </button>
              <button
                type="button"
                onClick={() => {
                  setIsDiscardConfirmOpen(false);
                  setIsConfigModalOpen(false);
                  setSelectedProduct(null);
                }}
                className="py-2.5 px-4 bg-red-950 text-red-400 hover:bg-red-900 hover:text-zinc-200 border border-red-900/30 font-semibold rounded-xl text-xs transition"
              >
                Discard Changes
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Toast Alert Feedback Overlay */}
      {toast && (
        <div className="fixed bottom-5 right-5 z-50 flex items-center gap-3 bg-zinc-950 border border-zinc-800/80 p-4 rounded-xl shadow-2xl text-xs max-w-sm animate-in fade-in slide-in-from-bottom-5">
          {toast.type === "success" ? (
            <div className="h-2 w-2 rounded-full bg-emerald-400 shrink-0" />
          ) : (
            <div className="h-2 w-2 rounded-full bg-red-400 shrink-0" />
          )}
          <p className={toast.type === "success" ? "text-emerald-400 font-semibold" : "text-red-400 font-semibold"}>
            {toast.message}
          </p>
        </div>
      )}
    </div>
  );
}
