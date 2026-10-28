"use client";

import React, { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Cloud, FileUp, Link2, RefreshCw, Webhook } from "lucide-react";
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

interface SalesforceStatus {
  oauth_configured: boolean;
  connected: boolean;
  instance_url?: string | null;
  user_email?: string | null;
  last_sync?: string | null;
  mapped_opportunities_count: number;
}
interface SyncLog {
  id: number;
  integration_type: string;
  started_at: string;
  completed_at?: string | null;
  status: string;
  records_processed: number;
  error_summary?: string | null;
}
interface Mapping { file_column: string; db_field: string }
interface ImportPreview {
  import_type: string;
  headers: string[];
  sample_rows: string[][];
  suggested_mappings: Mapping[];
  target_fields: { field: string; label: string; required: boolean }[];
  total_rows: number;
}
interface ImportResult {
  success: boolean;
  message: string;
  records_imported: number;
  records_failed: number;
  errors: { row: number; key?: string | null; error: string }[];
}
interface WebhookConfig {
  configured: boolean;
  enabled: boolean;
  endpoint_url?: string | null;
  secret_key?: string | null;
  events: string[];
  available_events: string[];
  last_delivery_status?: string | null;
  last_delivery_at?: string | null;
}

const inputCls = "w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-sm focus:outline-none focus:border-blue-500";

export default function IntegrationsPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin" || user?.role === "executive";
  const queryClient = useQueryClient();
  const [notice, setNotice] = useState<{ text: string; type: "success" | "error" } | null>(null);
  const notify = (text: string, type: "success" | "error" = "success") => {
    setNotice({ text, type });
    setTimeout(() => setNotice(null), 6000);
  };
  const refreshLogs = () => queryClient.invalidateQueries({ queryKey: ["integration-logs"] });

  // OAuth redirect result (?sf=connected|error)
  useEffect(() => {
    const p = new URLSearchParams(window.location.search);
    const sfResult = p.get("sf");
    if (sfResult === "connected") notify("Salesforce connected.");
    if (sfResult === "error") notify(p.get("message") || "Salesforce connection failed.", "error");
    if (sfResult) window.history.replaceState({}, "", "/integrations");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const { data: logs = [] } = useQuery<SyncLog[]>({
    queryKey: ["integration-logs"],
    queryFn: () => api.get<SyncLog[]>("/integrations/logs"),
  });

  return (
    <div className="space-y-6">
      {notice && (
        <div
          className={`fixed top-5 right-5 z-50 max-w-md px-4 py-3 rounded-xl shadow-lg border text-sm font-medium ${
            notice.type === "success" ? "bg-emerald-50 text-emerald-800 border-emerald-200" : "bg-rose-50 text-rose-800 border-rose-200"
          }`}
        >
          {notice.text}
        </div>
      )}
      <PageHeader title="Integrations" description="Connect Salesforce, import catalog and customer data, and push quote events to your systems." />

      <SalesforceCard isAdmin={isAdmin} notify={notify} refreshLogs={refreshLogs} />
      <ImportCard notify={notify} refreshLogs={refreshLogs} />
      {isAdmin && <WebhookCard notify={notify} refreshLogs={refreshLogs} />}

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Activity log</CardTitle>
          <CardDescription>Syncs, imports and webhook deliveries</CardDescription>
        </CardHeader>
        <CardContent>
          <DataTable>
            <TableHead>
              <TableRow>
                <TableHeader>Type</TableHeader>
                <TableHeader>Started</TableHeader>
                <TableHeader>Status</TableHeader>
                <TableHeader className="text-right">Records</TableHeader>
                <TableHeader>Detail</TableHeader>
              </TableRow>
            </TableHead>
            <tbody>
              {logs.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={5} className="text-center py-6 text-slate-500">No integration activity yet.</TableCell>
                </TableRow>
              ) : (
                logs.map((l) => (
                  <TableRow key={l.id}>
                    <TableCell className="font-medium">{l.integration_type}</TableCell>
                    <TableCell className="text-slate-500">{new Date(l.started_at + "Z").toLocaleString()}</TableCell>
                    <TableCell>
                      <StatusBadge status={l.status === "success" ? "ACTIVE" : l.status === "failed" ? "REJECTED" : "PENDING"} showDot={false} />
                    </TableCell>
                    <TableCell className="text-right">{l.records_processed}</TableCell>
                    <TableCell className="text-xs text-rose-600">{l.error_summary}</TableCell>
                  </TableRow>
                ))
              )}
            </tbody>
          </DataTable>
        </CardContent>
      </Card>
    </div>
  );
}

// ─── Salesforce ─────────────────────────────────────────────────────────────

