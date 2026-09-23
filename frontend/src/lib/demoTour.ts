export type DemoAction =
  | "navigate"
  | "highlight"
  | "open-panel"
  | "select-options"
  | "show-waterfall"
  | "inject-line"
  | "submit-visual"
  | "decide-approval"
  | "sync-visual";

export interface DemoSimulationFlags {
  openCustomerRecord: boolean;
  openProductRecord: boolean;
  configQuantity: number;
  showConfigSuccess: boolean;
  showPricingWaterfall: boolean;
  pricingTab: "configurations" | "calculator";
  quoteBuilder: boolean;
  quoteLineCount: number;
  quoteSubmitted: boolean;
  approvalDecided: boolean;
  approvalsTab: "pending" | "history";
  showSyncSuccess: boolean;
  salesforceConnected: boolean;
}

export const DEFAULT_DEMO_FLAGS: DemoSimulationFlags = {
  openCustomerRecord: false,
  openProductRecord: false,
  configQuantity: 1,
  showConfigSuccess: false,
  showPricingWaterfall: false,
  pricingTab: "configurations",
  quoteBuilder: true,
  quoteLineCount: 0,
  quoteSubmitted: false,
  approvalDecided: false,
  approvalsTab: "pending",
  showSyncSuccess: false,
  salesforceConnected: false,
};

export interface DemoToast {
  title: string;
  body: string;
  variant: "success" | "info";
}

export interface DemoStep {
  id: string;
  route: string;
  /** CSS selector, typically `[data-demo="..."]` */
  target?: string;
  title: string;
  body: string;
  action?: DemoAction;
  durationMs?: number;
  flags?: Partial<DemoSimulationFlags>;
  toast?: DemoToast;
}

export const DEMO_CREDENTIALS = {
  email: "aarav.lunkad@enterprise.com",
  password: "Password123!",
} as const;

export const DEMO_TOUR_STORAGE_KEY = "cpq-demo-tour";
export const DEMO_PENDING_STORAGE_KEY = "cpq-demo-pending";

export interface DemoTourPersistedState {
  isActive: boolean;
  stepIndex: number;
}

const DEFAULT_DURATION_MS = 5500;

