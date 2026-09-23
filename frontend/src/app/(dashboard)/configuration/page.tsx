"use client";

import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Sliders,
  Plus,
  HelpCircle,
  AlertCircle,
  CheckCircle,
  Layers,
  ChevronRight,
  Info,
  ShieldAlert,
  Lock,
  PlusCircle,
  Trash2,
  Settings,
  Sparkles,
  ArrowRight,
  Eye,
  Check,
  Edit2,
  Package,
  Wrench,
  History,
  Scale
} from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import { useDemoTour } from "@/components/demo/DemoTourProvider";
import { DEMO_CONFIG_OPTIONS } from "@/lib/demoMockData";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
  Button,
  StatusBadge,
  PageHeader,
  DataTable,
  TableHead,
  TableRow,
  TableHeader,
  TableCell,
  Tabs,
  Modal
} from "@/components/ui";

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

export default function ProductConfigurationPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const isExecutive = user?.role === "executive" || user?.role === "admin";

  // Tabs: Configurator, Solution Builder, Rules, Versions
  const [activeTab, setActiveTab] = useState<string>("configurator");

  // Configurator Workspace State
  const [selectedBundleId, setSelectedBundleId] = useState<string>("1");
  const [selectedOptions, setSelectedOptions] = useState<Record<string, string>>({
    processor: "Intel Core i7-13700H (14-Core, up to 5.0GHz)",
    memory: "32GB DDR5 5200MHz (2x16GB)",
    storage: "1TB M.2 PCIe NVMe SSD Class 40",
    display: "15.6 FHD+ (1920 x 1200) Anti-Glare 500 nits",
    os: "Windows 11 Pro Enterprise License",
    support: "3-Year ProSupport Plus with Next Business Day Onsite",
  });
  const [configQuantity, setConfigQuantity] = useState<number>(1);
  const [isConfigValid, setIsConfigValid] = useState<boolean>(true);

  // Queries
  const { data: bundles = [], isLoading: isLoadingBundles } = useQuery<Bundle[]>({
    queryKey: ["bundles"],
    queryFn: () => api.get<Bundle[]>("/catalog/bundles/").catch(() => []),
  });

  const { data: products = [] } = useQuery<Product[]>({
    queryKey: ["products-config"],
    queryFn: () => api.get<Product[]>("/catalog/products/").catch(() => []),
  });

  const pageTabs = [
    { id: "configurator", label: "Configurator", icon: <Sliders size={14} /> },
    { id: "builder", label: "Solution Builder", icon: <Layers size={14} /> },
    { id: "rules", label: "Rules", icon: <Scale size={14} /> },
    { id: "versions", label: "Versions", icon: <History size={14} /> },
  ];

  const optionCategories = [
    {
      id: "processor",
      name: "Processor / CPU",
      options: [
        { id: "i5", label: "Intel Core i5-13500H (12-Core, up to 4.7GHz)", price: "+$0.00" },
        { id: "i7", label: "Intel Core i7-13700H (14-Core, up to 5.0GHz)", price: "+$240.00", recommended: true },
        { id: "i9", label: "Intel Core i9-13900H (14-Core, up to 5.4GHz)", price: "+$480.00" },
      ],
    },
    {
      id: "memory",
      name: "Memory / RAM",
      options: [
        { id: "16gb", label: "16GB DDR5 5200MHz (1x16GB)", price: "+$0.00" },
        { id: "32gb", label: "32GB DDR5 5200MHz (2x16GB)", price: "+$180.00", recommended: true },
        { id: "64gb", label: "64GB DDR5 5200MHz (2x32GB)", price: "+$380.00" },
      ],
    },
    {
      id: "storage",
      name: "Storage / SSD",
      options: [
        { id: "512gb", label: "512GB M.2 PCIe NVMe SSD Class 35", price: "+$0.00" },
        { id: "1tb", label: "1TB M.2 PCIe NVMe SSD Class 40", price: "+$150.00", recommended: true },
        { id: "2tb", label: "2TB M.2 PCIe NVMe SSD Class 40", price: "+$320.00" },
      ],
    },
    {
      id: "os",
      name: "Operating System",
      options: [
        { id: "w11pro", label: "Windows 11 Pro Enterprise License", price: "+$0.00", recommended: true },
        { id: "ubuntu", label: "Ubuntu Linux 24.04 LTS Preloaded", price: "-$50.00" },
      ],
    },
    {
      id: "support",
      name: "Warranty & Support Plan",
      options: [
        { id: "basic", label: "1-Year Basic Hardware Onsite Service", price: "+$0.00" },
        { id: "pro", label: "3-Year ProSupport Plus with Next Business Day Onsite", price: "+$299.00", recommended: true },
      ],
    },
  ];

  return (
    <div className="space-y-6">
      {/* ─── Page Header ────────────────────────────────────────── */}
      <div data-demo="config-header">
      <PageHeader
        title="Product Configuration"
        description="Configure products, bundles and validation rules"
        actions={
          isExecutive && (
            <Button
              variant="primary"
              size="sm"
              icon={<Plus size={14} />}
              onClick={() => setActiveTab("builder")}
            >
              New Bundle
            </Button>
          )
        }
      />
      </div>

      {/* ─── Navigation Tabs ────────────────────────────────────── */}
      <div className="bg-white px-4 border border-slate-200/80 rounded-xl shadow-xs">
        <Tabs tabs={pageTabs} activeTab={activeTab} onChange={setActiveTab} />
      </div>

      {/* ─── TAB 1: CONFIGURATOR WORKSPACE ──────────────────────── */}
      {activeTab === "configurator" && (
        <div data-demo="config-workspace" className="space-y-6">
          {/* Top Bundle / Product Selector Header */}
          <Card>
            <CardContent className="p-4 flex flex-col sm:flex-row items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center border border-blue-100 shrink-0">
                  <Package size={20} />
                </div>
                <div>
                  <span className="text-[10px] uppercase font-bold text-slate-400 block tracking-wider">
                    Configuring Target Bundle
                  </span>
                  <h3 className="text-sm font-bold text-slate-900">
                    Enterprise Developer Workstation Bundle (DEV-BUNDLE-01)
                  </h3>
                </div>
              </div>

              <div className="flex items-center gap-3 w-full sm:w-auto">
                <span className="text-xs text-slate-500 font-medium">Switch Bundle:</span>
                <select
                  value={selectedBundleId}
                  onChange={(e) => setSelectedBundleId(e.target.value)}
                  className="px-3 py-1.5 bg-white border border-slate-200 rounded-lg text-xs font-semibold text-slate-800 focus:outline-none focus:border-blue-500 shadow-2xs cursor-pointer"
                >
                  <option value="1">Dell Latitude 7440 Workstation Bundle</option>
                  <option value="2">Cloud Infrastructure Tier 1 Bundle</option>
                  <option value="3">Executive Mobility Package</option>
                </select>
              </div>
            </CardContent>
          </Card>

          {/* 2-Column Configurator Workspace */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
            {/* Left Column (7 cols): Configuration Options */}
            <div className="lg:col-span-7 space-y-4">
              {optionCategories.map((category) => (
                <Card key={category.id}>
                  <CardHeader className="py-3 px-5 bg-slate-50/50">
                    <div className="flex items-center justify-between w-full">
                      <span className="font-semibold text-xs text-slate-900">{category.name}</span>
                      <span className="text-[11px] text-slate-400">Single Choice</span>
                    </div>
                  </CardHeader>
                  <CardContent className="p-4 space-y-2.5">
                    {category.options.map((opt) => {
                      const isSelected = selectedOptions[category.id] === opt.label;
                      return (
                        <label
                          key={opt.id}
                          className={`flex items-center justify-between p-3 rounded-lg border transition-all cursor-pointer text-xs ${
                            isSelected
                              ? "bg-blue-50/70 border-blue-300 shadow-2xs ring-1 ring-blue-400/20"
                              : "bg-white border-slate-200/80 hover:bg-slate-50 hover:border-slate-300"
                          }`}
                        >
                          <div className="flex items-center gap-3">
                            <input
                              type="radio"
                              name={category.id}
                              checked={isSelected}
                              onChange={() =>
                                setSelectedOptions((prev) => ({
                                  ...prev,
                                  [category.id]: opt.label,
                                }))
                              }
                              className="text-blue-600 focus:ring-blue-500 w-4 h-4"
                            />
                            <div>
                              <span className={`font-medium ${isSelected ? "text-blue-900 font-semibold" : "text-slate-700"}`}>
                                {opt.label}
                              </span>
                              {opt.recommended && (
                                <span className="ml-2 px-1.5 py-0.5 rounded text-[10px] font-bold bg-teal-50 text-teal-700 border border-teal-200">
                                  Recommended
                                </span>
                              )}
                            </div>
                          </div>
                          <span className={`font-semibold text-[11px] ${isSelected ? "text-blue-700" : "text-slate-500"}`}>
                            {opt.price}
                          </span>
                        </label>
                      );
                    })}
                  </CardContent>
                </Card>
              ))}

              {/* Quantity Counter Card */}
              <Card>
                <CardContent className="p-4 flex items-center justify-between">
                  <div>
                    <span className="text-xs font-semibold text-slate-800 block">System Units Quantity</span>
                    <span className="text-[11px] text-slate-400">Number of workstations configured with this profile</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setConfigQuantity(Math.max(1, configQuantity - 1))}
                      className="w-8 h-8 rounded-lg border border-slate-200 bg-white text-slate-600 hover:bg-slate-50 flex items-center justify-center font-bold cursor-pointer"
                    >
                      -
                    </button>
                    <span className="w-10 text-center font-bold text-sm text-slate-900">
                      {configQuantity}
                    </span>
                    <button
                      onClick={() => setConfigQuantity(configQuantity + 1)}
                      className="w-8 h-8 rounded-lg border border-slate-200 bg-white text-slate-600 hover:bg-slate-50 flex items-center justify-center font-bold cursor-pointer"
                    >
                      +
                    </button>
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Right Column (5 cols): Configuration Summary & Validation */}
            <div className="lg:col-span-5 space-y-4 sticky top-20">
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">Configuration Summary</CardTitle>
                  <CardDescription>Live breakdown of selected hardware & software options</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3.5 text-xs">
                  <div className="space-y-2 border-b border-slate-100 pb-3">
                    <span className="text-[10px] uppercase font-bold text-slate-400 tracking-wider block">
                      Selected Components ({Object.keys(selectedOptions).length})
                    </span>
                    {Object.entries(selectedOptions).map(([catKey, optVal]) => (
                      <div key={catKey} className="flex items-start justify-between gap-2 text-[11px]">
                        <span className="text-slate-400 capitalize w-20 shrink-0">{catKey}:</span>
                        <span className="font-semibold text-slate-800 text-right">{optVal}</span>
                      </div>
                    ))}
                  </div>

                  {/* Real-time Validation Box */}
                  <div className="p-3.5 rounded-xl border border-emerald-200 bg-emerald-50/80 flex items-start gap-2.5 text-emerald-900">
                    <CheckCircle size={18} className="text-emerald-600 shrink-0 mt-0.5" />
                    <div>
                      <span className="font-bold text-xs block">Configuration Valid</span>
                      <p className="text-[11px] text-emerald-700 mt-0.5 leading-tight">
                        All dependency constraints satisfied. No exclusion rules violated.
                      </p>
                    </div>
                  </div>

                  {/* Pricing preview for configuration */}
                  <div className="p-3 bg-slate-50 rounded-xl border border-slate-200/80 space-y-1.5">
                    <div className="flex justify-between items-baseline">
                      <span className="text-slate-500">Unit Configured Price:</span>
                      <span className="font-bold text-slate-900 text-sm">$1,479.00</span>
                    </div>
                    <div className="flex justify-between items-baseline">
                      <span className="text-slate-500">Total for {configQuantity} unit(s):</span>
                      <span className="font-extrabold text-blue-600 text-base">
                        ${(1479 * configQuantity).toLocaleString("en-US", { minimumFractionDigits: 2 })}
                      </span>
                    </div>
                  </div>
                </CardContent>

                <CardFooter className="flex items-center justify-between">
                  <Button variant="secondary" size="sm" onClick={() => alert("Draft configuration saved!")}>
                    Save Profile
                  </Button>
                  <Button
                    variant="primary"
                    size="sm"
                    icon={<ArrowRight size={14} />}
                    iconPosition="right"
                    onClick={() => {
                      alert("Configuration applied! Redirecting to Quote Builder with preconfigured lines...");
                      window.location.href = "/quotes";
                    }}
                  >
                    Add to Quote
                  </Button>
                </CardFooter>
              </Card>
            </div>
          </div>
        </div>
      )}

      {/* ─── TAB 2: SOLUTION BUILDER ────────────────────────────── */}
      {activeTab === "builder" && (
        <Card>
          <CardHeader>
            <CardTitle>Solution & Bundle Builder</CardTitle>
            <CardDescription>Assemble multi-product bundles and define component requirement policies.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <DataTable>
              <TableHead>
                <TableRow>
                  <TableHeader>Bundle Name</TableHeader>
                  <TableHeader>SKU</TableHeader>
                  <TableHeader>Components</TableHeader>
                  <TableHeader>Status</TableHeader>
                  <TableHeader className="text-right">Actions</TableHeader>
                </TableRow>
              </TableHead>
              <tbody>
                <TableRow>
                  <TableCell className="font-semibold text-slate-900">Developer Workstation Bundle</TableCell>
                  <TableCell className="font-mono text-slate-500">DEV-BUNDLE-01</TableCell>
                  <TableCell>4 Hardware + 2 Software</TableCell>
                  <TableCell>
                    <StatusBadge status="ACTIVE" />
                  </TableCell>
                  <TableCell className="text-right">
                    <Button variant="secondary" size="sm">Edit Bundle</Button>
                  </TableCell>
                </TableRow>
                <TableRow>
                  <TableCell className="font-semibold text-slate-900">Cloud Infrastructure Tier 1</TableCell>
                  <TableCell className="font-mono text-slate-500">CLOUD-BUN-02</TableCell>
                  <TableCell>3 SaaS Modules + 1 Support</TableCell>
                  <TableCell>
                    <StatusBadge status="ACTIVE" />
                  </TableCell>
                  <TableCell className="text-right">
                    <Button variant="secondary" size="sm">Edit Bundle</Button>
                  </TableCell>
                </TableRow>
              </tbody>
            </DataTable>
          </CardContent>
        </Card>
      )}

      {/* ─── TAB 3: RULES ───────────────────────────────────────── */}
      {activeTab === "rules" && (
        <Card>
          <CardHeader>
            <CardTitle>Compatibility & Validation Rules</CardTitle>
            <CardDescription>Requires / Excludes constraints evaluated during real-time configuration.</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3 text-xs">
              <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 flex items-center justify-between">
                <div>
                  <span className="font-bold text-slate-900 block">Intel i9 CPU Requires 64GB RAM</span>
                  <span className="text-slate-500">Rule Type: MANDATORY_REQUIRES • Target: Dell Latitude 7440</span>
                </div>
                <StatusBadge status="ACTIVE" />
              </div>
              <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 flex items-center justify-between">
                <div>
                  <span className="font-bold text-slate-900 block">Ubuntu Linux Excludes Windows Enterprise Support</span>
                  <span className="text-slate-500">Rule Type: MUTUALLY_EXCLUSIVE • Target: OS Options</span>
                </div>
                <StatusBadge status="ACTIVE" />
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* ─── TAB 4: VERSIONS ────────────────────────────────────── */}
      {activeTab === "versions" && (
        <Card>
          <CardHeader>
            <CardTitle>Configuration Lifecycle & Versions</CardTitle>
            <CardDescription>Track revisions, structural diffs, and published release versions.</CardDescription>
          </CardHeader>
          <CardContent>
            <DataTable>
              <TableHead>
                <TableRow>
                  <TableHeader>Version</TableHeader>
                  <TableHeader>Bundle</TableHeader>
                  <TableHeader>State</TableHeader>
                  <TableHeader>Published Date</TableHeader>
                  <TableHeader className="text-right">Actions</TableHeader>
                </TableRow>
              </TableHead>
              <tbody>
                <TableRow>
                  <TableCell className="font-bold text-slate-900">v1.2 (Current)</TableCell>
                  <TableCell>Developer Workstation Bundle</TableCell>
                  <TableCell>
                    <StatusBadge status="ACTIVE" />
                  </TableCell>
                  <TableCell className="text-slate-500">2026-09-15</TableCell>
                  <TableCell className="text-right">
                    <Button variant="secondary" size="sm">Compare</Button>
                  </TableCell>
                </TableRow>
                <TableRow>
                  <TableCell className="font-medium text-slate-700">v1.1</TableCell>
                  <TableCell>Developer Workstation Bundle</TableCell>
                  <TableCell>
                    <StatusBadge status="ARCHIVED" />
                  </TableCell>
                  <TableCell className="text-slate-500">2026-08-01</TableCell>
                  <TableCell className="text-right">
                    <Button variant="secondary" size="sm">View</Button>
                  </TableCell>
                </TableRow>
              </tbody>
            </DataTable>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
