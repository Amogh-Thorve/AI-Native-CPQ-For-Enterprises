"use client";

import React, { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, ArrowRight, CheckCircle, Layers, Plus, Scale, Sliders, History } from "lucide-react";
import { api, errorMessage } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import {
  Button,
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
  DataTable,
  PageHeader,
  StatusBadge,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  Tabs,
} from "@/components/ui";

// ─── Types ──────────────────────────────────────────────────────────────────

interface Product { id: number; sku: string; name: string; base_price: string | number; currency: string; is_active: boolean }
interface Option { id: number; group_id: number; name: string; description?: string | null; value: string; is_active: boolean }
interface Group { id: number; name: string; description?: string | null; required: boolean; selection_type: string; options: Option[] }
interface Rule { id: number; rule_type: "REQUIRES" | "EXCLUDES"; source_option_id: number; target_option_id: number; message: string }
interface ValidateResult { valid: boolean; errors: { message: string; rule_type: string }[]; warnings: string[] }
interface Bundle {
  id: number; name: string; sku: string; description?: string | null; is_active: boolean;
  components: { id: number; product_id: number; required: boolean; default_quantity: number; product?: Product }[];
}
interface Version { id: number; version_number: number; status: string; change_summary?: string | null; created_at: string }
interface PriceResult { final_unit_price: string; total_price: string; currency: string; pricing_method: string }

const inputCls = "w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-sm focus:outline-none focus:border-blue-500";

export default function ProductConfigurationPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "executive" || user?.role === "admin";
  const [activeTab, setActiveTab] = useState("configurator");
  const [productId, setProductId] = useState<number | null>(null);

  const { data: products = [] } = useQuery<Product[]>({
    queryKey: ["config-products"],
    queryFn: () => api.get<Product[]>("/products?limit=100&status=active"),
  });

  const tabs = [
    { id: "configurator", label: "Configurator", icon: <Sliders size={14} /> },
    { id: "bundles", label: "Bundles", icon: <Layers size={14} /> },
    ...(isAdmin ? [{ id: "builder", label: "Builder", icon: <Scale size={14} /> }] : []),
    { id: "versions", label: "Versions", icon: <History size={14} /> },
  ];

  return (
    <div className="space-y-6">
      <PageHeader title="Product Configuration" description="Configure products against their option groups and compatibility rules, manage bundles and versions." />

      {activeTab !== "bundles" && (
        <Card>
          <CardContent className="p-4 flex items-center gap-3">
            <span className="text-xs font-semibold text-slate-600 shrink-0">Product</span>
            <select className={inputCls} value={productId ?? ""} onChange={(e) => setProductId(e.target.value ? Number(e.target.value) : null)}>
              <option value="">Select a product…</option>
              {products.map((p) => (
                <option key={p.id} value={p.id}>{p.name} ({p.sku})</option>
              ))}
            </select>
          </CardContent>
        </Card>
      )}

      <div className="bg-white px-4 border border-slate-200/80 rounded-xl shadow-xs">
        <Tabs tabs={tabs} activeTab={activeTab} onChange={setActiveTab} />
      </div>

      {activeTab === "configurator" && <Configurator productId={productId} products={products} />}
      {activeTab === "bundles" && <Bundles isAdmin={isAdmin} />}
      {activeTab === "builder" && isAdmin && <Builder productId={productId} />}
      {activeTab === "versions" && <Versions productId={productId} isAdmin={isAdmin} />}
    </div>
  );
}

function NeedProduct() {
  return <p className="text-sm text-slate-500">Select a product above to continue.</p>;
}

// ─── Configurator ───────────────────────────────────────────────────────────

