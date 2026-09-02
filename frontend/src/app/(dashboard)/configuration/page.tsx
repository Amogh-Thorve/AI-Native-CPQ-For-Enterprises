"use client";

import React, { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Sliders,
  Plus,
  HelpCircle,
  AlertCircle,
  CheckCircle,
  Layers,
  ChevronRight,
  ChevronLeft,
  Info,
  ShieldAlert,
  Loader2,
  Lock,
  PlusCircle,
  Database,
  Trash2,
  Settings,
  Briefcase,
  Wrench,
  Sparkles,
  ArrowRight,
  Eye,
  Check,
  Edit2
} from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";

// --- Types & Interfaces ---

interface Product {
  id: number;
  sku: string;
  name: string;
  base_price: string;
  is_active: boolean;
  billing_type: string;
}

interface BundleComponent {
  id: number;
  bundle_id: number;
  product_id: number;
  required: boolean;
  default_selected: boolean;
  min_quantity: number;
  max_quantity: number | null;
  default_quantity: number;
  display_order: number;
  is_active: boolean;
  product?: Product;
}

interface Bundle {
  id: number;
  name: string;
  description: string | null;
  sku: string;
  is_active: boolean;
  components: BundleComponent[];
}

interface SelectionItem {
  group_id: number;
  option_ids: number[];
  quantities?: { [opt_id: string]: number };
}

interface ConfigurationGroup {
  id: number;
  product_id: number;
  name: string;
  description: string | null;
  required: boolean;
  selection_type: "SINGLE_SELECT" | "MULTI_SELECT";
  display_order: number;
  is_active: boolean;
  options: any[];
}

interface ComponentSelectionState {
  component_id: number;
  selected: boolean;
  quantity: number;
  configuration: {
    product_id: number;
    selections: SelectionItem[];
  } | null;
}

interface BundleErrorDetail {
  type: string;
  message: string;
  component_id: number | null;
}

