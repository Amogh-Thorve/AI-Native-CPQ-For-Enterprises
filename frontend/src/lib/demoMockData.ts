import type { CustomerListResponse, CustomerRead } from "@/types/customer";
import type { CategoryRead, ProductRead } from "@/types/catalog";

export const DEMO_ACME_ID = 9001;
export const DEMO_LATITUDE_ID = 9101;
export const DEMO_CLOUD_ID = 9102;
export const DEMO_CONSULTING_ID = 9103;
export const DEMO_QUOTE_ID = 9201;
export const DEMO_APPROVAL_ID = 9301;

const NOW = "2026-09-23T10:30:00.000Z";

export const DEMO_CATEGORIES: CategoryRead[] = [
  { id: 91, name: "Hardware", description: "Laptops and workstations" },
  { id: 92, name: "Cloud / SaaS", description: "Subscription SKUs" },
  { id: 93, name: "Professional Services", description: "Implementation and consulting" },
];

export const DEMO_CUSTOMERS: CustomerRead[] = [
  {
    id: DEMO_ACME_ID,
    tenant_id: "demo-tenant",
    customer_number: "CUST-001",
    legal_name: "Acme Corporation",
    display_name: "Acme",
    email: "sarah.johnson@acme.com",
    phone: "+1 (415) 555-0123",
    website: "https://acme.example",
    industry: "Technology",
    customer_type: "BUSINESS",
    status: "ACTIVE",
    owner_id: "aarav.lunkad",
    created_at: NOW,
    updated_at: NOW,
    contacts: [
      {
        id: 9401,
        customer_id: DEMO_ACME_ID,
        first_name: "Sarah",
        last_name: "Johnson",
        email: "sarah.johnson@acme.com",
        phone: "+1 (415) 555-0123",
        is_primary: true,
        created_at: NOW,
      },
    ],
    addresses: [
      {
        id: 9501,
        customer_id: DEMO_ACME_ID,
        address_type: "BILLING",
        line1: "100 Market Street",
        line2: "Floor 24",
        city: "San Francisco",
        state: "CA",
        postal_code: "94105",
        country: "US",
        is_primary: true,
        created_at: NOW,
      },
    ],
  },
  {
    id: 9002,
    tenant_id: "demo-tenant",
    customer_number: "CUST-002",
    legal_name: "Global Logistics Tech",
    display_name: "GLT",
    email: "ops@globallogistics.example",
    phone: "+1 (312) 555-0199",
    website: null,
    industry: "Logistics",
    customer_type: "BUSINESS",
    status: "ACTIVE",
    owner_id: "aarav.lunkad",
    created_at: NOW,
    updated_at: NOW,
    contacts: [],
    addresses: [],
  },
];

export const DEMO_CUSTOMER_LIST: CustomerListResponse = {
  items: DEMO_CUSTOMERS,
  total: DEMO_CUSTOMERS.length,
  page: 1,
  page_size: 10,
  pages: 1,
};

export const DEMO_PRODUCTS: ProductRead[] = [
  {
    id: DEMO_LATITUDE_ID,
    sku: "DEV-LAP-001",
    name: "Dell Latitude 7440",
    description:
      "Configurable enterprise workstation. Pair with cloud seats and implementation consulting on the Acme deal.",
    base_price: 1299,
    cost_price: 875,
    currency: "USD",
    margin_amount: 424,
    margin_percentage: 32.6,
    is_active: true,
    billing_type: "NRC",
    category_id: 91,
    category: DEMO_CATEGORIES[0],
  },
  {
    id: DEMO_CLOUD_ID,
    sku: "SaaS-TIER-SEED",
    name: "Enterprise Cloud Subscription",
    description: "50-seat cloud platform subscription used on Q-2026-0001.",
    base_price: 49,
    cost_price: 12,
    currency: "USD",
    margin_amount: 37,
    margin_percentage: 75.5,
    is_active: true,
    billing_type: "MRC",
    category_id: 92,
    category: DEMO_CATEGORIES[1],
  },
  {
    id: DEMO_CONSULTING_ID,
    sku: "DEV-SVC-IMP",
    name: "Implementation Consulting",
    description: "Fixed-fee professional services for hardware and cloud rollout.",
    base_price: 1500,
    cost_price: 620,
    currency: "USD",
    margin_amount: 880,
    margin_percentage: 58.7,
    is_active: true,
    billing_type: "NRC",
    category_id: 93,
    category: DEMO_CATEGORIES[2],
  },
];

