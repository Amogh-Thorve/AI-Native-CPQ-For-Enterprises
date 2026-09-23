"use client";

import React, { useState } from "react";
import {
  ArrowRightLeft,
  FileSpreadsheet,
  CloudLightning,
  ShieldCheck,
  Upload,
  AlertCircle,
  CheckCircle2,
  RefreshCw,
  ExternalLink,
  Settings,
  Database
} from "lucide-react";
import { useDemoTour } from "@/components/demo/DemoTourProvider";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
  Button,
  StatusBadge,
  PageHeader
} from "@/components/ui";

interface IntegrationItem {
  id: string;
  name: string;
  type: string;
  description: string;
  status: "CONNECTED" | "DISCONNECTED" | "CONFIGURED";
  lastSync: string;
  icon: React.ReactNode;
  syncCount?: string;
}

export default function IntegrationsPage() {
  const [integrations, setIntegrations] = useState<IntegrationItem[]>([
    {
      id: "salesforce",
      name: "Salesforce CRM",
      type: "CRM Connector",
      description:
        "Authenticate via OAuth 2.0 to import accounts, contacts, and opportunities. Automatically sync approved CPQ quotes back to Salesforce opportunities.",
      status: "DISCONNECTED",
      lastSync: "Never synced",
      icon: <CloudLightning size={22} className="text-blue-600" />,
      syncCount: "0 opportunities mapped",
    },
    {
      id: "excel",
      name: "Excel / CSV Batch Pipeline",
      type: "Flat File Uploader",
      description:
        "Batch import product catalogs, customer master files, category hierarchies, and custom price books with automatic schema validation.",
      status: "CONNECTED",
      lastSync: "Today at 10:45 AM",
      icon: <FileSpreadsheet size={22} className="text-emerald-600" />,
      syncCount: "142 SKUs active",
    },
    {
      id: "sap_erp",
      name: "SAP S/4HANA ERP Connector",
      type: "Enterprise ERP",
      description:
        "Bi-directional synchronization of sales orders, inventory availability, billing schedules, and customer ledger master data.",
      status: "DISCONNECTED",
      lastSync: "Connector standby",
      icon: <Database size={22} className="text-indigo-600" />,
      syncCount: "Planned Q4 2026",
    },
    {
      id: "webhooks",
      name: "CPQ Cognitive Webhooks API",
      type: "REST & Event Bus",
      description:
        "Real-time event webhooks triggered on Quote Created, Quote Approved, and Revision Generated to downstream microservices.",
      status: "CONNECTED",
      lastSync: "3 mins ago",
      icon: <ArrowRightLeft size={22} className="text-teal-600" />,
      syncCount: "1,290 events processed",
    },
  ]);

  const toggleSalesforce = () => {
    setIntegrations((prev) =>
      prev.map((item) =>
        item.id === "salesforce"
          ? {
              ...item,
              status: item.status === "CONNECTED" ? "DISCONNECTED" : "CONNECTED",
              lastSync: item.status === "CONNECTED" ? "Never synced" : "Just now",
              syncCount: item.status === "CONNECTED" ? "0 mapped" : "48 opportunities mapped",
            }
          : item
      )
    );
  };

  return (
    <div className="space-y-6">
      {/* ─── Page Header ────────────────────────────────────────── */}
      <div data-demo="integrations-header">
      <PageHeader
        title="Integrations & Connectors"
        description="Sync accounts and products using CSV imports or dynamic enterprise CRM & ERP pipeline synchronization."
      />
      </div>

      {/* ─── Integrations Grid ──────────────────────────────────── */}
      <div data-demo="integrations-grid" className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {integrations.map((item) => (
          <Card key={item.id} className="flex flex-col justify-between">
            <CardHeader className="pb-3">
              <div className="flex items-start justify-between w-full">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-slate-50 border border-slate-200/80 flex items-center justify-center shrink-0">
                    {item.icon}
                  </div>
                  <div>
                    <CardTitle className="text-sm">{item.name}</CardTitle>
                    <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block">
                      {item.type}
                    </span>
                  </div>
                </div>
                <StatusBadge status={item.status} />
              </div>
            </CardHeader>

            <CardContent className="space-y-3.5 text-xs text-slate-600">
              <p className="leading-relaxed">{item.description}</p>

              <div className="p-3 bg-slate-50 rounded-xl border border-slate-100 flex items-center justify-between text-[11px]">
                <div>
                  <span className="text-slate-400 block">Last Sync:</span>
                  <span className="font-semibold text-slate-800">{item.lastSync}</span>
                </div>
                <div className="text-right">
                  <span className="text-slate-400 block">Status Detail:</span>
                  <span className="font-semibold text-slate-800">{item.syncCount}</span>
                </div>
              </div>
            </CardContent>

            <CardFooter className="flex items-center justify-between">
              {item.id === "salesforce" ? (
                <Button
                  variant={item.status === "CONNECTED" ? "danger" : "primary"}
                  size="sm"
                  onClick={toggleSalesforce}
                >
                  {item.status === "CONNECTED" ? "Disconnect Salesforce" : "Link Salesforce Account"}
                </Button>
              ) : item.id === "excel" ? (
                <Button
                  variant="primary"
                  size="sm"
                  icon={<Upload size={14} />}
                  onClick={() => {
                    window.location.href = "/catalog";
                  }}
                >
                  Open Excel Importer
                </Button>
              ) : item.id === "sap_erp" ? (
                <Button variant="secondary" size="sm" disabled>
                  Coming Soon (Q4)
                </Button>
              ) : (
                <Button variant="secondary" size="sm" onClick={() => alert("Webhook keys active.")}>
                  Configure Webhooks
                </Button>
              )}

              <Button
                variant="ghost"
                size="sm"
                icon={<Settings size={14} />}
                onClick={() => alert(`Managing settings for ${item.name}`)}
              >
                Settings
              </Button>
            </CardFooter>
          </Card>
        ))}
      </div>
    </div>
  );
}