function Configurator({ productId, products }: { productId: number | null; products: Product[] }) {
  const [selected, setSelected] = useState<Record<number, number[]>>({});
  const [quantity, setQuantity] = useState(1);
  const [result, setResult] = useState<ValidateResult | null>(null);

  const { data: groups = [], isLoading } = useQuery<Group[]>({
    queryKey: ["config-groups", productId],
    queryFn: () => api.get<Group[]>(`/configuration/products/${productId}`),
    enabled: productId != null,
  });

  // reset choices when product changes
  useEffect(() => {
    setSelected({});
    setResult(null);
    setQuantity(1);
  }, [productId]);

  const selections = useMemo(
    () => groups.map((g) => ({ group_id: g.id, option_ids: selected[g.id] ?? [] })),
    [groups, selected]
  );

  // Backend validates on every change (debounced)
  useEffect(() => {
    if (productId == null || groups.length === 0) return;
    const t = setTimeout(() => {
      api
        .post<ValidateResult>("/configuration/validate", { product_id: productId, selections })
        .then(setResult)
        .catch((e) => setResult({ valid: false, errors: [{ message: errorMessage(e), rule_type: "ERROR" }], warnings: [] }));
    }, 250);
    return () => clearTimeout(t);
  }, [productId, groups.length, selections]);

  const { data: price } = useQuery<PriceResult>({
    queryKey: ["config-price", productId, quantity],
    queryFn: () => api.post<PriceResult>("/pricing/calculate", { product_id: productId, quantity }),
    enabled: productId != null,
    retry: false,
  });

  const toggle = (g: Group, optionId: number) =>
    setSelected((cur) => {
      const now = cur[g.id] ?? [];
      if (g.selection_type === "MULTI_SELECT") {
        return { ...cur, [g.id]: now.includes(optionId) ? now.filter((x) => x !== optionId) : [...now, optionId] };
      }
      return { ...cur, [g.id]: [optionId] };
    });

  const addToQuote = useMutation({
    mutationFn: () =>
      api.post<{ id: string }>("/configuration/sessions", { product_id: productId, selections }),
    onSuccess: (session) => {
      const product = products.find((p) => p.id === productId);
      const snapshot = {
        selections: groups.map((g) => ({
          group: g.name,
          options: g.options.filter((o) => (selected[g.id] ?? []).includes(o.id)).map((o) => o.name),
        })),
      };
      sessionStorage.setItem(
        "cpq_pending_line",
        JSON.stringify({
          product_id: productId,
          product_name: product?.name ?? "Configured product",
          quantity,
          configuration_id: session.id,
          configuration_snapshot: snapshot,
        })
      );
      window.location.href = "/quotes";
    },
  });

  if (productId == null) return <NeedProduct />;
  if (isLoading) return <p className="text-sm text-slate-500">Loading configuration…</p>;
  if (groups.length === 0)
    return (
      <p className="text-sm text-slate-500">
        This product has no configurable option groups. It can be added to a quote as-is; an administrator can define options in the Builder tab.
      </p>
    );

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
      <div className="lg:col-span-7 space-y-4">
        {groups.map((g) => (
          <Card key={g.id}>
            <CardHeader className="py-3 px-5 bg-slate-50/50">
              <div className="flex items-center justify-between w-full">
                <span className="font-semibold text-xs text-slate-900">
                  {g.name} {g.required && <span className="text-rose-500">*</span>}
                </span>
                <span className="text-[11px] text-slate-400">{g.selection_type === "MULTI_SELECT" ? "Multiple choice" : "Single choice"}</span>
              </div>
            </CardHeader>
            <CardContent className="p-4 space-y-2">
              {g.options.filter((o) => o.is_active).map((o) => {
                const on = (selected[g.id] ?? []).includes(o.id);
                return (
                  <label
                    key={o.id}
                    className={`flex items-center gap-3 p-3 rounded-lg border text-xs cursor-pointer ${on ? "bg-blue-50/70 border-blue-300" : "bg-white border-slate-200 hover:bg-slate-50"}`}
                  >
                    <input
                      type={g.selection_type === "MULTI_SELECT" ? "checkbox" : "radio"}
                      name={`g-${g.id}`}
                      checked={on}
                      onChange={() => toggle(g, o.id)}
                    />
                    <div>
                      <span className="font-medium text-slate-800">{o.name}</span>
                      {o.description && <span className="block text-slate-500">{o.description}</span>}
                    </div>
                  </label>
                );
              })}
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="lg:col-span-5 space-y-4 sticky top-20">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Configuration summary</CardTitle>
            <CardDescription>Validated by the configuration engine</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4 text-xs">
            {result?.valid ? (
              <div className="p-3 rounded-xl border border-emerald-200 bg-emerald-50 flex gap-2 text-emerald-800">
                <CheckCircle size={16} className="shrink-0" /> Configuration is valid.
              </div>
            ) : result ? (
              <div className="p-3 rounded-xl border border-rose-200 bg-rose-50 text-rose-800 space-y-1">
                <div className="flex items-center gap-2 font-semibold"><AlertTriangle size={16} /> Fix the following:</div>
                <ul className="list-disc pl-5">
                  {result.errors.map((e, i) => <li key={i}>{e.message}</li>)}
                </ul>
              </div>
            ) : null}
            {result?.warnings.map((w, i) => <p key={i} className="text-amber-700">{w}</p>)}
            <div className="flex items-center justify-between">
              <span className="font-medium text-slate-700">Quantity</span>
              <input type="number" min={1} value={quantity} onChange={(e) => setQuantity(Math.max(1, Number(e.target.value) || 1))} className="w-24 px-2 py-1 border border-slate-200 rounded-md text-right" />
            </div>
            <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 space-y-1">
              {price ? (
                <>
                  <div className="flex justify-between"><span className="text-slate-500">Unit price ({price.pricing_method})</span><span className="font-semibold">{price.currency} {price.final_unit_price}</span></div>
                  <div className="flex justify-between"><span className="text-slate-500">Total</span><span className="font-bold text-blue-600 text-sm">{price.currency} {price.total_price}</span></div>
                </>
              ) : (
                <span className="text-slate-500">Price unavailable for this product (no active pricing configuration).</span>
              )}
            </div>
            {addToQuote.isError && <p className="text-rose-600">{errorMessage(addToQuote.error)}</p>}
          </CardContent>
          <CardFooter className="flex justify-end">
            <Button variant="primary" size="sm" icon={<ArrowRight size={14} />} iconPosition="right" disabled={!result?.valid || addToQuote.isPending} onClick={() => addToQuote.mutate()}>
              Add to quote
            </Button>
          </CardFooter>
        </Card>
      </div>
    </div>
  );
}

// ─── Bundles ────────────────────────────────────────────────────────────────

function Bundles({ isAdmin }: { isAdmin: boolean }) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({ name: "", sku: "", description: "" });
  const { data: bundles = [], isLoading } = useQuery<Bundle[]>({
    queryKey: ["bundles"],
    queryFn: () => api.get<Bundle[]>("/configuration/bundles"),
  });
  const create = useMutation({
    mutationFn: () => api.post("/configuration/bundles", { ...form, description: form.description || null, is_active: true }),
    onSuccess: () => {
      setForm({ name: "", sku: "", description: "" });
      queryClient.invalidateQueries({ queryKey: ["bundles"] });
    },
  });

  return (
    <div className="space-y-4">
      {isAdmin && (
        <Card>
          <CardContent className="p-4 grid grid-cols-1 md:grid-cols-4 gap-3 items-end">
            <input className={inputCls} placeholder="Bundle name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            <input className={inputCls} placeholder="SKU" value={form.sku} onChange={(e) => setForm({ ...form, sku: e.target.value })} />
            <input className={inputCls} placeholder="Description" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
            <Button variant="primary" icon={<Plus size={14} />} disabled={!form.name || !form.sku || create.isPending} onClick={() => create.mutate()}>New bundle</Button>
            {create.isError && <p className="md:col-span-4 text-xs text-rose-600">{errorMessage(create.error)}</p>}
          </CardContent>
        </Card>
      )}
      <DataTable>
        <TableHead>
          <TableRow>
            <TableHeader>Bundle</TableHeader>
            <TableHeader>SKU</TableHeader>
            <TableHeader>Components</TableHeader>
            <TableHeader>Status</TableHeader>
          </TableRow>
        </TableHead>
        <tbody>
          {isLoading ? (
            <TableRow><TableCell colSpan={4} className="text-center py-6 text-slate-500">Loading…</TableCell></TableRow>
          ) : bundles.length === 0 ? (
            <TableRow><TableCell colSpan={4} className="text-center py-6 text-slate-500">No bundles defined yet.</TableCell></TableRow>
          ) : (
            bundles.map((b) => (
              <TableRow key={b.id}>
                <TableCell>
                  <div className="font-semibold text-slate-900">{b.name}</div>
                  {b.description && <div className="text-xs text-slate-500">{b.description}</div>}
                </TableCell>
                <TableCell className="font-mono text-slate-500">{b.sku}</TableCell>
                <TableCell className="text-xs text-slate-600">
                  {b.components.length === 0 ? "No components" : b.components.map((c) => `${c.product?.name ?? `#${c.product_id}`} ×${c.default_quantity}${c.required ? "" : " (optional)"}`).join(", ")}
                </TableCell>
                <TableCell><StatusBadge status={b.is_active ? "ACTIVE" : "INACTIVE"} /></TableCell>
              </TableRow>
            ))
          )}
        </tbody>
      </DataTable>
    </div>
  );
}

// ─── Builder (admin) ────────────────────────────────────────────────────────

function Builder({ productId }: { productId: number | null }) {
  const queryClient = useQueryClient();
  const [group, setGroup] = useState({ name: "", selection_type: "SINGLE_SELECT", required: true });
  const [option, setOption] = useState({ group_id: "", name: "", value: "" });
  const [rule, setRule] = useState({ rule_type: "REQUIRES", source: "", target: "", message: "" });

  const { data: groups = [] } = useQuery<Group[]>({
    queryKey: ["config-groups", productId],
    queryFn: () => api.get<Group[]>(`/configuration/products/${productId}`),
    enabled: productId != null,
  });
  const { data: rules = [] } = useQuery<Rule[]>({
    queryKey: ["config-rules", productId],
    queryFn: () => api.get<Rule[]>(`/configuration/rules?product_id=${productId}`),
    enabled: productId != null,
  });
  const allOptions = groups.flatMap((g) => g.options.map((o) => ({ ...o, groupName: g.name })));
  const optName = (id: number) => allOptions.find((o) => o.id === id)?.name ?? `#${id}`;
  const done = () => {
    queryClient.invalidateQueries({ queryKey: ["config-groups", productId] });
    queryClient.invalidateQueries({ queryKey: ["config-rules", productId] });
  };

  const addGroup = useMutation({
    mutationFn: () => api.post("/configuration/groups", { product_id: productId, ...group, display_order: groups.length + 1 }),
    onSuccess: () => { setGroup({ name: "", selection_type: "SINGLE_SELECT", required: true }); done(); },
  });
  const addOption = useMutation({
    mutationFn: () => api.post("/configuration/options", { group_id: Number(option.group_id), name: option.name, value: option.value || option.name }),
    onSuccess: () => { setOption({ ...option, name: "", value: "" }); done(); },
  });
  const addRule = useMutation({
    mutationFn: () => api.post("/configuration/rules", { product_id: productId, rule_type: rule.rule_type, source_option_id: Number(rule.source), target_option_id: Number(rule.target), message: rule.message }),
    onSuccess: () => { setRule({ rule_type: "REQUIRES", source: "", target: "", message: "" }); done(); },
  });

  if (productId == null) return <NeedProduct />;
  const err = addGroup.error || addOption.error || addRule.error;

  return (
    <div className="space-y-6">
      {err && <p className="text-sm text-rose-600">{errorMessage(err)}</p>}
      <Card>
        <CardHeader><CardTitle className="text-sm">Option groups</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          {groups.map((g) => (
            <div key={g.id} className="text-sm">
              <div className="font-semibold text-slate-900">{g.name} <span className="text-xs font-normal text-slate-400">{g.selection_type}{g.required ? " · required" : ""}</span></div>
              <div className="text-xs text-slate-600">{g.options.length ? g.options.map((o) => o.name).join(" · ") : "No options yet"}</div>
            </div>
          ))}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-2 border-t border-slate-100 pt-3">
            <input className={inputCls} placeholder="New group name" value={group.name} onChange={(e) => setGroup({ ...group, name: e.target.value })} />
            <select className={inputCls} value={group.selection_type} onChange={(e) => setGroup({ ...group, selection_type: e.target.value })}>
              <option value="SINGLE_SELECT">Single select</option>
              <option value="MULTI_SELECT">Multi select</option>
            </select>
            <label className="flex items-center gap-2 text-xs"><input type="checkbox" checked={group.required} onChange={(e) => setGroup({ ...group, required: e.target.checked })} /> Required</label>
            <Button variant="primary" size="sm" disabled={!group.name} onClick={() => addGroup.mutate()}>Add group</Button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
            <select className={inputCls} value={option.group_id} onChange={(e) => setOption({ ...option, group_id: e.target.value })}>
              <option value="">Group…</option>
              {groups.map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}
            </select>
            <input className={inputCls} placeholder="Option name" value={option.name} onChange={(e) => setOption({ ...option, name: e.target.value })} />
            <input className={inputCls} placeholder="Value (optional)" value={option.value} onChange={(e) => setOption({ ...option, value: e.target.value })} />
            <Button variant="primary" size="sm" disabled={!option.group_id || !option.name} onClick={() => addOption.mutate()}>Add option</Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Compatibility rules</CardTitle>
          <CardDescription>Requires / excludes constraints enforced during validation</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 text-xs">
          {rules.length === 0 && <p className="text-slate-500">No rules defined.</p>}
          {rules.map((r) => (
            <div key={r.id} className="p-3 bg-slate-50 rounded-xl border border-slate-200">
              <span className="font-bold text-slate-900">{optName(r.source_option_id)}</span> {r.rule_type === "REQUIRES" ? "requires" : "excludes"}{" "}
              <span className="font-bold text-slate-900">{optName(r.target_option_id)}</span>
              <span className="block text-slate-500">{r.message}</span>
            </div>
          ))}
          <div className="grid grid-cols-1 md:grid-cols-5 gap-2 border-t border-slate-100 pt-3">
            <select className={inputCls} value={rule.source} onChange={(e) => setRule({ ...rule, source: e.target.value })}>
              <option value="">If option…</option>
              {allOptions.map((o) => <option key={o.id} value={o.id}>{o.groupName}: {o.name}</option>)}
            </select>
            <select className={inputCls} value={rule.rule_type} onChange={(e) => setRule({ ...rule, rule_type: e.target.value })}>
              <option value="REQUIRES">requires</option>
              <option value="EXCLUDES">excludes</option>
            </select>
            <select className={inputCls} value={rule.target} onChange={(e) => setRule({ ...rule, target: e.target.value })}>
              <option value="">option…</option>
              {allOptions.map((o) => <option key={o.id} value={o.id}>{o.groupName}: {o.name}</option>)}
            </select>
            <input className={inputCls} placeholder="Message shown to the user" value={rule.message} onChange={(e) => setRule({ ...rule, message: e.target.value })} />
            <Button variant="primary" size="sm" disabled={!rule.source || !rule.target || !rule.message} onClick={() => addRule.mutate()}>Add rule</Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

// ─── Versions ───────────────────────────────────────────────────────────────

function Versions({ productId, isAdmin }: { productId: number | null; isAdmin: boolean }) {
  const queryClient = useQueryClient();
  const { data: versions = [], isLoading } = useQuery<Version[]>({
    queryKey: ["config-versions", productId],
    queryFn: () => api.get<Version[]>(`/configuration/products/${productId}/versions`),
    enabled: productId != null,
  });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["config-versions", productId] });
  const draft = useMutation({ mutationFn: () => api.post(`/configuration/products/${productId}/versions/draft`), onSuccess: refresh });
  const activate = useMutation({ mutationFn: (id: number) => api.post(`/configuration/versions/${id}/activate`), onSuccess: refresh });
  const archive = useMutation({ mutationFn: (id: number) => api.post(`/configuration/versions/${id}/archive`), onSuccess: refresh });

  if (productId == null) return <NeedProduct />;
  const err = draft.error || activate.error || archive.error;
  return (
    <div className="space-y-3">
      {err && <p className="text-sm text-rose-600">{errorMessage(err)}</p>}
      {isAdmin && (
        <Button variant="secondary" size="sm" icon={<Plus size={14} />} onClick={() => draft.mutate()} disabled={draft.isPending}>New draft from active</Button>
      )}
      <DataTable>
        <TableHead>
          <TableRow>
            <TableHeader>Version</TableHeader>
            <TableHeader>State</TableHeader>
            <TableHeader>Summary</TableHeader>
            <TableHeader>Created</TableHeader>
            {isAdmin && <TableHeader className="text-right">Actions</TableHeader>}
          </TableRow>
        </TableHead>
        <tbody>
          {isLoading ? (
            <TableRow><TableCell colSpan={5} className="text-center py-6 text-slate-500">Loading…</TableCell></TableRow>
          ) : versions.length === 0 ? (
            <TableRow><TableCell colSpan={5} className="text-center py-6 text-slate-500">No configuration versions for this product.</TableCell></TableRow>
          ) : (
            versions.map((v) => (
              <TableRow key={v.id}>
                <TableCell className="font-semibold">v{v.version_number}</TableCell>
                <TableCell><StatusBadge status={v.status} /></TableCell>
                <TableCell className="text-slate-600">{v.change_summary || "—"}</TableCell>
                <TableCell className="text-slate-500">{new Date(v.created_at).toLocaleDateString()}</TableCell>
                {isAdmin && (
                  <TableCell className="text-right space-x-2">
                    {v.status === "DRAFT" && <Button size="sm" variant="primary" onClick={() => activate.mutate(v.id)}>Activate</Button>}
                    {v.status !== "ARCHIVED" && v.status !== "DRAFT" && <Button size="sm" variant="secondary" onClick={() => archive.mutate(v.id)}>Archive</Button>}
                  </TableCell>
                )}
              </TableRow>
            ))
          )}
        </tbody>
      </DataTable>
    </div>
  );
}