export interface DemoQuoteListItem {
  id: number;
  quote_number: string;
  version: number;
  customer_id: number;
  title: string;
  description: string;
  status: "DRAFT" | "SUBMITTED" | "APPROVED" | "REJECTED" | "EXPIRED" | "CANCELLED";
  currency: string;
  valid_until: string;
  notes: string;
  subtotal: string;
  discount_amount: string;
  discount_total: string;
  tax_amount: string;
  total_amount: string;
  grand_total: string;
  margin_percentage: string;
  margin_amount: string;
  created_by_id: string;
  created_at: string;
  customer: {
    id: number;
    name: string;
    legal_name: string;
    customer_number: string;
    email: string;
    industry: string;
  };
  items: {
    id: number;
    product_id: number;
    product_name: string;
    sku: string;
    billing_type: string;
    currency: string;
    quantity: number;
    unit_price: number;
    discount_percentage: number;
    line_total: number;
    configuration_status: "CONFIGURED" | "STANDARD";
    configuration_version?: string;
  }[];
}

export const DEMO_QUOTE_LINES: DemoQuoteListItem["items"] = [
  {
    id: 1,
    product_id: DEMO_LATITUDE_ID,
    product_name: "Dell Latitude 7440",
    sku: "DEV-LAP-001",
    billing_type: "NRC",
    currency: "USD",
    quantity: 10,
    unit_price: 1299,
    discount_percentage: 10,
    line_total: 11691,
    configuration_status: "CONFIGURED",
    configuration_version: "v1.0",
  },
  {
    id: 2,
    product_id: DEMO_CLOUD_ID,
    product_name: "Enterprise Cloud Subscription",
    sku: "SaaS-TIER-SEED",
    billing_type: "MRC",
    currency: "USD",
    quantity: 50,
    unit_price: 49,
    discount_percentage: 0,
    line_total: 2450,
    configuration_status: "STANDARD",
  },
  {
    id: 3,
    product_id: DEMO_CONSULTING_ID,
    product_name: "Implementation Consulting",
    sku: "DEV-SVC-IMP",
    billing_type: "NRC",
    currency: "USD",
    quantity: 1,
    unit_price: 1500,
    discount_percentage: 0,
    line_total: 1500,
    configuration_status: "STANDARD",
  },
];

export function buildDemoQuote(status: DemoQuoteListItem["status"]): DemoQuoteListItem {
  return {
    id: DEMO_QUOTE_ID,
    quote_number: "Q-2026-0001",
    version: 1,
    customer_id: DEMO_ACME_ID,
    title: "Acme IT Infrastructure Upgrade",
    description:
      "IT infrastructure upgrade including hardware, software licenses, and professional services.",
    status,
    currency: "USD",
    valid_until: "2026-09-30",
    notes: "Simulated demo quote — not persisted.",
    subtotal: "15640.00",
    discount_amount: "1299.00",
    discount_total: "1299.00",
    tax_amount: "0.00",
    total_amount: "14341.00",
    grand_total: "14341.00",
    margin_percentage: "32.5",
    margin_amount: "6834.00",
    created_by_id: "aarav.lunkad",
    created_at: NOW,
    customer: {
      id: DEMO_ACME_ID,
      name: "Acme Corporation",
      legal_name: "Acme Corporation",
      customer_number: "CUST-001",
      email: "sarah.johnson@acme.com",
      industry: "Technology",
    },
    items: DEMO_QUOTE_LINES,
  };
}

export interface DemoApprovalItem {
  id: number;
  quote_number: string;
  customer_name: string;
  amount: string;
  discount_percentage: string;
  margin_percentage: string;
  requested_by: string;
  requested_role: string;
  status: "PENDING" | "APPROVED" | "REJECTED";
  submitted_date: string;
  reason: string;
}