function SalesforceCard({ isAdmin, notify, refreshLogs }: { isAdmin: boolean; notify: (t: string, k?: "success" | "error") => void; refreshLogs: () => void }) {
  const queryClient = useQueryClient();
  const [instanceUrl, setInstanceUrl] = useState("");
  const [accessToken, setAccessToken] = useState("");

  const { data: status } = useQuery<SalesforceStatus>({
    queryKey: ["salesforce-status"],
    queryFn: () => api.get<SalesforceStatus>("/integrations/salesforce/status"),
  });
  const done = () => {
    queryClient.invalidateQueries({ queryKey: ["salesforce-status"] });
    refreshLogs();
  };
  const oauth = useMutation({
    mutationFn: () => api.get<{ url: string }>("/integrations/salesforce/authorize"),
    onSuccess: (r) => {
      window.location.href = r.url;
    },
    onError: (e) => notify(errorMessage(e), "error"),
  });
  const connect = useMutation({
    mutationFn: () => api.post("/integrations/salesforce/connect", { instance_url: instanceUrl, access_token: accessToken }),
    onSuccess: () => {
      setAccessToken("");
      notify("Salesforce connected.");
      done();
    },
    onError: (e) => notify(errorMessage(e), "error"),
  });
  const disconnect = useMutation({
    mutationFn: () => api.post("/integrations/salesforce/disconnect"),
    onSuccess: () => {
      notify("Salesforce disconnected.");
      done();
    },
    onError: (e) => notify(errorMessage(e), "error"),
  });
  const syncAll = useMutation({
    mutationFn: () => api.post<{ status: string; message: string }>("/integrations/salesforce/sync-all"),
    onSuccess: (r) => {
      notify(r.message, r.status === "FAILED" ? "error" : "success");
      done();
      queryClient.invalidateQueries({ queryKey: ["quotes"] });
    },
    onError: (e) => notify(errorMessage(e), "error"),
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm flex items-center gap-2">
          <Cloud size={15} className="text-sky-600" /> Salesforce CRM
          <StatusBadge status={status?.connected ? "CONNECTED" : "DISCONNECTED"} />
        </CardTitle>
        <CardDescription>
          Approved, sent and accepted quotes are pushed to Salesforce as Opportunities under a matching Account.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        {status?.connected ? (
          <>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <Info label="Instance" value={status.instance_url} />
              <Info label="Connected as" value={status.user_email} />
              <Info label="Quotes linked to opportunities" value={String(status.mapped_opportunities_count)} />
              <Info label="Last successful sync" value={status.last_sync ? new Date(status.last_sync + "Z").toLocaleString() : "Never"} />
            </div>
            {isAdmin && (
              <div className="flex gap-2">
                <Button variant="primary" icon={<RefreshCw size={14} />} onClick={() => syncAll.mutate()} disabled={syncAll.isPending}>
                  {syncAll.isPending ? "Syncing…" : "Sync all eligible quotes"}
                </Button>
                <Button variant="danger" onClick={() => disconnect.mutate()} disabled={disconnect.isPending}>Disconnect</Button>
              </div>
            )}
          </>
        ) : isAdmin ? (
          <div className="space-y-4">
            {status?.oauth_configured ? (
              <Button variant="primary" icon={<Link2 size={14} />} onClick={() => oauth.mutate()} disabled={oauth.isPending}>
                Connect with Salesforce (OAuth)
              </Button>
            ) : (
              <p className="text-xs text-slate-500">
                OAuth is not configured on the server (set SALESFORCE_CLIENT_ID and SALESFORCE_CLIENT_SECRET in backend/.env). You can still connect with an access token.
              </p>
            )}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <input className={inputCls} placeholder="https://your-org.my.salesforce.com" value={instanceUrl} onChange={(e) => setInstanceUrl(e.target.value)} />
              <input className={inputCls} type="password" placeholder="Access token" value={accessToken} onChange={(e) => setAccessToken(e.target.value)} autoComplete="off" />
            </div>
            <Button variant="secondary" onClick={() => connect.mutate()} disabled={!instanceUrl || !accessToken || connect.isPending}>
              {connect.isPending ? "Verifying…" : "Connect with token"}
            </Button>
          </div>
        ) : (
          <p className="text-slate-500">Salesforce is not connected. An administrator can connect it.</p>
        )}
      </CardContent>
    </Card>
  );
}

function Info({ label, value }: { label: string; value?: string | null }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wider font-bold text-slate-400">{label}</div>
      <div className="text-slate-800 font-medium break-all">{value || "—"}</div>
    </div>
  );
}

// ─── Import ─────────────────────────────────────────────────────────────────

