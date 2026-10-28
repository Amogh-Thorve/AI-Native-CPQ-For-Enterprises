"use client";

import React, { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import { api, errorMessage } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import {
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  DataTable,
  PageHeader,
  StatusBadge,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui";

interface TaxRate { id: number; name: string; country?: string | null; region?: string | null; rate_percent: string; is_default: boolean; is_active: boolean }
interface Policy { id: number; name: string; policy_type: "DISCOUNT" | "MARGIN"; discount_threshold: number; margin_threshold?: number | null; role_required: string; is_active: boolean }

const inputCls = "w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-sm focus:outline-none focus:border-blue-500";

export default function SettingsPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin" || user?.role === "executive";
  return (
    <div className="space-y-6">
      <PageHeader title="Settings" description="System status, tax rates and approval policies." />
      <SystemStatus />
      <TaxRates isAdmin={isAdmin} />
      <Policies isAdmin={isAdmin} />
    </div>
  );
}

function SystemStatus() {
  const { data: ai } = useQuery<{ gemini_configured: boolean; model: string }>({ queryKey: ["ai-status"], queryFn: () => api.get("/ai/status") });
  const { data: mail } = useQuery<{ configured: boolean; host?: string | null; from_address?: string | null }>({ queryKey: ["email-status"], queryFn: () => api.get("/emails/status") });
  const { data: sf } = useQuery<{ connected: boolean }>({ queryKey: ["salesforce-status"], queryFn: () => api.get("/integrations/salesforce/status") });
  const rows = [
    { label: "AI (Gemini)", ok: ai?.gemini_configured, detail: ai?.gemini_configured ? `Model ${ai.model}` : "Not configured: AI features use built-in data-driven logic. Set GEMINI_API_KEY in backend/.env." },
    { label: "Email (SMTP)", ok: mail?.configured, detail: mail?.configured ? `${mail.host} · from ${mail.from_address}` : "Not configured: proposals cannot be emailed. Set SMTP_HOST and SMTP_FROM in backend/.env." },
    { label: "Salesforce", ok: sf?.connected, detail: sf?.connected ? "Connected" : "Not connected: connect it under Integrations." },
  ];
  return (
    <Card>
      <CardHeader><CardTitle className="text-sm">System status</CardTitle></CardHeader>
      <CardContent className="space-y-3 text-sm">
        {rows.map((r) => (
          <div key={r.label} className="flex items-start justify-between gap-4">
            <div>
              <div className="font-semibold text-ink">{r.label}</div>
              <div className="text-xs text-slate-600">{r.detail}</div>
            </div>
            <StatusBadge status={r.ok ? "CONNECTED" : "DISCONNECTED"} />
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function TaxRates({ isAdmin }: { isAdmin: boolean }) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({ name: "", country: "", region: "", rate_percent: "", is_default: false });
  const { data: rates = [] } = useQuery<TaxRate[]>({ queryKey: ["tax-rates"], queryFn: () => api.get("/tax-rates/") });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["tax-rates"] });
  const create = useMutation({
    mutationFn: () => api.post("/tax-rates/", { name: form.name, country: form.country || null, region: form.region || null, rate_percent: form.rate_percent, is_default: form.is_default }),
    onSuccess: () => { setForm({ name: "", country: "", region: "", rate_percent: "", is_default: false }); refresh(); },
  });
  const remove = useMutation({ mutationFn: (id: number) => api.delete(`/tax-rates/${id}`), onSuccess: refresh });

  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle className="text-sm">Tax rates</CardTitle>
          <CardDescription>Applied automatically to quotes by the customer&apos;s address: country + region, then country, then the default rate.</CardDescription>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <DataTable>
          <TableHead>
            <TableRow>
              <TableHeader>Name</TableHeader>
              <TableHeader>Country</TableHeader>
              <TableHeader>Region</TableHeader>
              <TableHeader className="text-right">Rate</TableHeader>
              <TableHeader>Default</TableHeader>
              {isAdmin && <TableHeader />}
            </TableRow>
          </TableHead>
          <tbody>
            {rates.length === 0 ? (
              <TableRow><TableCell colSpan={6} className="text-center py-6 text-slate-500">No tax rates defined: quotes are issued without tax.</TableCell></TableRow>
            ) : (
              rates.map((r) => (
                <TableRow key={r.id}>
                  <TableCell className="font-semibold">{r.name}</TableCell>
                  <TableCell>{r.country || "—"}</TableCell>
                  <TableCell>{r.region || "—"}</TableCell>
                  <TableCell className="text-right">{Number(r.rate_percent)}%</TableCell>
                  <TableCell>{r.is_default ? "Yes" : ""}</TableCell>
                  {isAdmin && (
                    <TableCell className="text-right">
                      <button className="p-1.5 text-slate-400 hover:text-rose-600 cursor-pointer" onClick={() => remove.mutate(r.id)} title="Delete"><Trash2 size={14} /></button>
                    </TableCell>
                  )}
                </TableRow>
              ))
            )}
          </tbody>
        </DataTable>
        {isAdmin && (
          <div className="grid grid-cols-1 md:grid-cols-6 gap-2 items-center">
            <input className={inputCls} placeholder="Name (e.g. US sales tax)" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            <input className={inputCls} placeholder="Country" value={form.country} onChange={(e) => setForm({ ...form, country: e.target.value })} />
            <input className={inputCls} placeholder="Region / state" value={form.region} onChange={(e) => setForm({ ...form, region: e.target.value })} />
            <input className={inputCls} type="number" min={0} max={100} step="0.01" placeholder="Rate %" value={form.rate_percent} onChange={(e) => setForm({ ...form, rate_percent: e.target.value })} />
            <label className="flex items-center gap-2 text-xs"><input type="checkbox" checked={form.is_default} onChange={(e) => setForm({ ...form, is_default: e.target.checked })} /> Default</label>
            <Button variant="primary" icon={<Plus size={14} />} disabled={!form.name || !form.rate_percent || create.isPending} onClick={() => create.mutate()}>Add</Button>
          </div>
        )}
        {(create.isError || remove.isError) && <p className="text-sm text-rose-600">{errorMessage(create.error || remove.error)}</p>}
      </CardContent>
    </Card>
  );
}

function Policies({ isAdmin }: { isAdmin: boolean }) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({ name: "", policy_type: "DISCOUNT", threshold: "", role_required: "Sales Manager" });
  const { data: policies = [] } = useQuery<Policy[]>({ queryKey: ["approval-policies"], queryFn: () => api.get("/approvals/policies") });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["approval-policies"] });
  const create = useMutation({
    mutationFn: () =>
      api.post("/approvals/policies", {
        name: form.name,
        policy_type: form.policy_type,
        role_required: form.role_required,
        ...(form.policy_type === "MARGIN" ? { margin_threshold: Number(form.threshold) } : { discount_threshold: Number(form.threshold) }),
      }),
    onSuccess: () => { setForm({ ...form, name: "", threshold: "" }); refresh(); },
  });
  const remove = useMutation({ mutationFn: (id: number) => api.delete(`/approvals/policies/${id}`), onSuccess: refresh });

  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle className="text-sm">Approval policies</CardTitle>
          <CardDescription>Discount policies trigger at or above a discount; margin policies trigger when blended margin falls below a floor.</CardDescription>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <DataTable>
          <TableHead>
            <TableRow>
              <TableHeader>Policy</TableHeader>
              <TableHeader>Type</TableHeader>
              <TableHeader>Trigger</TableHeader>
              <TableHeader>Approver role</TableHeader>
              {isAdmin && <TableHeader />}
            </TableRow>
          </TableHead>
          <tbody>
            {policies.length === 0 ? (
              <TableRow><TableCell colSpan={5} className="text-center py-6 text-slate-500">No active policies: every submitted quote is auto-approved.</TableCell></TableRow>
            ) : (
              policies.map((p) => (
                <TableRow key={p.id}>
                  <TableCell className="font-semibold">{p.name}</TableCell>
                  <TableCell>{p.policy_type ?? "DISCOUNT"}</TableCell>
                  <TableCell>{p.policy_type === "MARGIN" ? `margin below ${p.margin_threshold}%` : `discount ≥ ${p.discount_threshold}%`}</TableCell>
                  <TableCell>{p.role_required}</TableCell>
                  {isAdmin && (
                    <TableCell className="text-right">
                      <button className="p-1.5 text-slate-400 hover:text-rose-600 cursor-pointer" title="Deactivate" onClick={() => remove.mutate(p.id)}><Trash2 size={14} /></button>
                    </TableCell>
                  )}
                </TableRow>
              ))
            )}
          </tbody>
        </DataTable>
        {isAdmin && (
          <div className="grid grid-cols-1 md:grid-cols-5 gap-2 items-center">
            <input className={inputCls} placeholder="Policy name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            <select className={inputCls} value={form.policy_type} onChange={(e) => setForm({ ...form, policy_type: e.target.value })}>
              <option value="DISCOUNT">Discount at or above</option>
              <option value="MARGIN">Margin below</option>
            </select>
            <input className={inputCls} type="number" min={0} max={100} step="0.5" placeholder="Threshold %" value={form.threshold} onChange={(e) => setForm({ ...form, threshold: e.target.value })} />
            <select className={inputCls} value={form.role_required} onChange={(e) => setForm({ ...form, role_required: e.target.value })}>
              <option>Sales Manager</option>
              <option>Executive</option>
              <option>Administrator</option>
            </select>
            <Button variant="primary" icon={<Plus size={14} />} disabled={!form.name || !form.threshold || create.isPending} onClick={() => create.mutate()}>Add</Button>
          </div>
        )}
        {(create.isError || remove.isError) && <p className="text-sm text-rose-600">{errorMessage(create.error || remove.error)}</p>}
      </CardContent>
    </Card>
  );
}