export default function ProductConfigurationPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();

  const isExecutive = user?.role === "executive" || user?.role === "admin";

  // --- Tabs State ---
  const [activeTab, setActiveTab] = useState<"configure" | "admin">("configure");

  // --- Admin Builder State ---
  const [editingBundle, setEditingBundle] = useState<Bundle | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newBundleName, setNewBundleName] = useState("");
  const [newBundleSku, setNewBundleSku] = useState("");
  const [newBundleDesc, setNewBundleDesc] = useState("");

  const [addComponentProductId, setAddComponentProductId] = useState<number | "">("");
  const [addComponentRequired, setAddComponentRequired] = useState(true);
  const [addComponentMinQty, setAddComponentMinQty] = useState(1);
  const [addComponentMaxQty, setAddComponentMaxQty] = useState<number | "">("");
  const [addComponentDefQty, setAddComponentDefQty] = useState(1);

  // --- Guided Flow Configurator State ---
  const [selectedBundleId, setSelectedBundleId] = useState<number | "">("");
  const [guidedStep, setGuidedStep] = useState<1 | 2 | 3 | 4>(1);
  const [bundleSelections, setBundleSelections] = useState<{ [comp_id: number]: ComponentSelectionState }>({});
  
  // Conf group navigation inside step 2 (Configurable products options selection)
  const [activeConfigCompId, setActiveConfigCompId] = useState<number | null>(null);
  const [activeConfigGroupId, setActiveConfigGroupId] = useState<number | null>(null);

  // --- Versioning & Lifecycle State ---
  const [selectedVersionEntity, setSelectedVersionEntity] = useState<{ type: "PRODUCT" | "BUNDLE"; id: number } | null>(null);
  const [showVersionHistoryModal, setShowVersionHistoryModal] = useState(false);
  const [showCompareModal, setShowCompareModal] = useState(false);
  const [versionAId, setVersionAId] = useState<number | "">("");
  const [versionBId, setVersionBId] = useState<number | "">("");
  const [compareResult, setCompareResult] = useState<any>(null);

  // --- Queries ---

  // Catalog products for component additions
  const { data: catalogProducts } = useQuery<Product[]>({
    queryKey: ["catalog-products"],
    queryFn: () => api.get<Product[]>("/pricing/products")
  });

  // Active solution bundles
  const { data: bundles, isLoading: isLoadingBundles, refetch: refetchBundles } = useQuery<Bundle[]>({
    queryKey: ["bundles-list"],
    queryFn: () => api.get<Bundle[]>("/configuration/bundles")
  });

  const selectedBundle = bundles?.find((b) => b.id === selectedBundleId);

  // Configuration groups structure lookup for a configurable component
  const activeConfigComp = selectedBundle?.components.find((c) => c.id === activeConfigCompId);
  const { data: configGroups, isLoading: isLoadingConfigGroups } = useQuery<ConfigurationGroup[]>({
    queryKey: ["configurable-product-structure", activeConfigComp?.product_id],
    queryFn: () => api.get<ConfigurationGroup[]>(`/configuration/products/${activeConfigComp?.product_id}`),
    enabled: !!activeConfigComp?.product_id
  });

  // --- Live Validation Mutation ---
  const validateMutation = useMutation({
    mutationFn: (payload: any) => api.post<any>(`/configuration/bundles/${payload.bundle_id}/validate`, payload)
  });

  // --- Admin Mutations ---
  const createBundleMutation = useMutation({
    mutationFn: (payload: any) => api.post<any>("/configuration/bundles", payload),
    onSuccess: () => {
      refetchBundles();
      setShowCreateModal(false);
      setNewBundleName("");
      setNewBundleSku("");
      setNewBundleDesc("");
    }
  });

  const updateBundleMutation = useMutation({
    mutationFn: (payload: { id: number; data: any }) => api.put<any>(`/configuration/bundles/${payload.id}`, payload.data),
    onSuccess: () => {
      refetchBundles();
    }
  });

  const addComponentMutation = useMutation({
    mutationFn: (payload: { bundleId: number; data: any }) =>
      api.post<any>(`/configuration/bundles/${payload.bundleId}/components`, payload.data),
    onSuccess: (data) => {
      refetchBundles();
      if (editingBundle) {
        setEditingBundle((prev) => prev ? { ...prev, components: [...prev.components, data] } : null);
      }
      setAddComponentProductId("");
      setAddComponentRequired(true);
      setAddComponentMinQty(1);
      setAddComponentMaxQty("");
      setAddComponentDefQty(1);
    }
  });

  const deleteComponentMutation = useMutation({
    mutationFn: (payload: { bundleId: number; compId: number }) =>
      api.delete(`/configuration/bundles/${payload.bundleId}/components/${payload.compId}`),
    onSuccess: (_, variables) => {
      refetchBundles();
      if (editingBundle) {
        setEditingBundle((prev) =>
          prev ? { ...prev, components: prev.components.filter((c) => c.id !== variables.compId) } : null
        );
      }
    }
  });

  // Save session mutation
  const saveSessionMutation = useMutation({
    mutationFn: (payload: any) => api.post<any>("/configuration/bundles/sessions", payload),
    onSuccess: () => {
      alert("Bundle Configuration session saved successfully!");
      setSelectedBundleId("");
      setGuidedStep(1);
    }
  });

  // --- Versioning & Lifecycle Queries/Mutations ---
  const { data: versionsList, refetch: refetchVersions } = useQuery<any[]>({
    queryKey: ["versions-list", selectedVersionEntity?.type, selectedVersionEntity?.id],
    queryFn: () => {
      const path = selectedVersionEntity?.type === "PRODUCT"
        ? `/configuration/products/${selectedVersionEntity?.id}/versions`
        : `/configuration/bundles/${selectedVersionEntity?.id}/versions`;
      return api.get<any[]>(path);
    },
    enabled: !!selectedVersionEntity
  });

  const createDraftMutation = useMutation({
    mutationFn: (payload: { type: "PRODUCT" | "BUNDLE"; id: number }) => {
      const path = payload.type === "PRODUCT"
        ? `/configuration/products/${payload.id}/versions/draft`
        : `/configuration/bundles/${payload.id}/versions/draft`;
      return api.post<any>(path, {});
    },
    onSuccess: () => {
      refetchVersions();
      alert("Draft version successfully created!");
    }
  });

  const activateVersionMutation = useMutation({
    mutationFn: (versionId: number) => api.post<any>(`/configuration/versions/${versionId}/activate`, {}),
    onSuccess: () => {
      refetchVersions();
      refetchBundles();
      alert("Version successfully activated!");
    },
    onError: (err: any) => {
      alert("Activation failed: " + (err.message || "Invalid draft structure"));
    }
  });

  const archiveVersionMutation = useMutation({
    mutationFn: (versionId: number) => api.post<any>(`/configuration/versions/${versionId}/archive`, {}),
    onSuccess: () => {
      refetchVersions();
      refetchBundles();
      alert("Version successfully archived!");
    }
  });

  // --- Hooks / Side Effects ---

  // Handle setting default component values when bundle selected
  useEffect(() => {
    if (selectedBundle) {
      const initial: { [comp_id: number]: ComponentSelectionState } = {};
      selectedBundle.components.forEach((c) => {
        initial[c.id] = {
          component_id: c.id,
          selected: c.required || c.default_selected,
          quantity: c.default_quantity,
          configuration: null
        };
      });
      setBundleSelections(initial);
      setGuidedStep(1);
    }
  }, [selectedBundleId]);

  // Set default group in active product options config view
  useEffect(() => {
    if (configGroups && configGroups.length > 0) {
      setActiveConfigGroupId(configGroups[0].id);
    }
  }, [configGroups]);

  // Handle live validate check
  useEffect(() => {
    if (!selectedBundleId || Object.keys(bundleSelections).length === 0) return;

    const selectionsPayload = Object.values(bundleSelections).map((sel) => ({
      component_id: sel.component_id,
      selected: sel.selected,
      quantity: sel.quantity,
      configuration: sel.configuration
    }));

    validateMutation.mutate({
      bundle_id: selectedBundleId,
      selections: selectionsPayload
    });
  }, [bundleSelections, selectedBundleId]);

  // Get active step validation errors
  const errors = validateMutation.data?.errors || [];
  const isValid = validateMutation.data?.valid;

  const getErrorsForStep = (step: 1 | 2 | 3 | 4) => {
    if (step === 1) {
      // Step 1 errors: Required components selected, quantity errors for required components
      return errors.filter(
        (e: BundleErrorDetail) => e.type === "REQUIRED_COMPONENT" || (e.type === "QUANTITY" && selectedBundle?.components.find((c) => c.id === e.component_id)?.required)
      );
    }
    if (step === 2) {
      // Step 2 errors: Nested product configuration failures
      return errors.filter((e: BundleErrorDetail) => e.type === "CONFIGURATION");
    }
    if (step === 3) {
      // Step 3 errors: Optional components quantity errors, active products errors
      return errors.filter(
        (e: BundleErrorDetail) => e.type === "INACTIVE_PRODUCT" || (e.type === "QUANTITY" && !selectedBundle?.components.find((c) => c.id === e.component_id)?.required)
      );
    }
    return errors;
  };

  const isStepValid = (step: 1 | 2 | 3 | 4) => {
    return getErrorsForStep(step).length === 0;
  };

  // --- Handlers ---

  const handleToggleSelectComp = (compId: number) => {
    setBundleSelections((prev) => {
      const prevVal = prev[compId];
      return {
        ...prev,
        [compId]: { ...prevVal, selected: !prevVal.selected }
      };
    });
  };

  const handleUpdateCompQuantity = (compId: number, val: number) => {
    setBundleSelections((prev) => {
      const prevVal = prev[compId];
      return {
        ...prev,
        [compId]: { ...prevVal, quantity: val }
      };
    });
  };

  // Configure option selection for configurable component inside Step 2
  const handleSelectProductOption = (group: ConfigurationGroup, option: any) => {
    if (!activeConfigCompId) return;

    setBundleSelections((prev) => {
      const prevComp = prev[activeConfigCompId];
      
      // Initialize or get current product configuration
      const prodConfig = prevComp.configuration || {
        product_id: activeConfigComp!.product_id,
        selections: [] as SelectionItem[]
      };

      const groupSel = prodConfig.selections.find((s) => s.group_id === group.id) || {
        group_id: group.id,
        option_ids: [],
        quantities: {}
      };

      let newOptionIds = [...groupSel.option_ids];
      const newQuantities = { ...groupSel.quantities };

      if (group.selection_type === "SINGLE_SELECT") {
        if (newOptionIds.includes(option.id)) {
          newOptionIds = [];
          delete newQuantities[option.id.toString()];
        } else {
          newOptionIds = [option.id];
          newQuantities[option.id.toString()] = 1;
        }
      } else {
        if (newOptionIds.includes(option.id)) {
          newOptionIds = newOptionIds.filter((id) => id !== option.id);
          delete newQuantities[option.id.toString()];
        } else {
          newOptionIds.push(option.id);
          newQuantities[option.id.toString()] = 1;
        }
      }

      // Rebuild selections list
      const cleanSelections = prodConfig.selections.filter((s) => s.group_id !== group.id);
      if (newOptionIds.length > 0) {
        cleanSelections.push({
          group_id: group.id,
          option_ids: newOptionIds,
          quantities: newQuantities
        });
      }

      return {
        ...prev,
        [activeConfigCompId]: {
          ...prevComp,
          configuration: {
            ...prodConfig,
            selections: cleanSelections
          }
        }
      };
    });
  };

  const handleUpdateProductOptionQuantity = (groupId: number, optionId: number, qty: number) => {
    if (!activeConfigCompId) return;

    setBundleSelections((prev) => {
      const prevComp = prev[activeConfigCompId];
      if (!prevComp.configuration) return prev;

      const updatedSelections = prevComp.configuration.selections.map((sel) => {
        if (sel.group_id === groupId) {
          return {
            ...sel,
            quantities: {
              ...sel.quantities,
              [optionId.toString()]: qty
            }
          };
        }
        return sel;
      });

      return {
        ...prev,
        [activeConfigCompId]: {
          ...prevComp,
          configuration: {
            ...prevComp.configuration,
            selections: updatedSelections
          }
        }
      };
    });
  };

  const handleSaveBundleSession = () => {
    if (!selectedBundleId) return;

    const selectionsPayload = Object.values(bundleSelections).map((sel) => ({
      component_id: sel.component_id,
      selected: sel.selected,
      quantity: sel.quantity,
      configuration: sel.configuration
    }));

    saveSessionMutation.mutate({
      bundle_id: selectedBundleId,
      selections: selectionsPayload
    });
  };

  const handleSeedSolutionBundle = async () => {
    try {
      const existingProds = await api.get<any[]>("/pricing/products");
      
      let prodCore = existingProds.find((p) => p.sku === "CORE-SVR-SEED");
      if (!prodCore) {
        prodCore = await api.post<any>("/products", {
          sku: "CORE-SVR-SEED",
          name: "Enterprise Core Server Platform",
          description: "Robust hardware IT infrastructure node",
          base_price: 3500.00,
          currency: "USD",
          billing_type: "NRC",
          pricing_method: "STANDARD"
        });
      }

      let prodSub = existingProds.find((p) => p.sku === "SaaS-TIER-SEED");
      if (!prodSub) {
        prodSub = await api.post<any>("/products", {
          sku: "SaaS-TIER-SEED",
          name: "Enterprise Cloud Subscription",
          description: "Base platform license with optional features",
          base_price: 49.00,
          currency: "USD",
          billing_type: "MRC",
          pricing_method: "STANDARD"
        });
      }

      let prodAnl = existingProds.find((p) => p.sku === "ANL-MOD-SEED");
      if (!prodAnl) {
        prodAnl = await api.post<any>("/products", {
          sku: "ANL-MOD-SEED",
          name: "AI Analytics Add-on Node",
          description: "Optional analytics nodes",
          base_price: 250.00,
          currency: "USD",
          billing_type: "MRC",
          pricing_method: "STANDARD"
        });
      }

      // Seed Configuration Options for prodSub
      let planGroup;
      const existingGroups = await api.get<any[]>(`/configuration/products/${prodSub.id}`);
      planGroup = existingGroups.find((g) => g.name === "Plan Level");
      if (!planGroup) {
        planGroup = await api.post<any>("/configuration/groups", {
          product_id: prodSub.id,
          name: "Plan Level",
          description: "Subscription tier level",
          required: true,
          selection_type: "SINGLE_SELECT",
          display_order: 1
        });
        await api.post<any>("/configuration/options", {
          group_id: planGroup.id,
          name: "Professional Cloud Tier",
          value: "professional",
          display_order: 1
        });
      }

      // Create Bundle
      const existingBundles = await api.get<any[]>("/configuration/bundles");
      let seededBundle = existingBundles.find((b) => b.sku === "BNDL-SYS-SEED");
      if (!seededBundle) {
        seededBundle = await api.post<any>("/configuration/bundles", {
          name: "Enterprise IT System Solution",
          description: "Bundled package containing Core Server hardware and Cloud SaaS subscriptions",
          sku: "BNDL-SYS-SEED"
        });

        // Add Components
        await api.post<any>(`/configuration/bundles/${seededBundle.id}/components`, {
          product_id: prodCore.id,
          required: true,
          default_selected: true,
          min_quantity: 1,
          max_quantity: 4,
          default_quantity: 1,
          display_order: 1
        });

        await api.post<any>(`/configuration/bundles/${seededBundle.id}/components`, {
          product_id: prodSub.id,
          required: true,
          default_selected: true,
          min_quantity: 1,
          max_quantity: 10,
          default_quantity: 1,
          display_order: 2
        });

        await api.post<any>(`/configuration/bundles/${seededBundle.id}/components`, {
          product_id: prodAnl.id,
          required: false,
          default_selected: false,
          min_quantity: 1,
          max_quantity: 10,
          default_quantity: 1,
          display_order: 3
        });
      }

      refetchBundles();
      alert("Sample IT Solution Bundle seeded successfully!");
    } catch (err) {
      console.error(err);
      alert("Seeding error occurred.");
    }
  };

  return (
    <div className="space-y-6">
      
      {/* Header and Switcher Tabs */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 bg-zinc-900 border border-zinc-800 p-6 rounded-2xl shadow-xl">
        <div className="space-y-1">
          <h1 className="text-2xl font-extrabold tracking-tight text-zinc-100 flex items-center gap-2">
            <Briefcase className="text-teal-400" size={26} />
            <span>Guided Solution Configurator</span>
          </h1>
          <p className="text-xs text-zinc-400">
            Define sellable bundles, configure component parameters, and review system validation rules.
          </p>
        </div>

        {/* Tab switchers if authorized */}
        <div className="flex bg-zinc-950 p-1.5 rounded-xl border border-zinc-800 self-stretch md:self-auto">
          <button
            onClick={() => {
              setActiveTab("configure");
              setEditingBundle(null);
            }}
            className={`flex items-center gap-2 px-4 py-2 text-xs font-bold rounded-lg transition ${
              activeTab === "configure"
                ? "bg-zinc-800 text-teal-400 shadow"
                : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            <Wrench size={14} />
            <span>Configure Solution</span>
          </button>
          {isExecutive && (
            <button
              onClick={() => setActiveTab("admin")}
              className={`flex items-center gap-2 px-4 py-2 text-xs font-bold rounded-lg transition ${
                activeTab === "admin"
                  ? "bg-zinc-800 text-teal-400 shadow"
                  : "text-zinc-400 hover:text-zinc-200"
              }`}
            >
              <Settings size={14} />
              <span>Solution Builder</span>
            </button>
          )}
        </div>
      </div>

      {activeTab === "configure" ? (
        
        // --- Tab 1: Guided Configuration Wizard ---
        selectedBundleId ? (
          
          /* Wiz Grid */
          <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 items-start">
            
            {/* Left side: Step Navigation Progress Tracker */}
            <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-5 space-y-4">
              <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-500">
                Solution Progress
              </h3>

              {/* Progress circles stack */}
              <div className="relative pl-6 space-y-6">
                <div className="absolute left-2.5 top-2.5 bottom-2.5 w-0.5 bg-zinc-800" />
                
                {[
                  { step: 1, name: "Core components", desc: "Select required elements" },
                  { step: 2, name: "Configure products", desc: "Configure parameter tiers" },
                  { step: 3, name: "Optional add-ons", desc: "Attach analytics & add-ons" },
                  { step: 4, name: "Review & validate", desc: "Complete configuration checks" }
                ].map((s) => {
                  const isActive = guidedStep === s.step;
                  const isDone = guidedStep > s.step;
                  
                  return (
                    <div key={s.step} className="relative flex gap-3 text-left">
                      <div className={`absolute -left-6 w-5.5 h-5.5 rounded-full border flex items-center justify-center text-[10px] font-bold transition-all duration-200 ${
                        isActive
                          ? "bg-teal-500/10 border-teal-500 text-teal-400 shadow-md shadow-teal-500/5 scale-110"
                          : isDone
                          ? "bg-teal-500 border-teal-500 text-zinc-950"
                          : "bg-zinc-950 border-zinc-800 text-zinc-500"
                      }`}>
                        {isDone ? <Check size={10} strokeWidth={3} /> : s.step}
                      </div>
                      <div className="space-y-0.5 ml-2">
                        <span className={`text-xs font-bold block ${isActive ? "text-teal-400" : isDone ? "text-zinc-300" : "text-zinc-500"}`}>
                          {s.name}
                        </span>
                        <span className="text-[10px] text-zinc-500 block leading-tight">
                          {s.desc}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Action buttons */}
              <div className="border-t border-zinc-800 pt-4 flex flex-col gap-2">
                <div className="flex gap-2">
                  <button
                    disabled={guidedStep === 1}
                    onClick={() => setGuidedStep((prev) => (prev - 1) as any)}
                    className="flex-1 flex items-center justify-center gap-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 py-2.5 rounded-xl text-xs font-bold transition disabled:opacity-40"
                  >
                    <ChevronLeft size={14} /> Back
                  </button>
                  <button
                    disabled={guidedStep === 4 || !isStepValid(guidedStep)}
                    onClick={() => setGuidedStep((prev) => (prev + 1) as any)}
                    className="flex-1 flex items-center justify-center gap-1.5 bg-teal-500 hover:bg-teal-400 text-zinc-950 py-2.5 rounded-xl text-xs font-bold transition disabled:opacity-40"
                  >
                    Next <ChevronRight size={14} />
                  </button>
                </div>
                
                {!isStepValid(guidedStep) && (
                  <div className="text-[10px] text-red-400 flex items-start gap-1 p-2 rounded bg-red-950/10 border border-red-900/20">
                    <AlertCircle size={12} className="shrink-0 mt-0.5" />
                    <span>Configure all required selections and options correctly to proceed.</span>
                  </div>
                )}

                <button
                  onClick={() => {
                    setSelectedBundleId("");
                    setGuidedStep(1);
                  }}
                  className="w-full text-center text-[10px] text-zinc-500 hover:text-zinc-300 py-1.5 transition"
                >
                  Exit Configurator
                </button>
              </div>
            </div>

            {/* Center Area: Step Content Controls */}
            <div className="lg:col-span-2 bg-zinc-900 border border-zinc-800 rounded-2xl p-6 min-h-[350px] space-y-6">
              
              {/* Step 1: Choose Core Components (Required Components) */}
              {guidedStep === 1 && (
                <div className="space-y-6">
                  <div>
                    <h2 className="text-lg font-bold text-zinc-100 flex items-center gap-2">
                      <Layers className="text-teal-400" size={20} />
                      <span>Step 1: Choose Core Components</span>
                    </h2>
                    <p className="text-xs text-zinc-500">
                      Required components are core elements of this package. Maintain the quantities within limits.
                    </p>
                  </div>

                  <div className="space-y-3">
                    {selectedBundle?.components
                      .filter((c) => c.required && c.is_active)
                      .map((comp) => {
                        const sel = bundleSelections[comp.id] || { quantity: comp.default_quantity };
                        const prod = comp.product;
                        if (!prod) return null;

                        return (
                          <div key={comp.id} className="bg-zinc-950 border border-zinc-850 p-4 rounded-xl flex items-center justify-between gap-4">
                            <div className="space-y-1">
                              <span className="px-2 py-0.5 rounded text-[8px] bg-teal-500/10 border border-teal-500/20 text-teal-400 font-bold uppercase tracking-wider">Required</span>
                              <h4 className="text-sm font-semibold text-zinc-200">{prod.name}</h4>
                              <p className="text-[10px] font-mono text-zinc-500">SKU: {prod.sku}</p>
                            </div>

                            <div className="flex items-center gap-3 bg-zinc-900 border border-zinc-800 p-2 rounded-xl">
                              <span className="text-[10px] font-bold text-zinc-500 uppercase">Quantity:</span>
                              <input
                                type="number"
                                value={sel.quantity}
                                min={comp.min_quantity}
                                max={comp.max_quantity || undefined}
                                onChange={(e) => handleUpdateCompQuantity(comp.id, parseInt(e.target.value) || 0)}
                                className="bg-zinc-950 border border-zinc-800 text-zinc-200 font-mono text-xs w-16 px-2 py-0.5 rounded text-center focus:outline-none focus:border-teal-500"
                              />
                            </div>
                          </div>
                        );
                      })}
                  </div>
                </div>
              )}

              {/* Step 2: Product Configuration (Configure Configurable Products) */}
              {guidedStep === 2 && (
                <div className="space-y-6">
                  <div>
                    <h2 className="text-lg font-bold text-zinc-100 flex items-center gap-2">
                      <Sliders className="text-teal-400" size={20} />
                      <span>Step 2: Configure Products</span>
                    </h2>
                    <p className="text-xs text-zinc-500">
                      Configure custom attribute options for configurable software or devices in the bundle.
                    </p>
                  </div>

                  {/* Configurable components tabs switcher */}
                  {selectedBundle?.components.filter((c) => bundleSelections[c.id]?.selected && c.is_active).some((c) => c.product?.billing_type !== "NRC") ? (
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                      {selectedBundle.components
                        .filter((c) => bundleSelections[c.id]?.selected && c.is_active)
                        .map((comp) => {
                          const isConfigurable = true; // In Phase 2 context we assume configurable if groups exist
                          const isActive = activeConfigCompId === comp.id;
                          const sel = bundleSelections[comp.id];

                          return (
                            <button
                              key={comp.id}
                              onClick={() => {
                                setActiveConfigCompId(comp.id);
                                setActiveConfigGroupId(null);
                              }}
                              className={`flex flex-col gap-1 items-start text-left p-3 rounded-xl border text-xs font-semibold transition ${
                                isActive
                                  ? "bg-zinc-800 border-teal-500 text-zinc-100"
                                  : "bg-zinc-950 border-zinc-850 text-zinc-400 hover:border-zinc-800 hover:text-zinc-200"
                              }`}
                            >
                              <span className="font-bold truncate w-full">{comp.product?.name}</span>
                              <span className="text-[9px] font-mono text-zinc-500">SKU: {comp.product?.sku}</span>
                            </button>
                          );
                        })}
                    </div>
                  ) : (
                    <div className="text-center py-10 text-zinc-500 text-xs italic">
                      No configurable products detected in bundle core.
                    </div>
                  )}

                  {/* Configure product workspace (embed Phase 1 Configuration UI logic) */}
                  {activeConfigCompId && (
                    <div className="border border-zinc-800 rounded-xl p-4 bg-zinc-950/20 space-y-4">
                      {isLoadingConfigGroups ? (
                        <div className="flex justify-center items-center py-10">
                          <Loader2 className="animate-spin text-teal-400" size={24} />
                        </div>
                      ) : !configGroups || configGroups.length === 0 ? (
                        <div className="text-center py-8 text-zinc-500 text-xs italic">
                          This product does not have any custom configuration attributes configured.
                        </div>
                      ) : (
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                          
                          {/* Attributes groups tabs */}
                          <div className="space-y-1.5">
                            {configGroups.map((g) => (
                              <button
                                key={g.id}
                                onClick={() => setActiveConfigGroupId(g.id)}
                                className={`w-full text-left px-3 py-2 rounded text-xs font-medium transition ${
                                  activeConfigGroupId === g.id
                                    ? "bg-zinc-800 text-zinc-100"
                                    : "text-zinc-400 hover:bg-zinc-900"
                                }`}
                              >
                                {g.name} {g.required && <span className="text-red-400">*</span>}
                              </button>
                            ))}
                          </div>

                          {/* Options grid */}
                          <div className="md:col-span-2 space-y-3">
                            {(() => {
                              const group = configGroups.find((g) => g.id === activeConfigGroupId);
                              if (!group) return null;
                              const compSel = bundleSelections[activeConfigCompId] || {};
                              const configSel = compSel.configuration || { selections: [] };
                              const groupSel = (configSel.selections.find((s) => s.group_id === group.id) || { group_id: group.id, option_ids: [], quantities: {} }) as SelectionItem;

                              return (
                                <div className="space-y-2">
                                  <h4 className="text-xs font-bold text-zinc-300">{group.name} options:</h4>
                                  <div className="space-y-2">
                                    {group.options.map((opt) => {
                                      const isSelected = groupSel.option_ids.includes(opt.id);
                                      return (
                                        <div
                                          key={opt.id}
                                          className={`border p-3 rounded-lg flex items-center justify-between gap-3 text-xs transition ${
                                            isSelected ? "bg-zinc-850 border-teal-500/40 text-teal-400" : "bg-zinc-950 border-zinc-900 text-zinc-300"
                                          }`}
                                        >
                                          <button
                                            onClick={() => handleSelectProductOption(group, opt)}
                                            className="flex-1 text-left font-semibold"
                                          >
                                            {opt.name}
                                          </button>
                                          {isSelected && (opt.min_quantity || opt.max_quantity) && (
                                            <input
                                              type="number"
                                              value={groupSel.quantities?.[opt.id.toString()] || 1}
                                              onChange={(e) => handleUpdateProductOptionQuantity(group.id, opt.id, parseInt(e.target.value) || 1)}
                                              className="bg-zinc-900 border border-zinc-850 text-zinc-200 text-center w-12 rounded"
                                            />
                                          )}
                                        </div>
                                      );
                                    })}
                                  </div>
                                </div>
                              );
                            })()}
                          </div>

                        </div>
                      )}
                    </div>
                  )}

                </div>
              )}

              {/* Step 3: Select Optional Add-ons */}
              {guidedStep === 3 && (
                <div className="space-y-6">
                  <div>
                    <h2 className="text-lg font-bold text-zinc-100 flex items-center gap-2">
                      <Sparkles className="text-teal-400" size={20} />
                      <span>Step 3: Select Optional Add-ons</span>
                    </h2>
                    <p className="text-xs text-zinc-500">
                      Expand the core solution with optional plug-ins, support parameters, or resource add-ons.
                    </p>
                  </div>

                  <div className="space-y-3">
                    {selectedBundle?.components.filter((c) => !c.required && c.is_active).length === 0 ? (
                      <div className="text-center py-10 text-zinc-500 text-xs italic">
                        No optional add-ons configured for this solution bundle.
                      </div>
                    ) : (
                      selectedBundle?.components
                        .filter((c) => !c.required && c.is_active)
                        .map((comp) => {
                          const sel = bundleSelections[comp.id] || { selected: false, quantity: comp.default_quantity };
                          const prod = comp.product;
                          if (!prod) return null;

                          return (
                            <div
                              key={comp.id}
                              className={`border p-4 rounded-xl flex items-center justify-between gap-4 transition ${
                                sel.selected ? "bg-zinc-850 border-teal-500/30" : "bg-zinc-950 border-zinc-900 hover:border-zinc-800"
                              }`}
                            >
                              <div className="flex items-center gap-3">
                                <button
                                  onClick={() => handleToggleSelectComp(comp.id)}
                                  className={`w-4 h-4 rounded border flex items-center justify-center transition ${
                                    sel.selected ? "border-teal-400 bg-teal-400/10" : "border-zinc-700"
                                  }`}
                                >
                                  {sel.selected && <Check size={10} className="text-teal-400" strokeWidth={3} />}
                                </button>
                                <div className="space-y-0.5">
                                  <h4 className={`text-sm font-semibold transition ${sel.selected ? "text-teal-400" : "text-zinc-200"}`}>
                                    {prod.name}
                                  </h4>
                                  <p className="text-[10px] font-mono text-zinc-500">SKU: {prod.sku}</p>
                                </div>
                              </div>

                              {sel.selected && (
                                <div className="flex items-center gap-2 bg-zinc-900 border border-zinc-800 p-1.5 rounded-lg">
                                  <span className="text-[9px] font-bold text-zinc-500 uppercase">Qty:</span>
                                  <input
                                    type="number"
                                    value={sel.quantity}
                                    min={comp.min_quantity}
                                    max={comp.max_quantity || undefined}
                                    onChange={(e) => handleUpdateCompQuantity(comp.id, parseInt(e.target.value) || 0)}
                                    className="bg-zinc-950 border border-zinc-800 text-zinc-200 text-center w-12 rounded font-mono text-xs"
                                  />
                                </div>
                              )}
                            </div>
                          );
                        })
                    )}
                  </div>
                </div>
              )}

              {/* Step 4: Configuration Review */}
              {guidedStep === 4 && (
                <div className="space-y-6">
                  <div>
                    <h2 className="text-lg font-bold text-zinc-100 flex items-center gap-2">
                      <CheckCircle className="text-teal-400" size={20} />
                      <span>Step 4: Review Solution Configuration</span>
                    </h2>
                    <p className="text-xs text-zinc-500">
                      Check validation constraints and compile final output structures.
                    </p>
                  </div>

                  <div className="border border-zinc-800 rounded-xl bg-zinc-950/40 p-4 space-y-3">
                    <div className="flex justify-between items-center border-b border-zinc-800 pb-2">
                      <span className="text-xs font-bold text-zinc-400 uppercase tracking-wide">Component Name</span>
                      <span className="text-xs font-bold text-zinc-400 uppercase tracking-wide">Status</span>
                    </div>

                    <div className="space-y-2">
                      {selectedBundle?.components
                        .filter((comp) => comp.is_active)
                        .map((comp) => {
                          const sel = bundleSelections[comp.id];
                          const isSelected = sel?.selected;
                          if (!comp.required && !isSelected) return null;

                          const product = comp.product;
                          // If configurable product, check if there's configuration error
                          const configErr = errors.find((e: BundleErrorDetail) => e.component_id === comp.id && e.type === "CONFIGURATION");
                          const qtyErr = errors.find((e: BundleErrorDetail) => e.component_id === comp.id && e.type === "QUANTITY");
                          const isConfigured = sel?.configuration?.selections && sel.configuration.selections.length > 0;

                          return (
                            <div key={comp.id} className="flex justify-between items-center text-xs p-2.5 rounded bg-zinc-900 border border-zinc-850">
                              <div className="space-y-1">
                                <span className="font-bold text-zinc-200">{product?.name}</span>
                                <div className="text-[10px] text-zinc-500">
                                  SKU: {product?.sku} | Qty: <span className="text-zinc-300 font-bold">{sel?.quantity}</span>
                                </div>
                              </div>
                              <div>
                                {configErr ? (
                                  <span className="text-red-400 font-bold flex items-center gap-1">
                                    <AlertCircle size={12} /> Conf Required
                                  </span>
                                ) : qtyErr ? (
                                  <span className="text-red-400 font-bold flex items-center gap-1">
                                    <AlertCircle size={12} /> Qty Limit Error
                                  </span>
                                ) : isConfigured ? (
                                  <span className="text-teal-400 font-bold flex items-center gap-1">
                                    <CheckCircle size={12} /> Conf Valid
                                  </span>
                                ) : (
                                  <span className="text-zinc-400 flex items-center gap-1">
                                    <CheckCircle size={12} /> Valid
                                  </span>
                                )}
                              </div>
                            </div>
                          );
                        })}
                    </div>
                  </div>
                </div>
              )}

            </div>

            {/* Right Side Panel: Live Solution Summary */}
            <div className="space-y-6">
              
              {/* Summary details card */}
              <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 space-y-4">
                <div className="border-b border-zinc-800 pb-3">
                  <h3 className="font-bold text-zinc-200 text-sm uppercase tracking-wider">
                    Bundle Summary
                  </h3>
                  <div className="mt-1 flex flex-col gap-0.5">
                    <span className="text-sm font-bold text-zinc-100">{selectedBundle?.name}</span>
                    <span className="text-[10px] font-mono text-zinc-500">SKU: {selectedBundle?.sku}</span>
                  </div>
                </div>

                <div className="space-y-3 min-h-[120px] max-h-[250px] overflow-y-auto pr-1">
                  {selectedBundle?.components.map((comp) => {
                    const sel = bundleSelections[comp.id];
                    if (!sel?.selected) return null;

                    return (
                      <div key={comp.id} className="space-y-1">
                        <span className="text-[9px] font-bold text-zinc-500 uppercase tracking-wider">
                          {comp.required ? "Required Core" : "Optional Add-on"}
                        </span>
                        <div className="flex justify-between items-center text-xs bg-zinc-950/40 border border-zinc-850 px-3 py-2 rounded-xl">
                          <span className="text-zinc-300 font-medium truncate max-w-[120px]">
                            {comp.product?.name}
                          </span>
                          <span className="text-zinc-500 font-mono text-[10px]">
                            Qty: <span className="text-zinc-300 font-bold">{sel.quantity}</span>
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>

                {/* Validation Status Indicator */}
                <div className="border-t border-zinc-800 pt-4 space-y-3">
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider">Status:</span>
                    {validateMutation.isPending ? (
                      <span className="flex items-center gap-1 text-xs text-zinc-400">
                        <Loader2 className="animate-spin text-zinc-500" size={14} /> Validating...
                      </span>
                    ) : isValid ? (
                      <span className="flex items-center gap-1 text-xs text-teal-400 font-bold">
                        <CheckCircle size={14} /> Ready to Save
                      </span>
                    ) : (
                      <span className="flex items-center gap-1 text-xs text-red-400 font-bold">
                        <ShieldAlert size={14} /> Validation Warning
                      </span>
                    )}
                  </div>

                  {errors.length > 0 && (
                    <div className="bg-red-950/20 border border-red-900/30 rounded-xl p-3 space-y-2 max-h-[150px] overflow-y-auto">
                      {errors.map((err: any, idx: number) => (
                        <div key={idx} className="flex items-start gap-2 text-xs text-red-400">
                          <AlertCircle size={14} className="mt-0.5 shrink-0" />
                          <span>{err.message}</span>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Save Session CTA Button */}
                  <button
                    onClick={handleSaveBundleSession}
                    disabled={!isValid || saveSessionMutation.isPending}
                    className="w-full bg-teal-500 hover:bg-teal-400 text-zinc-950 font-bold py-2.5 rounded-xl text-xs transition shadow-lg shadow-teal-500/10 disabled:opacity-40"
                  >
                    {saveSessionMutation.isPending ? "Saving..." : "Save Bundle Configuration"}
                  </button>
                </div>
              </div>

            </div>
          </div>
        ) : (
          /* Landing Solution lists selector */
          <div className="space-y-6">
            <div className="flex justify-between items-center">
              <h2 className="text-lg font-bold text-zinc-100">Select a Solution Bundle to Configure</h2>
              {isExecutive && (
                <button
                  onClick={handleSeedSolutionBundle}
                  className="flex items-center gap-2 bg-zinc-800 border border-zinc-700 text-zinc-200 px-3 py-1.5 rounded-xl text-xs font-semibold hover:bg-zinc-700 transition"
                >
                  <PlusCircle size={14} />
                  <span>Seed Sample IT Solution</span>
                </button>
              )}
            </div>

            {isLoadingBundles ? (
              <div className="flex justify-center items-center py-20">
                <Loader2 className="animate-spin text-teal-400" size={32} />
              </div>
            ) : !bundles || bundles.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-24 gap-4 text-zinc-500 bg-zinc-900/30 border border-zinc-850 border-dashed rounded-3xl">
                <Briefcase size={48} className="text-zinc-600 animate-pulse" />
                <span className="text-sm font-semibold text-center px-4">
                  {isExecutive 
                    ? "No solution bundles configured. Switch to the 'Solution Builder' tab to build them, or click 'Seed Sample IT Solution' above."
                    : "No solution bundles configured. Log in as Executive to build them."}
                </span>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {bundles.map((bundle) => (
                  <div
                    key={bundle.id}
                    className="bg-zinc-900 border border-zinc-800 p-6 rounded-2xl flex flex-col justify-between gap-4 hover:border-zinc-700 transition duration-200"
                  >
                    <div className="space-y-2">
                      <div className="flex justify-between items-start">
                        <h3 className="font-bold text-zinc-100 text-base">{bundle.name}</h3>
                        <span className="px-2 py-0.5 rounded text-[9px] bg-zinc-850 border border-zinc-800 text-zinc-400 font-mono">
                          {bundle.sku}
                        </span>
                      </div>
                      <p className="text-xs text-zinc-500 line-clamp-3">{bundle.description || "No description set."}</p>
                      <div className="flex items-center gap-2 text-[10px] text-zinc-400 pt-2 border-t border-zinc-950">
                        <Info size={12} />
                        <span>Contains {bundle.components.length} products.</span>
                      </div>
                    </div>

                    <button
                      onClick={() => setSelectedBundleId(bundle.id)}
                      className="w-full bg-teal-500 hover:bg-teal-400 text-zinc-950 text-xs font-bold py-2 rounded-xl flex items-center justify-center gap-1.5 transition"
                    >
                      <span>Configure Bundle</span>
                      <ArrowRight size={14} />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )

      ) : (
        
        // --- Tab 2: Solution Builder Administrative Interface (Executive Only) ---
        isExecutive && (
          editingBundle ? (
            /* Editing Bundle Workspace */
            <div className="space-y-6">
              <div className="flex justify-between items-center">
                <div className="space-y-1">
                  <button
                    onClick={() => setEditingBundle(null)}
                    className="text-xs text-zinc-400 hover:text-zinc-200 flex items-center gap-1"
                  >
                    <ChevronLeft size={12} /> Back to list
                  </button>
                  <h2 className="text-xl font-bold text-zinc-100">Edit Bundle: {editingBundle.name}</h2>
                </div>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
                
                {/* Bundle meta configuration details */}
                <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 space-y-4">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-500">Bundle Details</h3>
                  <div className="space-y-3">
                    <div>
                      <label className="text-[10px] font-bold text-zinc-500 uppercase block mb-1">Bundle Name</label>
                      <input
                        type="text"
                        value={editingBundle.name}
                        onChange={(e) => setEditingBundle({ ...editingBundle, name: e.target.value })}
                        className="w-full bg-zinc-950 border border-zinc-850 px-3 py-2 rounded-xl text-xs text-zinc-200 focus:outline-none focus:border-teal-500"
                      />
                    </div>
                    <div>
                      <label className="text-[10px] font-bold text-zinc-500 uppercase block mb-1">SKU / Bundle Code</label>
                      <input
                        type="text"
                        value={editingBundle.sku}
                        onChange={(e) => setEditingBundle({ ...editingBundle, sku: e.target.value })}
                        className="w-full bg-zinc-950 border border-zinc-850 px-3 py-2 rounded-xl text-xs text-zinc-200 focus:outline-none focus:border-teal-500"
                      />
                    </div>
                    <div>
                      <label className="text-[10px] font-bold text-zinc-500 uppercase block mb-1">Description</label>
                      <textarea
                        value={editingBundle.description || ""}
                        onChange={(e) => setEditingBundle({ ...editingBundle, description: e.target.value })}
                        className="w-full bg-zinc-950 border border-zinc-850 px-3 py-2 rounded-xl text-xs text-zinc-200 focus:outline-none focus:border-teal-500 h-24"
                      />
                    </div>
                    
                    <button
                      onClick={() => updateBundleMutation.mutate({
                        id: editingBundle.id,
                        data: {
                          name: editingBundle.name,
                          sku: editingBundle.sku,
                          description: editingBundle.description
                        }
                      })}
                      className="w-full bg-teal-500 hover:bg-teal-400 text-zinc-950 text-xs font-bold py-2.5 rounded-xl transition"
                    >
                      Save Bundle Metadata
                    </button>

                    {/* Versioning and Lifecycle control panel */}
                    <div className="border-t border-zinc-800 pt-4 mt-4 space-y-4">
                      <h4 className="text-xs font-bold uppercase tracking-wider text-zinc-400">Blueprints Versions</h4>
                      
                      <div className="flex gap-2">
                        <button
                          onClick={() => {
                            setSelectedVersionEntity({ type: "BUNDLE", id: editingBundle.id });
                            setShowVersionHistoryModal(true);
                          }}
                          className="flex-1 bg-zinc-950 hover:bg-zinc-900 border border-zinc-800 text-zinc-300 text-xs font-bold py-2 rounded-xl transition flex items-center justify-center gap-1"
                        >
                          <Layers size={14} /> Version History
                        </button>
                        <button
                          onClick={() => createDraftMutation.mutate({ type: "BUNDLE", id: editingBundle.id })}
                          className="flex-1 bg-teal-500/10 hover:bg-teal-500/20 border border-teal-500/20 text-teal-400 text-xs font-bold py-2 rounded-xl transition flex items-center justify-center gap-1"
                        >
                          <PlusCircle size={14} /> Create Draft
                        </button>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Bundle components config list */}
                <div className="lg:col-span-2 space-y-6">
                  
                  {/* Components settings table */}
                  <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 space-y-4">
                    <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-500">Components List</h3>
                    <div className="border border-zinc-850 rounded-xl overflow-hidden">
                      <table className="w-full text-xs text-left">
                        <thead className="bg-zinc-950 text-zinc-400">
                          <tr>
                            <th className="p-3">Product SKU</th>
                            <th className="p-3">Product Name</th>
                            <th className="p-3">Required</th>
                            <th className="p-3">Min Qty</th>
                            <th className="p-3">Max Qty</th>
                            <th className="p-3">Default Qty</th>
                            <th className="p-3">Actions</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-zinc-850 text-zinc-300">
                          {editingBundle.components.map((comp) => (
                            <tr key={comp.id}>
                              <td className="p-3 font-mono">{comp.product?.sku}</td>
                              <td className="p-3">{comp.product?.name}</td>
                              <td className="p-3">{comp.required ? "Yes" : "No"}</td>
                              <td className="p-3 font-mono">{comp.min_quantity}</td>
                              <td className="p-3 font-mono">{comp.max_quantity || "Unlimited"}</td>
                              <td className="p-3 font-mono">{comp.default_quantity}</td>
                              <td className="p-3">
                                <button
                                  onClick={() => deleteComponentMutation.mutate({ bundleId: editingBundle.id, compId: comp.id })}
                                  className="text-red-400 hover:text-red-300 transition"
                                >
                                  <Trash2 size={14} />
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>

                  {/* Add component configuration widget */}
                  <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 space-y-4">
                    <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-500">Add Product Component</h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div>
                        <label className="text-[10px] font-bold text-zinc-500 uppercase block mb-1">Catalog Product</label>
                        <select
                          value={addComponentProductId}
                          onChange={(e) => setAddComponentProductId(e.target.value ? parseInt(e.target.value) : "")}
                          className="w-full bg-zinc-950 border border-zinc-850 px-3 py-2 rounded-xl text-xs text-zinc-300 focus:outline-none focus:border-teal-500"
                        >
                          <option value="">-- Choose Product --</option>
                          {catalogProducts?.map((p) => (
                            <option key={p.id} value={p.id}>
                              {p.name} ({p.sku})
                            </option>
                          ))}
                        </select>
                      </div>

                      <div className="flex items-center gap-3">
                        <button
                          onClick={() => setAddComponentRequired(!addComponentRequired)}
                          className={`w-4 h-4 rounded border flex items-center justify-center transition ${
                            addComponentRequired ? "border-teal-400 bg-teal-400/10" : "border-zinc-700"
                          }`}
                        >
                          {addComponentRequired && <Check size={10} className="text-teal-400" strokeWidth={3} />}
                        </button>
                        <span className="text-xs text-zinc-400 font-semibold">Required element</span>
                      </div>

                      <div>
                        <label className="text-[10px] font-bold text-zinc-500 uppercase block mb-1">Min Quantity</label>
                        <input
                          type="number"
                          value={addComponentMinQty}
                          onChange={(e) => setAddComponentMinQty(parseInt(e.target.value) || 1)}
                          className="w-full bg-zinc-950 border border-zinc-850 px-3 py-2 rounded-xl text-xs text-zinc-300 focus:outline-none focus:border-teal-500"
                        />
                      </div>

                      <div>
                        <label className="text-[10px] font-bold text-zinc-500 uppercase block mb-1">Max Quantity (Optional)</label>
                        <input
                          type="number"
                          value={addComponentMaxQty}
                          onChange={(e) => setAddComponentMaxQty(e.target.value ? parseInt(e.target.value) : "")}
                          className="w-full bg-zinc-950 border border-zinc-850 px-3 py-2 rounded-xl text-xs text-zinc-300 focus:outline-none focus:border-teal-500"
                        />
                      </div>

                      <div>
                        <label className="text-[10px] font-bold text-zinc-500 uppercase block mb-1">Default Quantity</label>
                        <input
                          type="number"
                          value={addComponentDefQty}
                          onChange={(e) => setAddComponentDefQty(parseInt(e.target.value) || 1)}
                          className="w-full bg-zinc-950 border border-zinc-850 px-3 py-2 rounded-xl text-xs text-zinc-300 focus:outline-none focus:border-teal-500"
                        />
                      </div>
                    </div>

                    <button
                      onClick={() => {
                        if (!addComponentProductId) return;
                        addComponentMutation.mutate({
                          bundleId: editingBundle.id,
                          data: {
                            product_id: addComponentProductId,
                            required: addComponentRequired,
                            min_quantity: addComponentMinQty,
                            max_quantity: addComponentMaxQty || null,
                            default_quantity: addComponentDefQty
                          }
                        });
                      }}
                      className="flex items-center gap-2 bg-teal-500 hover:bg-teal-400 text-zinc-950 font-bold px-4 py-2 rounded-xl text-xs transition"
                    >
                      <Plus size={14} /> Add Component
                    </button>
                  </div>

                </div>

              </div>
            </div>
          ) : (
            /* Admin Bundle Dashboard List */
            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <h2 className="text-lg font-bold text-zinc-100">Bundle Definitions</h2>
                <button
                  onClick={() => setShowCreateModal(true)}
                  className="flex items-center gap-2 bg-teal-500 hover:bg-teal-400 text-zinc-950 px-4 py-2 rounded-xl text-xs font-bold transition shadow-lg shadow-teal-500/10"
                >
                  <Plus size={16} /> Create Bundle
                </button>
              </div>

              {/* Create Bundle Dialog Modal */}
              {showCreateModal && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
                  <div className="bg-zinc-900 border border-zinc-800 rounded-2xl max-w-md w-full p-6 space-y-4">
                    <h3 className="text-base font-bold text-zinc-100">Create New Solution Bundle</h3>
                    
                    <div className="space-y-3">
                      <div>
                        <label className="text-[10px] font-bold text-zinc-500 uppercase block mb-1">Bundle Name</label>
                        <input
                          type="text"
                          value={newBundleName}
                          onChange={(e) => setNewBundleName(e.target.value)}
                          placeholder="Enterprise IT Platform"
                          className="w-full bg-zinc-950 border border-zinc-850 px-3 py-2 rounded-xl text-xs text-zinc-300 focus:outline-none focus:border-teal-500"
                        />
                      </div>
                      <div>
                        <label className="text-[10px] font-bold text-zinc-500 uppercase block mb-1">SKU / Bundle Code</label>
                        <input
                          type="text"
                          value={newBundleSku}
                          onChange={(e) => setNewBundleSku(e.target.value)}
                          placeholder="BNDL-ENT"
                          className="w-full bg-zinc-950 border border-zinc-850 px-3 py-2 rounded-xl text-xs text-zinc-300 focus:outline-none focus:border-teal-500"
                        />
                      </div>
                      <div>
                        <label className="text-[10px] font-bold text-zinc-500 uppercase block mb-1">Description</label>
                        <textarea
                          value={newBundleDesc}
                          onChange={(e) => setNewBundleDesc(e.target.value)}
                          placeholder="Enter details..."
                          className="w-full bg-zinc-950 border border-zinc-850 px-3 py-2 rounded-xl text-xs text-zinc-300 focus:outline-none focus:border-teal-500 h-24"
                        />
                      </div>
                    </div>

                    <div className="flex gap-2 justify-end pt-2">
                      <button
                        onClick={() => setShowCreateModal(false)}
                        className="bg-zinc-850 border border-zinc-800 hover:bg-zinc-800 text-zinc-300 px-4 py-2 rounded-xl text-xs font-semibold"
                      >
                        Cancel
                      </button>
                      <button
                        onClick={() => createBundleMutation.mutate({
                          name: newBundleName,
                          sku: newBundleSku,
                          description: newBundleDesc
                        })}
                        className="bg-teal-500 hover:bg-teal-400 text-zinc-950 px-4 py-2 rounded-xl text-xs font-bold"
                      >
                        Create
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {/* Bundles Admin Table */}
              <div className="bg-zinc-900 border border-zinc-800 rounded-2xl overflow-hidden shadow-xl">
                <table className="w-full text-xs text-left">
                  <thead className="bg-zinc-950 text-zinc-400">
                    <tr>
                      <th className="p-4">SKU / Bundle Code</th>
                      <th className="p-4">Bundle Name</th>
                      <th className="p-4">Components</th>
                      <th className="p-4">Status</th>
                      <th className="p-4 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-850 text-zinc-300">
                    {bundles?.map((b) => (
                      <tr key={b.id}>
                        <td className="p-4 font-mono">{b.sku}</td>
                        <td className="p-4 font-semibold">{b.name}</td>
                        <td className="p-4">{b.components.length} components</td>
                        <td className="p-4">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                            b.is_active ? "bg-teal-500/10 border border-teal-500/20 text-teal-400" : "bg-zinc-950 text-zinc-500"
                          }`}>
                            {b.is_active ? "Active" : "Inactive"}
                          </span>
                        </td>
                        <td className="p-4 text-right">
                          <button
                            onClick={() => setEditingBundle(b)}
                            className="bg-zinc-800 border border-zinc-700 hover:bg-zinc-700 text-zinc-200 px-3 py-1.5 rounded-xl text-[11px] font-semibold transition inline-flex items-center gap-1"
                          >
                            <Edit2 size={12} />
                            <span>Edit</span>
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {/* Version History Modal */}
              {showVersionHistoryModal && selectedVersionEntity && (
                <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
                  <div className="bg-zinc-950 border border-zinc-800 rounded-3xl w-full max-w-lg overflow-hidden shadow-2xl flex flex-col max-h-[85vh]">
                    <div className="p-6 border-b border-zinc-900 flex justify-between items-center bg-zinc-950">
                      <div>
                        <h3 className="text-lg font-bold text-zinc-100 flex items-center gap-2">
                          <Layers className="text-teal-400" size={20} />
                          <span>Blueprints Version History</span>
                        </h3>
                        <p className="text-[11px] text-zinc-500 mt-1">
                          Track changes, compare differences, and promote drafts.
                        </p>
                      </div>
                      <button
                        onClick={() => setShowVersionHistoryModal(false)}
                        className="text-zinc-500 hover:text-zinc-300 text-sm font-semibold"
                      >
                        Close
                      </button>
                    </div>

                    <div className="p-6 overflow-y-auto space-y-4 flex-1">
                      {versionsList && versionsList.length === 0 ? (
                        <div className="text-center py-8 text-zinc-500 text-xs italic">
                          No version records created yet. Create a draft to get started.
                        </div>
                      ) : (
                        versionsList?.map((v) => (
                          <div
                            key={v.id}
                            className="bg-zinc-900 border border-zinc-850 p-4 rounded-2xl flex items-center justify-between gap-4"
                          >
                            <div className="space-y-1">
                              <div className="flex items-center gap-2">
                                <span className="font-bold text-sm text-zinc-100">Version {v.version_number}</span>
                                <span className={`px-2 py-0.5 rounded text-[9px] font-bold ${
                                  v.status === "ACTIVE"
                                    ? "bg-teal-500/10 border border-teal-500/20 text-teal-400"
                                    : v.status === "DRAFT"
                                    ? "bg-yellow-500/10 border border-yellow-500/20 text-yellow-400"
                                    : "bg-zinc-950 text-zinc-500"
                                }`}>
                                  {v.status}
                                </span>
                              </div>
                              <p className="text-xs text-zinc-400">{v.change_summary || "No description provided."}</p>
                              <p className="text-[10px] text-zinc-500 font-mono">
                                Created: {new Date(v.created_at).toLocaleDateString()}
                              </p>
                            </div>

                            <div className="flex gap-2">
                              {v.status === "DRAFT" && (
                                <button
                                  onClick={() => activateVersionMutation.mutate(v.id)}
                                  className="bg-teal-500 hover:bg-teal-400 text-zinc-950 px-3 py-1.5 rounded-xl text-xs font-bold transition"
                                >
                                  Activate
                                </button>
                              )}
                              {v.status === "ACTIVE" && (
                                <button
                                  onClick={() => archiveVersionMutation.mutate(v.id)}
                                  className="bg-zinc-800 hover:bg-zinc-700 border border-zinc-750 text-zinc-300 px-3 py-1.5 rounded-xl text-xs font-semibold transition"
                                >
                                  Archive
                                </button>
                              )}
                            </div>
                          </div>
                        ))
                      )}

                      {versionsList && versionsList.length >= 2 && (
                        <div className="border-t border-zinc-900 pt-4 mt-2">
                          <h4 className="text-xs font-bold uppercase tracking-wider text-zinc-500 mb-3">Compare Blueprints</h4>
                          <div className="grid grid-cols-2 gap-3 mb-3">
                            <div>
                              <label className="text-[10px] text-zinc-500 uppercase block mb-1">Version A</label>
                              <select
                                value={versionAId}
                                onChange={(e) => setVersionAId(Number(e.target.value))}
                                className="w-full bg-zinc-900 border border-zinc-800 text-zinc-300 text-xs py-2 px-3 rounded-xl focus:outline-none focus:border-teal-500"
                              >
                                <option value="">Select version...</option>
                                {versionsList.map((v) => (
                                  <option key={v.id} value={v.id}>V{v.version_number} ({v.status})</option>
                                ))}
                              </select>
                            </div>
                            <div>
                              <label className="text-[10px] text-zinc-500 uppercase block mb-1">Version B</label>
                              <select
                                value={versionBId}
                                onChange={(e) => setVersionBId(Number(e.target.value))}
                                className="w-full bg-zinc-900 border border-zinc-800 text-zinc-300 text-xs py-2 px-3 rounded-xl focus:outline-none focus:border-teal-500"
                              >
                                <option value="">Select version...</option>
                                {versionsList.map((v) => (
                                  <option key={v.id} value={v.id}>V{v.version_number} ({v.status})</option>
                                ))}
                              </select>
                            </div>
                          </div>

                          <button
                            disabled={!versionAId || !versionBId}
                            onClick={async () => {
                              const res = await api.get<any>(`/configuration/versions/${versionAId}/compare/${versionBId}`);
                              setCompareResult(res);
                              setShowCompareModal(true);
                            }}
                            className="w-full bg-zinc-850 hover:bg-zinc-800 border border-zinc-800 text-zinc-200 py-2 rounded-xl text-xs font-bold transition flex items-center justify-center gap-1"
                          >
                            Compare Configurations
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {/* Compare Structural Differences Modal */}
              {showCompareModal && compareResult && (
                <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[60] flex items-center justify-center p-4">
                  <div className="bg-zinc-950 border border-zinc-800 rounded-3xl w-full max-w-md overflow-hidden shadow-2xl flex flex-col max-h-[75vh]">
                    <div className="p-6 border-b border-zinc-900 flex justify-between items-center bg-zinc-950">
                      <div>
                        <h3 className="text-lg font-bold text-zinc-100">
                          Comparison: V{compareResult.version_a} → V{compareResult.version_b}
                        </h3>
                        <p className="text-[11px] text-zinc-500 mt-0.5">Blueprints structure diff audit.</p>
                      </div>
                      <button
                        onClick={() => {
                          setShowCompareModal(false);
                          setCompareResult(null);
                        }}
                        className="text-zinc-500 hover:text-zinc-300 text-sm font-semibold"
                      >
                        Close
                      </button>
                    </div>

                    <div className="p-6 overflow-y-auto space-y-4 flex-1 text-xs">
                      {/* Added elements */}
                      {(compareResult.added_groups?.length > 0 ||
                        compareResult.added_options?.length > 0 ||
                        compareResult.added_rules?.length > 0 ||
                        compareResult.added_components?.length > 0) ? (
                          <div className="space-y-3">
                            <h4 className="text-[10px] font-bold text-teal-400 uppercase tracking-wider">Added elements</h4>
                            <div className="bg-teal-950/10 border border-teal-900/20 rounded-2xl p-4 space-y-2">
                              {compareResult.added_groups?.map((g: string, i: number) => (
                                <div key={i} className="text-teal-400 font-semibold">+ Group: {g}</div>
                              ))}
                              {compareResult.added_options?.map((o: string, i: number) => (
                                <div key={i} className="text-teal-400/90">+ Option: {o}</div>
                              ))}
                              {compareResult.added_rules?.map((r: string, i: number) => (
                                <div key={i} className="text-teal-400/80">+ Rule: {r}</div>
                              ))}
                              {compareResult.added_components?.map((c: string, i: number) => (
                                <div key={i} className="text-teal-400">+ Component: {c}</div>
                              ))}
                            </div>
                          </div>
                      ) : null}

                      {/* Removed elements */}
                      {(compareResult.removed_groups?.length > 0 ||
                        compareResult.removed_options?.length > 0 ||
                        compareResult.removed_rules?.length > 0 ||
                        compareResult.removed_components?.length > 0) ? (
                          <div className="space-y-3">
                            <h4 className="text-[10px] font-bold text-red-400 uppercase tracking-wider">Removed elements</h4>
                            <div className="bg-red-950/10 border border-red-900/20 rounded-2xl p-4 space-y-2">
                              {compareResult.removed_groups?.map((g: string, i: number) => (
                                <div key={i} className="text-red-400 font-semibold">- Group: {g}</div>
                              ))}
                              {compareResult.removed_options?.map((o: string, i: number) => (
                                <div key={i} className="text-red-400/90">- Option: {o}</div>
                              ))}
                              {compareResult.removed_rules?.map((r: string, i: number) => (
                                <div key={i} className="text-red-400/80">- Rule: {r}</div>
                              ))}
                              {compareResult.removed_components?.map((c: string, i: number) => (
                                <div key={i} className="text-red-400">- Component: {c}</div>
                              ))}
                            </div>
                          </div>
                      ) : null}

                      {/* No diffs */}
                      {!(compareResult.added_groups?.length > 0 ||
                        compareResult.added_options?.length > 0 ||
                        compareResult.added_rules?.length > 0 ||
                        compareResult.added_components?.length > 0 ||
                        compareResult.removed_groups?.length > 0 ||
                        compareResult.removed_options?.length > 0 ||
                        compareResult.removed_rules?.length > 0 ||
                        compareResult.removed_components?.length > 0) && (
                          <div className="text-zinc-500 text-center italic py-4">No structure differences detected.</div>
                      )}
                    </div>
                  </div>
                </div>
              )}

            </div>
          )
        )
      )}

    </div>
  );
}
