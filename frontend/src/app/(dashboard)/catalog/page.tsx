"use client";

import React, { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient, keepPreviousData } from "@tanstack/react-query";
import {
  BookOpen,
  Search,
  Plus,
  Download,
  Upload,
  RefreshCw,
  X,
  Edit2,
  Trash2,
  ChevronLeft,
  ChevronRight,
  Archive,
  RotateCcw,
  MoreHorizontal,
  Eye,
  Laptop,
  Coins,
  Sliders,
  DollarSign,
  Package,
  Layers,
  Settings,
  HelpCircle,
  Activity,
  Calendar,
  Grid,
  List as ListIcon,
  Filter,
  Check,
  AlertCircle
} from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import { useDemoTour } from "@/components/demo/DemoTourProvider";
import { DEMO_LATITUDE_ID } from "@/lib/demoMockData";
import type {
  ProductRead,
  ProductCreate,
  ProductUpdate,
  CategoryRead,
  PriceBookRead
} from "@/types/catalog";
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

export default function ProductCatalogPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const { isActive: isDemoActive, flags: demoFlags, mockProducts, mockCategories } = useDemoTour();

  // Role permissions
  const isManager = user?.role === "manager" || user?.role === "admin";
  const isExecutive = user?.role === "executive";
  const isSalesRep = user?.role === "sales_rep";
  const isAdmin = user?.role === "admin";

  const canCreate = isManager || isSalesRep;
  const canUpdate = isManager || isSalesRep;
  const canArchive = isManager;
  const canRestore = isManager;
  const canDelete = isAdmin;
  const canImport = isManager;
  const canViewCost = isManager || isExecutive;
  const canManageCost = isManager;
  const canViewMargin = isManager || isExecutive;

  // Pagination, search, and filter states
  const [page, setPage] = useState(1);
  const [pageSize] = useState(10);
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");

  const [selectedCategories, setSelectedCategories] = useState<number[]>([]);
  const [statusFilter, setStatusFilter] = useState<string>("ACTIVE");
  const [productTypeFilter, setProductTypeFilter] = useState<string>("ALL");
  const [sortBy, setSortBy] = useState<string>("created_newest");

  // Selection & Details panel
  const [selectedProductId, setSelectedProductId] = useState<number | null>(null);
  const [activeTab, setActiveTab] = useState<string>("overview");

  // View Mode: Table vs Grid
  const [viewMode, setViewMode] = useState<"list" | "grid">("list");

  // Modals state
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [archiveConfirmId, setArchiveConfirmId] = useState<number | null>(null);
  const [restoreConfirmId, setRestoreConfirmId] = useState<number | null>(null);

  // Excel Import states
  const [isImportModalOpen, setIsImportModalOpen] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [importResult, setImportResult] = useState<{
    total_rows: number;
    imported_count: number;
    failed_count: number;
    errors: { row: number; sku?: string; error: string }[];
  } | null>(null);

  // Row context menu state
  const [activeMenuId, setActiveMenuId] = useState<number | null>(null);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchQuery);
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  // Fetch Categories
  const { data: liveCategories = [] } = useQuery<CategoryRead[]>({
    queryKey: ["categories"],
    queryFn: () => api.get<CategoryRead[]>("/categories"),
    enabled: !isDemoActive,
  });
  const categories = isDemoActive ? mockCategories : liveCategories;

  // Fetch Products
  const { data: liveProducts = [], isLoading: isLiveLoading, isError, error } = useQuery<ProductRead[]>({
    queryKey: ["products", page, statusFilter, selectedCategories, debouncedSearch],
    queryFn: async () => {
      const offset = (page - 1) * pageSize;
      const params = new URLSearchParams({
        offset: offset.toString(),
        limit: pageSize.toString(),
      });
      if (selectedCategories.length > 0) {
        params.append("category_id", selectedCategories[0].toString());
      }
      return api.get<ProductRead[]>(`/products?${params.toString()}`);
    },
    placeholderData: keepPreviousData,
    enabled: !isDemoActive,
  });
  const products = isDemoActive ? mockProducts : liveProducts;
  const isLoading = isDemoActive ? false : isLiveLoading;

  useEffect(() => {
    if (!isDemoActive) return;
    if (demoFlags.openProductRecord) {
      setSelectedProductId(DEMO_LATITUDE_ID);
      setActiveTab("overview");
    } else {
      setSelectedProductId(null);
    }
  }, [isDemoActive, demoFlags.openProductRecord]);

  // Fetch Single Product Details
  const { data: liveSelectedProduct } = useQuery<ProductRead>({
    queryKey: ["product", selectedProductId],
    queryFn: () => api.get<ProductRead>(`/products/${selectedProductId}`),
    enabled: selectedProductId !== null && !isDemoActive,
  });
  const selectedProduct = isDemoActive
    ? mockProducts.find((p) => p.id === selectedProductId)
    : liveSelectedProduct;

  // Mutations
  const createProductMutation = useMutation({
    mutationFn: (newProd: ProductCreate) => api.post<ProductRead>("/products", newProd),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["products"] });
      setIsCreateModalOpen(false);
    }
  });

  const editProductMutation = useMutation({
    mutationFn: (payload: { id: number; data: ProductUpdate }) =>
      api.put<ProductRead>(`/products/${payload.id}`, payload.data),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["products"] });
      queryClient.invalidateQueries({ queryKey: ["product", data.id] });
      setIsEditModalOpen(false);
    }
  });

  const archiveProductMutation = useMutation({
    mutationFn: (id: number) => api.patch<ProductRead>(`/products/${id}/archive`),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["products"] });
      queryClient.invalidateQueries({ queryKey: ["product", data.id] });
      setArchiveConfirmId(null);
    }
  });

  const restoreProductMutation = useMutation({
    mutationFn: (id: number) => api.patch<ProductRead>(`/products/${id}/restore`),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["products"] });
      queryClient.invalidateQueries({ queryKey: ["product", data.id] });
      setRestoreConfirmId(null);
    }
  });

  const importProductsMutation = useMutation({
    mutationFn: async (file: File) => {
      const formData = new FormData();
      formData.append("file", file);
      return api.upload<{
        total_rows: number;
        imported_count: number;
        failed_count: number;
        errors: { row: number; sku?: string; error: string }[];
      }>("/products/import", formData);
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["products"] });
      setImportResult(data);
    }
  });

  // Filter & Sort
  const processedProducts = React.useMemo(() => {
    let list = [...products];

    if (debouncedSearch.trim() !== "") {
      const q = debouncedSearch.toLowerCase();
      list = list.filter(
        (p) =>
          p.name.toLowerCase().includes(q) ||
          p.sku.toLowerCase().includes(q) ||
          (p.description && p.description.toLowerCase().includes(q))
      );
    }

    if (selectedCategories.length > 0) {
      list = list.filter((p) => p.category_id && selectedCategories.includes(p.category_id));
    }

    if (statusFilter === "ACTIVE") {
      list = list.filter((p) => p.is_active);
    } else if (statusFilter === "INACTIVE") {
      list = list.filter((p) => !p.is_active);
    }

    if (productTypeFilter !== "ALL") {
      list = list.filter((p) => p.billing_type === productTypeFilter);
    }

    if (sortBy === "name_asc") {
      list.sort((a, b) => a.name.localeCompare(b.name));
    } else if (sortBy === "price_asc") {
      list.sort((a, b) => Number(a.base_price) - Number(b.base_price));
    } else if (sortBy === "price_desc") {
      list.sort((a, b) => Number(b.base_price) - Number(a.base_price));
    }

    return list;
  }, [products, debouncedSearch, selectedCategories, statusFilter, productTypeFilter, sortBy]);

  const handleCreateProduct = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (isDemoActive) return;
    const formData = new FormData(e.currentTarget);
    const data: ProductCreate = {
      sku: formData.get("sku") as string,
      name: formData.get("name") as string,
      description: (formData.get("description") as string) || null,
      base_price: parseFloat(formData.get("base_price") as string) || 0,
      currency: (formData.get("currency") as string) || "USD",
      billing_type: (formData.get("billing_type") as any) || "NRC",
      category_id: formData.get("category_id") ? parseInt(formData.get("category_id") as string) : null,
      cost_price: formData.get("cost_price") ? parseFloat(formData.get("cost_price") as string) : null,
    };
    createProductMutation.mutate(data);
  };

  const handleEditProduct = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!selectedProductId || isDemoActive) return;
    const formData = new FormData(e.currentTarget);
    const data: ProductUpdate = {
      name: formData.get("name") as string,
      description: (formData.get("description") as string) || null,
      base_price: parseFloat(formData.get("base_price") as string) || 0,
      currency: (formData.get("currency") as string) || "USD",
      billing_type: (formData.get("billing_type") as any) || "NRC",
      category_id: formData.get("category_id") ? parseInt(formData.get("category_id") as string) : null,
      cost_price: formData.get("cost_price") ? parseFloat(formData.get("cost_price") as string) : null,
    };
    editProductMutation.mutate({ id: selectedProductId, data });
  };

  const detailTabs = [
    { id: "overview", label: "Overview" },
    { id: "pricing", label: "Pricing & Margins" },
    { id: "specs", label: "Specifications" },
  ];

  return (
    <div className="space-y-6">
      {/* ─── Page Header ────────────────────────────────────────── */}
      <div data-demo="catalog-header">
      <PageHeader
        title="Product Catalog"
        description="Browse and manage your products, pricing models, and price books"
        actions={
          <>
            {canImport && (
              <Button
                variant="secondary"
                size="sm"
                icon={<Upload size={14} />}
                onClick={() => setIsImportModalOpen(true)}
              >
                Import Excel
              </Button>
            )}
            {canCreate && (
              <Button
                variant="primary"
                size="sm"
                icon={<Plus size={14} />}
                onClick={() => setIsCreateModalOpen(true)}
              >
                Add Product
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
          placeholder="Search products by SKU, name, or description..."
          className="w-full sm:w-80"
        />

        <div className="flex items-center gap-2.5 w-full sm:w-auto flex-wrap">
          <FilterSelect
            value={selectedCategories[0]?.toString() || "ALL"}
            onChange={(e) => {
              const val = e.target.value;
              setSelectedCategories(val === "ALL" ? [] : [parseInt(val)]);
            }}
            label="Category"
          >
            <option value="ALL">All Categories</option>
            {categories.map((c) => (
              <option key={c.id} value={c.id.toString()}>
                {c.name}
              </option>
            ))}
          </FilterSelect>

          <FilterSelect
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            label="Status"
          >
            <option value="ALL">All Statuses</option>
            <option value="ACTIVE">Active</option>
            <option value="INACTIVE">Archived</option>
          </FilterSelect>

          <FilterSelect
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            label="Sort"
          >
            <option value="created_newest">Newest First</option>
            <option value="name_asc">Name A-Z</option>
            <option value="price_asc">Price Low to High</option>
            <option value="price_desc">Price High to Low</option>
          </FilterSelect>

          {/* Table / Grid view switcher */}
          <div className="flex items-center border border-slate-200 rounded-lg p-0.5 bg-slate-50">
            <button
              onClick={() => setViewMode("list")}
              className={`p-1.5 rounded ${viewMode === "list" ? "bg-white text-blue-600 shadow-2xs font-semibold" : "text-slate-400 hover:text-slate-700"}`}
              title="Table View"
            >
              <ListIcon size={14} />
            </button>
            <button
              onClick={() => setViewMode("grid")}
              className={`p-1.5 rounded ${viewMode === "grid" ? "bg-white text-blue-600 shadow-2xs font-semibold" : "text-slate-400 hover:text-slate-700"}`}
              title="Grid View"
            >
              <Grid size={14} />
            </button>
          </div>
        </div>
      </div>

      {/* ─── Main Content Split ──────────────────────────────────── */}
      <div className="flex gap-6 items-start">
        {/* Left: Products List or Grid */}
        <div className={`transition-all duration-200 ${selectedProductId ? "w-full lg:w-7/12" : "w-full"}`}>
          {viewMode === "list" ? (
            <Card data-demo="catalog-table">
              <DataTable className="border-0 rounded-none">
                <TableHead>
                  <TableRow>
                    <TableHeader>Product</TableHeader>
                    <TableHeader>SKU</TableHeader>
                    <TableHeader>Category</TableHeader>
                    <TableHeader>Type</TableHeader>
                    <TableHeader>Status</TableHeader>
                    {canViewCost && <TableHeader>Cost</TableHeader>}
                    <TableHeader>Base Price</TableHeader>
                    {canViewMargin && <TableHeader>Margin</TableHeader>}
                    <TableHeader className="w-16 text-right">Actions</TableHeader>
                  </TableRow>
                </TableHead>
                <tbody>
                  {isLoading ? (
                    <TableRow>
                      <TableCell colSpan={9} className="text-center py-12 text-slate-500">
                        <RefreshCw size={18} className="animate-spin inline-block mr-2 text-blue-600" />
                        Loading product catalog...
                      </TableCell>
                    </TableRow>
                  ) : processedProducts.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={9} className="text-center py-12 text-slate-500">
                        No products match your filters.
                      </TableCell>
                    </TableRow>
                  ) : (
                    processedProducts.map((p) => {
                      const costNum = p.cost_price ? Number(p.cost_price) : null;
                      const marginPct = p.margin_percentage ? Number(p.margin_percentage) : null;

                      return (
                        <TableRow
                          key={p.id}
                          data-demo={
                            /latitude 7440/i.test(p.name) || p.sku === "DEV-LAP-001"
                              ? "catalog-latitude"
                              : undefined
                          }
                          onClick={() => setSelectedProductId(p.id)}
                          className={`cursor-pointer ${selectedProductId === p.id ? "bg-blue-50/60" : ""}`}
                        >
                          <TableCell>
                            <div className="flex items-center gap-2.5">
                              <div className="w-7 h-7 rounded-lg bg-slate-100 flex items-center justify-center text-slate-600 shrink-0">
                                <Package size={14} />
                              </div>
                              <span className="font-semibold text-slate-900 text-xs">{p.name}</span>
                            </div>
                          </TableCell>
                          <TableCell className="font-mono text-slate-500 text-[11px]">{p.sku}</TableCell>
                          <TableCell className="text-slate-600">{p.category?.name || "General"}</TableCell>
                          <TableCell>
                            <span className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-700 text-[10px] font-semibold">
                              {p.billing_type}
                            </span>
                          </TableCell>
                          <TableCell>
                            <StatusBadge status={p.is_active ? "ACTIVE" : "INACTIVE"} />
                          </TableCell>
                          {canViewCost && (
                            <TableCell className="text-slate-500">
                              {costNum !== null ? `$${costNum.toFixed(2)}` : "—"}
                            </TableCell>
                          )}
                          <TableCell className="font-bold text-slate-900">
                            ${Number(p.base_price).toLocaleString("en-US", { minimumFractionDigits: 2 })}
                          </TableCell>
                          {canViewMargin && (
                            <TableCell>
                              {marginPct !== null ? (
                                <span className={`font-semibold text-xs ${marginPct >= 30 ? "text-emerald-600" : "text-amber-600"}`}>
                                  {marginPct.toFixed(1)}%
                                </span>
                              ) : (
                                "—"
                              )}
                            </TableCell>
                          )}
                          <TableCell className="text-right" onClick={(e) => e.stopPropagation()}>
                            <button
                              onClick={() => {
                                setSelectedProductId(p.id);
                                setIsEditModalOpen(true);
                              }}
                              className="p-1 rounded text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors cursor-pointer"
                              title="Edit product"
                            >
                              <Edit2 size={13} />
                            </button>
                          </TableCell>
                        </TableRow>
                      );
                    })
                  )}
                </tbody>
              </DataTable>
            </Card>
          ) : (
            /* Grid View */
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
              {processedProducts.map((p) => (
                <Card
                  key={p.id}
                  data-demo={
                    /latitude 7440/i.test(p.name) || p.sku === "DEV-LAP-001"
                      ? "catalog-latitude"
                      : undefined
                  }
                  onClick={() => setSelectedProductId(p.id)}
                  className={`p-4 cursor-pointer hover:border-blue-400 transition-all ${selectedProductId === p.id ? "ring-2 ring-blue-500" : ""}`}
                >
                  <div className="flex justify-between items-start mb-2">
                    <span className="text-[10px] font-mono text-slate-400">{p.sku}</span>
                    <StatusBadge status={p.is_active ? "ACTIVE" : "INACTIVE"} />
                  </div>
                  <h4 className="font-semibold text-slate-900 text-xs mb-1">{p.name}</h4>
                  <p className="text-[11px] text-slate-500 line-clamp-2 mb-3">
                    {p.description || "Enterprise product"}
                  </p>
                  <div className="border-t border-slate-100 pt-2 flex justify-between items-baseline">
                    <span className="text-[10px] text-slate-400">{p.billing_type}</span>
                    <span className="font-bold text-slate-900 text-sm">
                      ${Number(p.base_price).toLocaleString("en-US", { minimumFractionDigits: 2 })}
                    </span>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </div>

        {/* Right: Selected Product Details */}
        {selectedProductId && selectedProduct && (
          <div className="w-full lg:w-5/12 animate-in slide-in-from-right duration-200">
            <Card>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between w-full">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-teal-50 text-teal-700 font-bold flex items-center justify-center text-sm border border-teal-200">
                      <Package size={18} />
                    </div>
                    <div>
                      <CardTitle className="text-sm">{selectedProduct.name}</CardTitle>
                      <CardDescription>{selectedProduct.sku} • {selectedProduct.category?.name || "General"}</CardDescription>
                    </div>
                  </div>
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => setSelectedProductId(null)}
                      className="p-1 text-slate-400 hover:text-slate-700 rounded-lg hover:bg-slate-100 transition-colors cursor-pointer"
                    >
                      <X size={16} />
                    </button>
                  </div>
                </div>
              </CardHeader>

              <div className="px-6 pt-1">
                <Tabs tabs={detailTabs} activeTab={activeTab} onChange={setActiveTab} />
              </div>

              <CardContent className="space-y-4 pt-4 text-xs">
                {activeTab === "overview" && (
                  <div className="space-y-3">
                    <p className="text-slate-600 leading-relaxed">
                      {selectedProduct.description || "No description provided for this product."}
                    </p>
                    <div className="grid grid-cols-2 gap-3 p-3 bg-slate-50 rounded-lg border border-slate-100">
                      <div>
                        <span className="text-[10px] text-slate-400 uppercase font-semibold block">Category</span>
                        <span className="text-slate-800 font-medium">{selectedProduct.category?.name || "General"}</span>
                      </div>
                      <div>
                        <span className="text-[10px] text-slate-400 uppercase font-semibold block">Billing</span>
                        <span className="text-slate-800 font-medium">{selectedProduct.billing_type}</span>
                      </div>
                      <div>
                        <span className="text-[10px] text-slate-400 uppercase font-semibold block">Currency</span>
                        <span className="text-slate-800 font-medium">{selectedProduct.currency}</span>
                      </div>
                      <div>
                        <span className="text-[10px] text-slate-400 uppercase font-semibold block">Base Price</span>
                        <span className="text-slate-900 font-bold">${Number(selectedProduct.base_price).toFixed(2)}</span>
                      </div>
                    </div>
                  </div>
                )}

                {activeTab === "pricing" && (
                  <div className="space-y-3">
                    <div className="p-3 bg-slate-50 rounded-lg border border-slate-100 space-y-2">
                      <div className="flex justify-between">
                        <span className="text-slate-500">Base Price:</span>
                        <span className="font-bold text-slate-900">${Number(selectedProduct.base_price).toFixed(2)}</span>
                      </div>
                      {canViewCost && (
                        <div className="flex justify-between">
                          <span className="text-slate-500">Unit Cost:</span>
                          <span className="font-medium text-slate-700">
                            {selectedProduct.cost_price ? `$${Number(selectedProduct.cost_price).toFixed(2)}` : "—"}
                          </span>
                        </div>
                      )}
                      {canViewMargin && (
                        <div className="flex justify-between border-t border-slate-200 pt-2">
                          <span className="text-slate-500">Calculated Margin:</span>
                          <span className="font-bold text-emerald-600">
                            {selectedProduct.margin_percentage ? `${Number(selectedProduct.margin_percentage).toFixed(1)}%` : "—"}
                          </span>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {activeTab === "specs" && (
                  <div className="text-slate-500 italic py-4 text-center">
                    No custom technical attributes configured.
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        )}
      </div>

      {/* ─── MODAL: CREATE PRODUCT ─── */}
      <Modal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        title="Add Product to Catalog"
        description="Enter product SKU, pricing, and classification."
        maxWidth="lg"
      >
        <form onSubmit={handleCreateProduct} className="space-y-3.5 text-xs">
          <div className="grid grid-cols-2 gap-3.5">
            <div>
              <label className="font-semibold text-slate-700 block mb-1">SKU *</label>
              <input
                type="text"
                name="sku"
                required
                placeholder="DEV-PROD-001"
                className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-slate-800 focus:outline-none focus:border-blue-500 font-mono"
              />
            </div>
            <div>
              <label className="font-semibold text-slate-700 block mb-1">Product Name *</label>
              <input
                type="text"
                name="name"
                required
                placeholder="Enterprise Laptop 15-inch"
                className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-slate-800 focus:outline-none focus:border-blue-500"
              />
            </div>
          </div>

          <div>
            <label className="font-semibold text-slate-700 block mb-1">Description</label>
            <textarea
              name="description"
              rows={2}
              placeholder="High performance developer laptop with 32GB RAM"
              className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-slate-800 focus:outline-none focus:border-blue-500"
            />
          </div>

          <div className="grid grid-cols-3 gap-3.5">
            <div>
              <label className="font-semibold text-slate-700 block mb-1">Base Price *</label>
              <input
                type="number"
                step="0.01"
                name="base_price"
                required
                placeholder="1299.00"
                className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-slate-800 focus:outline-none focus:border-blue-500"
              />
            </div>
            {canManageCost && (
              <div>
                <label className="font-semibold text-slate-700 block mb-1">Unit Cost</label>
                <input
                  type="number"
                  step="0.01"
                  name="cost_price"
                  placeholder="850.00"
                  className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-slate-800 focus:outline-none focus:border-blue-500"
                />
              </div>
            )}
            <div>
              <label className="font-semibold text-slate-700 block mb-1">Billing Type</label>
              <select
                name="billing_type"
                className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-slate-800 focus:outline-none focus:border-blue-500"
              >
                <option value="ONE_TIME">One Time (NRC)</option>
                <option value="RECURRING">Recurring (MRC)</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3.5">
            <div>
              <label className="font-semibold text-slate-700 block mb-1">Category</label>
              <select
                name="category_id"
                className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-slate-800 focus:outline-none focus:border-blue-500"
              >
                <option value="">No Category</option>
                {categories.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="font-semibold text-slate-700 block mb-1">Product Type</label>
              <select
                name="type"
                className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-slate-800 focus:outline-none focus:border-blue-500"
              >
                <option value="STANDALONE">Standalone</option>
                <option value="BUNDLE">Bundle Parent</option>
                <option value="COMPONENT">Component</option>
              </select>
            </div>
          </div>

          <div className="flex justify-end gap-2.5 pt-4 border-t border-slate-100">
            <Button variant="secondary" onClick={() => setIsCreateModalOpen(false)}>
              Cancel
            </Button>
            <Button variant="primary" type="submit" isLoading={createProductMutation.isPending}>
              Create Product
            </Button>
          </div>
        </form>
      </Modal>

      {/* ─── MODAL: EDIT PRODUCT ─── */}
      {isEditModalOpen && selectedProduct && (
        <Modal
          isOpen={isEditModalOpen}
          onClose={() => setIsEditModalOpen(false)}
          title={`Edit Product: ${selectedProduct.sku}`}
          maxWidth="lg"
        >
          <form onSubmit={handleEditProduct} className="space-y-3.5 text-xs">
            <div>
              <label className="font-semibold text-slate-700 block mb-1">Product Name *</label>
              <input
                type="text"
                name="name"
                defaultValue={selectedProduct.name}
                required
                className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-slate-800 focus:outline-none focus:border-blue-500"
              />
            </div>
            <div>
              <label className="font-semibold text-slate-700 block mb-1">Description</label>
              <textarea
                name="description"
                defaultValue={selectedProduct.description || ""}
                rows={2}
                className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-slate-800 focus:outline-none focus:border-blue-500"
              />
            </div>
            <div className="grid grid-cols-2 gap-3.5">
              <div>
                <label className="font-semibold text-slate-700 block mb-1">Base Price *</label>
                <input
                  type="number"
                  step="0.01"
                  name="base_price"
                  defaultValue={selectedProduct.base_price}
                  required
                  className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-slate-800 focus:outline-none focus:border-blue-500"
                />
              </div>
              {canManageCost && (
                <div>
                  <label className="font-semibold text-slate-700 block mb-1">Unit Cost</label>
                  <input
                    type="number"
                    step="0.01"
                    name="cost_price"
                    defaultValue={selectedProduct.cost_price || ""}
                    className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-slate-800 focus:outline-none focus:border-blue-500"
                  />
                </div>
              )}
            </div>
            <div className="flex justify-end gap-2.5 pt-4 border-t border-slate-100">
              <Button variant="secondary" onClick={() => setIsEditModalOpen(false)}>
                Cancel
              </Button>
              <Button variant="primary" type="submit" isLoading={editProductMutation.isPending}>
                Save Changes
              </Button>
            </div>
          </form>
        </Modal>
      )}

      {/* ─── MODAL: EXCEL IMPORT ─── */}
      {isImportModalOpen && (
        <Modal
          isOpen={isImportModalOpen}
          onClose={() => {
            setIsImportModalOpen(false);
            setSelectedFile(null);
            setImportResult(null);
          }}
          title="Import Products from Excel"
          description="Upload an .xlsx or .csv file to batch create products."
          maxWidth="md"
        >
          <div className="space-y-4 text-xs">
            <div className="border-2 border-dashed border-slate-200 rounded-xl p-6 text-center bg-slate-50">
              <Upload size={24} className="mx-auto text-slate-400 mb-2" />
              <input
                type="file"
                accept=".xlsx,.xls,.csv"
                onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                className="text-xs text-slate-500 file:mr-4 file:py-1 file:px-3 file:rounded-md file:border-0 file:text-xs file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100 cursor-pointer"
              />
            </div>
            {importResult && (
              <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-lg text-emerald-800">
                <span className="font-bold">Import Complete:</span> {importResult.imported_count} imported,{" "}
                {importResult.failed_count} errors.
              </div>
            )}
            <div className="flex justify-end gap-2 pt-3 border-t border-slate-100">
              <Button variant="secondary" onClick={() => setIsImportModalOpen(false)}>
                Close
              </Button>
              <Button
                variant="primary"
                disabled={!selectedFile || importProductsMutation.isPending}
                isLoading={importProductsMutation.isPending}
                onClick={() => selectedFile && importProductsMutation.mutate(selectedFile)}
              >
                Upload & Import
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