export const DEMO_STEPS: DemoStep[] = [
  {
    id: "dashboard-intro",
    route: "/dashboard",
    target: '[data-demo="dashboard-kpis"]',
    title: "Command center",
    body: "Aarav opens CPQ for the morning pipeline. Revenue, active quotes, and two pending sign-offs are already in view — including the Acme deal.",
    action: "highlight",
    durationMs: DEFAULT_DURATION_MS,
  },
  {
    id: "dashboard-quote",
    route: "/dashboard",
    target: '[data-demo="quote-q-2026-0001"]',
    title: "Deal in motion: Q-2026-0001",
    body: "Acme IT Infrastructure Upgrade is the live opportunity — $14,342, still in draft. We’ll walk the same path a sales exec takes to close it.",
    action: "highlight",
    durationMs: DEFAULT_DURATION_MS,
  },
  {
    id: "customers-list",
    route: "/customers",
    target: '[data-demo="customer-acme"]',
    title: "Find the account",
    body: "Quotes start with a customer. Acme Corporation (CUST-001) is the Technology enterprise account for this walkthrough — injected so the table is never empty.",
    action: "highlight",
    durationMs: DEFAULT_DURATION_MS,
    flags: { openCustomerRecord: false },
  },
  {
    id: "customers-open",
    route: "/customers",
    target: '[data-demo="customer-drawer"]',
    title: "Open Acme Corporation",
    body: "Simulated click opens the account record: billing in San Francisco, primary contact Sarah Johnson. No CRM write is sent.",
    action: "open-panel",
    durationMs: DEFAULT_DURATION_MS,
    flags: { openCustomerRecord: true },
  },
  {
    id: "catalog-list",
    route: "/catalog",
    target: '[data-demo="catalog-table"]',
    title: "Shop the catalog",
    body: "The deal mixes three SKUs: Dell Latitude 7440 hardware, Enterprise Cloud Subscription seats, and Implementation Consulting. Latitude is the configurable hero product.",
    action: "highlight",
    durationMs: DEFAULT_DURATION_MS,
    flags: { openCustomerRecord: false, openProductRecord: false },
  },
  {
    id: "catalog-latitude",
    route: "/catalog",
    target: '[data-demo="catalog-latitude"]',
    title: "Select Dell Latitude 7440",
    body: "Simulated selection of DEV-LAP-001. List price $1,299 NRC. We’ll configure CPU, RAM, and storage next, then price ten units at 10% off.",
    action: "open-panel",
    durationMs: DEFAULT_DURATION_MS,
    flags: { openProductRecord: true },
  },
  {
    id: "config-cpu",
    route: "/configuration",
    target: '[data-demo="config-option-processor"]',
    title: "Configure the workstation",
    body: "Guided config: Intel Core i7-13700H is selected for the Acme developer fleet. Compatible options stay enabled; incompatible SKUs never appear.",
    action: "select-options",
    durationMs: DEFAULT_DURATION_MS,
    flags: { openProductRecord: false, configQuantity: 10, showConfigSuccess: false },
  },
  {
    id: "config-memory-storage",
    route: "/configuration",
    target: '[data-demo="config-option-memory"]',
    title: "RAM and storage",
    body: "32GB DDR5 and 1TB NVMe are applied — the recommended bundle for Latitude 7440. Quantity is set to 10 workstations to match the quote.",
    action: "select-options",
    durationMs: DEFAULT_DURATION_MS,
    flags: { configQuantity: 10 },
  },
  {
    id: "config-validate",
    route: "/configuration",
    target: '[data-demo="config-validation"]',
    title: "Validation succeeds",
    body: "All dependency rules pass. The configured unit is ready to drop onto Q-2026-0001 — still a local simulation, not a catalog mutation.",
    action: "highlight",
    durationMs: DEFAULT_DURATION_MS,
    flags: { showConfigSuccess: true, configQuantity: 10 },
  },
  {
    id: "pricing-table",
    route: "/pricing",
    target: '[data-demo="pricing-table"]',
    title: "Pricing methods",
    body: "List, volume, and cost-plus methods sit on each SKU. Latitude uses standard list with a volume override rule that flags 10% discounts into approvals.",
    action: "highlight",
    durationMs: DEFAULT_DURATION_MS,
    flags: { pricingTab: "configurations", showPricingWaterfall: false },
  },
  {
    id: "pricing-waterfall",
    route: "/pricing",
    target: '[data-demo="pricing-calculator"]',
    title: "10% override preview",
    body: "Ten units × $1,299 list, then a 10% line override. Waterfall: $12,990 → −$1,299 → $11,691 net for hardware. This is the number that will need sign-off.",
    action: "show-waterfall",
    durationMs: 6500,
    flags: { pricingTab: "calculator", showPricingWaterfall: true },
  },
  {
    id: "quotes-customer",
    route: "/quotes",
    target: '[data-demo="quotes-header"]',
    title: "Quote builder",
    body: "Q-2026-0001 is opened for Acme. Customer, validity, and currency are already filled — the way a saved draft looks after discovery.",
    action: "navigate",
    durationMs: DEFAULT_DURATION_MS,
    flags: { quoteBuilder: true, quoteLineCount: 0, quoteSubmitted: false },
  },
  {
    id: "quotes-lines",
    route: "/quotes",
    target: '[data-demo="quotes-lines"]',
    title: "Add configured lines",
    body: "Simulated add: 10× Latitude (configured), 50× Enterprise Cloud Subscription, and Implementation Consulting. Totals will land at $14,341 before tax.",
    action: "inject-line",
    durationMs: DEFAULT_DURATION_MS,
    flags: { quoteBuilder: true, quoteLineCount: 3 },
  },
  {
    id: "quotes-totals",
    route: "/quotes",
    target: '[data-demo="quotes-summary"]',
    title: "Totals: $14,341",
    body: "Subtotal $15,640 minus the $1,299 hardware override. Expected margin stays healthy at 32.5%. Ready to send for discount approval.",
    action: "highlight",
    durationMs: DEFAULT_DURATION_MS,
    flags: { quoteBuilder: true, quoteLineCount: 3 },
  },
  {
    id: "quotes-submit",
    route: "/quotes",
    target: '[data-demo="quotes-submit"]',
    title: "Submit for approval",
    body: "Review & Submit is simulated only. The quote moves to SUBMITTED in demo state — no POST to /quotes. Approvers will see the 10% override next.",
    action: "submit-visual",
    durationMs: DEFAULT_DURATION_MS,
    flags: { quoteBuilder: true, quoteLineCount: 3, quoteSubmitted: true },
    toast: {
      title: "Quote submitted",
      body: "Q-2026-0001 sent for discount approval (simulated — nothing was saved).",
      variant: "success",
    },
  },
  {
    id: "approvals-pending",
    route: "/approvals",
    target: '[data-demo="approval-acme"]',
    title: "Approval queue",
    body: "Finance sees Q-2026-0001 pending: 10% hardware override, 32.5% margin, requested by the sales exec. Approve/Reject here is visual only.",
    action: "highlight",
    durationMs: DEFAULT_DURATION_MS,
    flags: { approvalDecided: false, approvalsTab: "pending" },
  },
  {
    id: "approvals-decide",
    route: "/approvals",
    target: '[data-demo="approval-acme"]',
    title: "Approved",
    body: "Simulated manager approval. The row flips to APPROVED and the sales team is notified in-product. No approve API is called.",
    action: "decide-approval",
    durationMs: DEFAULT_DURATION_MS,
    flags: { approvalDecided: true, approvalsTab: "history" },
    toast: {
      title: "Approved",
      body: "Q-2026-0001 approved. Ready to sync the opportunity downstream.",
      variant: "success",
    },
  },
  {
    id: "integrations-grid",
    route: "/integrations",
    target: '[data-demo="integrations-salesforce"]',
    title: "CRM connector",
    body: "Approved quotes can push accounts and opportunities to Salesforce, import catalogs from Excel, and emit webhooks. We’ll simulate a Salesforce sync.",
    action: "highlight",
    durationMs: DEFAULT_DURATION_MS,
    flags: { salesforceConnected: false, showSyncSuccess: false },
  },
  {
    id: "integrations-sync",
    route: "/integrations",
    target: '[data-demo="integrations-salesforce"]',
    title: "Synced to Salesforce",
    body: "Opportunity Q-2026-0001 shows as connected. That closes the loop: account → catalog → config → price → quote → approval → CRM — all simulated, nothing persisted.",
    action: "sync-visual",
    durationMs: 6500,
    flags: { salesforceConnected: true, showSyncSuccess: true },
    toast: {
      title: "Synced to Salesforce",
      body: "Acme opportunity updated (demo status only).",
      variant: "success",
    },
  },
];

export function accumulateDemoFlags(stepIndex: number): DemoSimulationFlags {
  let flags: DemoSimulationFlags = { ...DEFAULT_DEMO_FLAGS };
  const last = Math.min(Math.max(stepIndex, 0), DEMO_STEPS.length - 1);
  for (let i = 0; i <= last; i += 1) {
    const partial = DEMO_STEPS[i]?.flags;
    if (partial) flags = { ...flags, ...partial };
  }
  return flags;
}

export function readDemoTourState(): DemoTourPersistedState | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = sessionStorage.getItem(DEMO_TOUR_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as DemoTourPersistedState;
    if (typeof parsed.isActive !== "boolean" || typeof parsed.stepIndex !== "number") {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

export function writeDemoTourState(state: DemoTourPersistedState) {
  if (typeof window === "undefined") return;
  sessionStorage.setItem(DEMO_TOUR_STORAGE_KEY, JSON.stringify(state));
}

export function clearDemoTourState() {
  if (typeof window === "undefined") return;
  sessionStorage.removeItem(DEMO_TOUR_STORAGE_KEY);
}