function ImportCard({ notify, refreshLogs }: { notify: (t: string, k?: "success" | "error") => void; refreshLogs: () => void }) {
  const queryClient = useQueryClient();
  const [importType, setImportType] = useState<"catalog" | "customers">("catalog");
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [mapping, setMapping] = useState<Record<string, string>>({}); // db_field -> file_column
  const [result, setResult] = useState<ImportResult | null>(null);

  const reset = () => {
    setFile(null);
    setPreview(null);
    setMapping({});
    setResult(null);
  };

  const previewMut = useMutation({
    mutationFn: (f: File) => {
      const fd = new FormData();
      fd.append("file", f);
      fd.append("import_type", importType);
      return api.upload<ImportPreview>("/integrations/import/preview", fd);
    },
    onSuccess: (p) => {
      setPreview(p);
      setMapping(Object.fromEntries(p.suggested_mappings.map((m) => [m.db_field, m.file_column])));
      setResult(null);
    },
    onError: (e) => {
      setPreview(null);
      notify(errorMessage(e), "error");
    },
  });

  const execute = useMutation({
    mutationFn: () => {
      const fd = new FormData();
      fd.append("file", file as File);
      fd.append("import_type", importType);
      fd.append(
        "mappings",
        JSON.stringify(Object.entries(mapping).filter(([, col]) => col).map(([db_field, file_column]) => ({ db_field, file_column })))
      );
      return api.upload<ImportResult>("/integrations/import/execute", fd);
    },
    onSuccess: (r) => {
      setResult(r);
      notify(r.message, r.records_imported > 0 ? "success" : "error");
      refreshLogs();
      queryClient.invalidateQueries({ queryKey: ["products"] });
      queryClient.invalidateQueries({ queryKey: ["customers"] });
    },
    onError: (e) => notify(errorMessage(e), "error"),
  });

  const missingRequired = preview?.target_fields.filter((f) => f.required && !mapping[f.field]) ?? [];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm flex items-center gap-2">
          <FileUp size={15} className="text-violet-600" /> Import from CSV / Excel
        </CardTitle>
        <CardDescription>Upload a file, confirm how its columns map to CPQ fields, then import. Rows that fail are listed and skipped.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <div className="flex flex-wrap items-center gap-3">
          <select className={`${inputCls} w-44`} value={importType} onChange={(e) => { setImportType(e.target.value as "catalog" | "customers"); reset(); }}>
            <option value="catalog">Product catalog</option>
            <option value="customers">Customers</option>
          </select>
          <input
            type="file"
            accept=".csv,.xlsx"
            onChange={(e) => {
              const f = e.target.files?.[0] ?? null;
              setFile(f);
              setPreview(null);
              setResult(null);
              if (f) previewMut.mutate(f);
            }}
            className="text-xs"
          />
          {previewMut.isPending && <span className="text-xs text-slate-500">Reading file…</span>}
        </div>

        {preview && (
          <div className="space-y-4">
            <p className="text-xs text-slate-500">{preview.total_rows} data row(s) found.</p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {preview.target_fields.map((f) => (
                <div key={f.field} className="flex items-center gap-3">
                  <label className="w-48 text-xs font-medium text-slate-700 shrink-0">
                    {f.label} {f.required && <span className="text-rose-500">*</span>}
                  </label>
                  <select className={inputCls} value={mapping[f.field] ?? ""} onChange={(e) => setMapping((m) => ({ ...m, [f.field]: e.target.value }))}>
                    <option value="">— not mapped —</option>
                    {preview.headers.map((h) => (
                      <option key={h} value={h}>{h}</option>
                    ))}
                  </select>
                </div>
              ))}
            </div>
            <div className="overflow-x-auto border border-slate-200 rounded-lg">
              <table className="min-w-full text-xs">
                <thead className="bg-slate-50">
                  <tr>{preview.headers.map((h) => <th key={h} className="px-3 py-1.5 text-left font-semibold text-slate-600">{h}</th>)}</tr>
                </thead>
                <tbody>
                  {preview.sample_rows.map((r, i) => (
                    <tr key={i} className="border-t border-slate-100">
                      {r.map((c, j) => <td key={j} className="px-3 py-1.5 text-slate-700">{c}</td>)}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {missingRequired.length > 0 && (
              <p className="text-xs text-amber-700">Map the required field(s): {missingRequired.map((f) => f.label).join(", ")}</p>
            )}
            <div className="flex gap-2">
              <Button variant="primary" onClick={() => execute.mutate()} disabled={missingRequired.length > 0 || execute.isPending}>
                {execute.isPending ? "Importing…" : `Import ${preview.total_rows} row(s)`}
              </Button>
              <Button variant="secondary" onClick={reset}>Clear</Button>
            </div>
          </div>
        )}

        {result && (
          <div className="rounded-lg border border-slate-200 p-3 space-y-2">
            <p className="font-medium text-slate-800">{result.message}</p>
            {result.errors.length > 0 && (
              <ul className="text-xs text-rose-700 space-y-0.5 max-h-40 overflow-y-auto">
                {result.errors.map((e, i) => (
                  <li key={i}>Row {e.row}{e.key ? ` (${e.key})` : ""}: {e.error}</li>
                ))}
              </ul>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ─── Webhooks ───────────────────────────────────────────────────────────────

function WebhookCard({ notify, refreshLogs }: { notify: (t: string, k?: "success" | "error") => void; refreshLogs: () => void }) {
  const queryClient = useQueryClient();
  const [url, setUrl] = useState("");
  const [events, setEvents] = useState<string[]>([]);
  const [enabled, setEnabled] = useState(true);
  const [showSecret, setShowSecret] = useState(false);

  const { data: cfg } = useQuery<WebhookConfig>({
    queryKey: ["webhook-config"],
    queryFn: () => api.get<WebhookConfig>("/integrations/webhooks"),
  });
  useEffect(() => {
    if (cfg?.configured) {
      setUrl(cfg.endpoint_url ?? "");
      setEvents(cfg.events);
      setEnabled(cfg.enabled);
    }
  }, [cfg]);

  const save = useMutation({
    mutationFn: (rotate: boolean) => api.put("/integrations/webhooks", { endpoint_url: url, events, enabled, rotate_secret: rotate }),
    onSuccess: () => {
      notify("Webhook saved.");
      queryClient.invalidateQueries({ queryKey: ["webhook-config"] });
    },
    onError: (e) => notify(errorMessage(e), "error"),
  });
  const remove = useMutation({
    mutationFn: () => api.delete("/integrations/webhooks"),
    onSuccess: () => {
      setUrl("");
      setEvents([]);
      notify("Webhook removed.");
      queryClient.invalidateQueries({ queryKey: ["webhook-config"] });
    },
  });
  const test = useMutation({
    mutationFn: () => api.post<{ success: boolean; status_code: number; response_body: string }>("/integrations/webhooks/test"),
    onSuccess: (r) => {
      notify(r.success ? `Test delivered (HTTP ${r.status_code}).` : `Test failed: ${r.status_code ? `HTTP ${r.status_code}` : r.response_body}`, r.success ? "success" : "error");
      queryClient.invalidateQueries({ queryKey: ["webhook-config"] });
      refreshLogs();
    },
    onError: (e) => notify(errorMessage(e), "error"),
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm flex items-center gap-2">
          <Webhook size={15} className="text-amber-600" /> Webhooks
        </CardTitle>
        <CardDescription>Signed JSON events (X-CPQ-Signature: HMAC-SHA256 of the body using the secret) are POSTed when quotes change state.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <input className={inputCls} placeholder="https://example.com/webhooks/cpq" value={url} onChange={(e) => setUrl(e.target.value)} />
        <div className="flex flex-wrap gap-3">
          {(cfg?.available_events ?? []).map((ev) => (
            <label key={ev} className="flex items-center gap-1.5 text-xs">
              <input type="checkbox" checked={events.includes(ev)} onChange={(e) => setEvents((cur) => (e.target.checked ? [...cur, ev] : cur.filter((x) => x !== ev)))} />
              {ev}
            </label>
          ))}
        </div>
        <label className="flex items-center gap-2 text-xs">
          <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} /> Enabled
        </label>
        {cfg?.configured && (
          <div className="text-xs text-slate-600 space-y-1">
            <div>
              Signing secret:{" "}
              <code className="bg-slate-100 px-1.5 py-0.5 rounded">{showSecret ? cfg.secret_key : "whsec_••••••••••••"}</code>{" "}
              <button className="text-blue-600 cursor-pointer" onClick={() => setShowSecret((s) => !s)}>{showSecret ? "hide" : "show"}</button>{" "}
              <button className="text-blue-600 cursor-pointer" onClick={() => save.mutate(true)}>rotate</button>
            </div>
            <div>Last delivery: {cfg.last_delivery_status ?? "none yet"}{cfg.last_delivery_at ? ` · ${new Date(cfg.last_delivery_at + "Z").toLocaleString()}` : ""}</div>
          </div>
        )}
        <div className="flex gap-2">
          <Button variant="primary" onClick={() => save.mutate(false)} disabled={!url || events.length === 0 || save.isPending}>Save</Button>
          {cfg?.configured && (
            <>
              <Button variant="secondary" onClick={() => test.mutate()} disabled={test.isPending}>{test.isPending ? "Sending…" : "Send test event"}</Button>
              <Button variant="danger" onClick={() => remove.mutate()}>Remove</Button>
            </>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