export function buildDemoApprovals(acmeStatus: DemoApprovalItem["status"]): DemoApprovalItem[] {
  return [
    {
      id: DEMO_APPROVAL_ID,
      quote_number: "Q-2026-0001",
      customer_name: "Acme Corporation",
      amount: "$14,342.00",
      discount_percentage: "10.0%",
      margin_percentage: "32.5%",
      requested_by: "Aarav Lunkad",
      requested_role: "Sales Exec",
      status: acmeStatus,
      submitted_date: "2026-09-23 14:30",
      reason: "Volume hardware 10% override on 10× Dell Latitude 7440",
    },
    {
      id: 9302,
      quote_number: "Q-2026-0004",
      customer_name: "Global Logistics Tech",
      amount: "$48,920.00",
      discount_percentage: "18.5%",
      margin_percentage: "26.1%",
      requested_by: "Michael Chang",
      requested_role: "Account Executive",
      status: "PENDING",
      submitted_date: "2026-09-22 17:15",
      reason: "Competitive displacement vs Legacy Oracle CPQ",
    },
  ];
}

export interface DemoEnrichedProduct {
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

export const DEMO_PRICING_PRODUCTS: DemoEnrichedProduct[] = [
  {
    id: DEMO_LATITUDE_ID,
    sku: "DEV-LAP-001",
    name: "Dell Latitude 7440",
    description: "Volume hardware with 10% override on 10 units",
    base_price: "1299.00",
    cost_price: "875.00",
    currency: "USD",
    is_active: true,
    billing_type: "NRC",
    category_name: "Hardware",
    pricing_method: "STANDARD",
    markup_percent: "48.00",
    discount_percent: "10.00",
    status: "ACTIVE",
    effective_from: "Always Active",
    has_tiers: true,
  },
  {
    id: DEMO_CLOUD_ID,
    sku: "SaaS-TIER-SEED",
    name: "Enterprise Cloud Subscription",
    base_price: "49.00",
    cost_price: "12.00",
    currency: "USD",
    is_active: true,
    billing_type: "MRC",
    category_name: "Cloud / SaaS",
    pricing_method: "TIERED",
    markup_percent: "0.00",
    status: "ACTIVE",
    effective_from: "Always Active",
    has_tiers: true,
  },
  {
    id: DEMO_CONSULTING_ID,
    sku: "DEV-SVC-IMP",
    name: "Implementation Consulting",
    base_price: "1500.00",
    cost_price: "620.00",
    currency: "USD",
    is_active: true,
    billing_type: "NRC",
    category_name: "Professional Services",
    pricing_method: "COST_PLUS_MARKUP",
    markup_percent: "141.00",
    status: "ACTIVE",
    effective_from: "Always Active",
    has_tiers: false,
  },
];

export const DEMO_PRICING_WATERFALL = {
  product_id: DEMO_LATITUDE_ID,
  product_name: "Dell Latitude 7440",
  sku: "DEV-LAP-001",
  quantity: 10,
  pricing_method: "STANDARD",
  billing_type: "NRC",
  base_unit_price: "1299.00",
  discount_percent: "10.00",
  discount_amount: "1299.00",
  final_unit_price: "1169.10",
  total_price: "11691.00",
  unit_cost: "875.00",
  total_cost: "8750.00",
  margin_amount: "2941.00",
  margin_percentage: "25.2",
  currency: "USD",
  calculation_breakdown: [
    { step: "List", amount: "12990.00" },
    { step: "Volume / override 10%", amount: "-1299.00" },
    { step: "Net", amount: "11691.00" },
  ],
};

export const DEMO_PRICING_RULES = [
  {
    id: 9601,
    name: "Acme volume hardware override",
    rule_type: "DISCOUNT",
    is_active: true,
    conditions: { sku: "DEV-LAP-001", min_qty: 10 },
    actions: { discount_percent: 10 },
    description: "10% line override when Latitude qty ≥ 10 — triggers approval.",
    status: "ACTIVE",
  },
];

export const DEMO_CONFIG_OPTIONS: Record<string, string> = {
  processor: "Intel Core i7-13700H (14-Core, up to 5.0GHz)",
  memory: "32GB DDR5 5200MHz (2x16GB)",
  storage: "1TB M.2 PCIe NVMe SSD Class 40",
  display: "15.6 FHD+ (1920 x 1200) Anti-Glare 500 nits",
  os: "Windows 11 Pro Enterprise License",
  support: "3-Year ProSupport Plus with Next Business Day Onsite",
};
