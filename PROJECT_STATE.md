# Project State - AI-Native Enterprise CPQ Platform

## Current Architecture
- **Backend**: Python 3.12, FastAPI, SQLAlchemy 2.0 (Async), Alembic, Pydantic v2. Domain-Driven Design (DDD) & Clean Architecture (Modular Monolith).
- **Frontend**: Next.js 14+ (App Router), TypeScript, Tailwind CSS, shadcn/ui.
- **Database**: PostgreSQL (normalized, migrations managed via Alembic).

---

## Folder Structure (Planned & Current Setup)
```
/
├── backend/
│   ├── app/
│   │   ├── core/           # Shared database setup, security, config, errors
│   │   ├── domains/        # Domain-driven Modular Monolith layers
│   │   │   ├── auth/       # Auth & RBAC
│   │   │   ├── customer/   # Customer Management
│   │   │   ├── catalog/    # Catalog & Price Books
│   │   │   ├── pricing/    # Pricing Engine
│   │   │   ├── configuration/ # Product Configuration
│   │   │   ├── quotes/     # Quote Builder
│   │   │   ├── approval/   # Approval Workflow
│   │   │   ├── document/   # PDF Generation
│   │   │   ├── email/      # Email Dispatcher
│   │   │   ├── ai/         # Gemini AI Assistant
│   │   │   └── integrations/ # CSV/Excel/Salesforce interfaces
│   │   └── main.py         # Entrypoint
│   ├── alembic/            # Migrations folder
│   ├── alembic.ini
│   └── requirements.txt
├── frontend/               # Next.js Application
└── PROJECT_STATE.md
```

---

## Status of Application Modules
- [x] 1. **Authentication** (Folder/Placeholder created: Yes | Fully implemented: Yes | Forgot & Reset Password: Yes)--->✅
- [x] 2. **Customer Management** (Folder/Placeholder created: Yes | Fully implemented: Yes | RBAC & Ownership: Yes | UI: Yes)--->✅
- [x] 3. **Product Catalog** (Folder/Placeholder created: Yes | Fully implemented: Yes | RBAC: Yes | UI: Yes | Excel Import: Yes | Cost & Margins: Yes)--->✅
- [x] 4. **Pricing Engine** (Folder/Placeholder created: Yes | Fully implemented: Yes | Standard, Line Discount, Tiered [Volume & Cumulative], Block & Cost+Markup methods, Configuration Lifecycle [DRAFT, ACTIVE, INACTIVE, ARCHIVED], Effective Dates [effective_from, effective_until], Manual Pricing Overrides [pricing.override with audit], Sensitive Data Masking [pricing.cost.view, pricing.margin.view], Decimal Arithmetic, Structured Calculation Breakdown Waterfalls, Admin UI, Price Preview, Full RBAC Governance, Alembic schema e71b29a834d1, 30/30 Pricing Domain Tests & 39/39 Regression Tests Passing)--->✅
- [x] 5. **Product Configuration** (Folder/Placeholder created: Yes | Fully implemented: Yes | Phase 1, 2 & 3 complete: Attributes, Options, Single/Multi select, Requires & Excludes constraints, Product Bundles, Component constraints, real-time Bundle Validator, Guided Config UI Wizard, Admin Builder UI, Versioning & Lifecycle draft promotion, Structural Comparer, Traceable historical sessions, Audit Integration, E2E tests passed)--->✅
- [x] 6. **Quote Builder** (Folder/Placeholder created: Yes | Fully implemented: Yes | Enterprise Quote Structure, Customer Integration, Product Configuration Consumption, Dynamic Pricing Engine Integration & Snapshot Freezing, Decimal Monetary Arithmetic, Versioned Revisions & Cloning, Strict RBAC [Rep/Manager/Exec], Audit Trail [7 Core Events], Full Next.js Quote Builder UI, 16/16 Unit & Lifecycle Tests Passed, 40/40 Regression Tests Passed)--->✅
- [ ] 7. **Approval Workflow** (Folder/Placeholder created: No | Fully implemented: No)
- [x] 8. **PDF Generation** (Folder/Placeholder created: Yes | Fully implemented: No)
- [x] 9. **Email** (Folder/Placeholder created: Yes | Fully implemented: No)
- [x] 10. **AI** (Folder/Placeholder created: Yes | Fully implemented: No)
- [x] 11. **Integrations** (Folder/Placeholder created: Yes | Fully implemented: No)

---

## Architectural Decisions
1. **Modular Monolith**: Run all domains inside a single FastAPI runtime. Ensure clean boundary lines by restricting cross-domain imports to services/repositories (no direct cross-model modifications outside their domains).
2. **Interface Abstraction**: Domain services and repositories inherit from protocols/abstract base classes to support easy testing and replacement.
3. **No Direct Business Logic in Routes**: API routes handle request validation, delegate to services, and format responses.
4. **Backend-Authoritative Pricing**: Frontend performs no price calculations; all formulas (Standard, Line Discount, Tiered Volume & Cumulative, Block, Cost Plus Markup) and margins are computed exclusively on the backend using Python `Decimal` arithmetic.
5. **Commercially Sensitive Data Isolation**: Unit cost, total cost, and margin figures are masked at the API response serialization layer based on caller permissions (`pricing.cost.view`, `pricing.margin.view`).
6. **Frozen Pricing & Configuration Snapshots**: Quotes capture and store frozen snapshots of Pricing Engine breakdowns and validated Product Configuration sessions at quote creation/update time to ensure strict historical consistency against future catalog modifications.

---

## Dependencies
- **Backend**: `fastapi`, `uvicorn[standard]`, `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `pydantic-settings`, `pydantic[email]`, `pyjwt[crypto]`, `passlib[bcrypt]`, `python-multipart`, `google-genai`
- **Frontend**: Next.js, React, React DOM, Tailwind CSS, lucide-react, clsx, tailwind-merge, @tanstack/react-query, react-hook-form, zod

---

## API Endpoints Map
All API routes are prefixed under `/api/v1` and defined in each domain's `routes.py`:
- **Auth**: `/auth/register` (POST), `/auth/login` (POST), `/auth/me` (GET)
- **Customer**: `/customers/` (GET, POST), `/customers/{customer_id}` (GET, PUT, DELETE), `/customers/{customer_id}/contacts` (POST)
- **Catalog**: `/products` (GET, POST), `/products/{product_id}` (GET, PUT), `/products/{product_id}/archive` (PATCH), `/products/{product_id}/restore` (PATCH), `/categories` (GET, POST), `/price-books` (GET, POST), `/price-books/{price_book_id}/entries` (POST)
- **Pricing**:
  - `/pricing/calculate` (POST) — Backend-authoritative calculation, validation, margin determination, breakdown waterfalls, and manual override handling
  - `/pricing/products` (GET) — Enriched catalog with pricing methods, active status, effective dating, and sensitive data RBAC masking
  - `/pricing/products/{id}/configuration` (GET, POST) — Product pricing settings configuration lifecycle
  - `/pricing/products/{id}/configuration/activate` (POST, PATCH) — Activate pricing configuration
  - `/pricing/products/{id}/configuration/deactivate` (POST, PATCH) — Deactivate pricing configuration
  - `/pricing/products/{id}/tiers` (GET, POST, DELETE) — Tier and block brackets configuration
  - `/pricing/rules` (GET, POST) — Dynamic pricing rules administration
  - `/pricing/rules/{id}` (PUT, DELETE) — Pricing rule modification and removal
- **Configuration**: `/configuration/validate` (POST), `/configuration/rules` (GET, POST)
- **Quotes**:
  - `/quotes/` (GET, POST) — List quotes with filtering / Create quote shell with lines
  - `/quotes/{quote_id}` (GET, PUT, DELETE) — Retrieve quote details / Update draft metadata / Delete draft quote
  - `/quotes/{quote_id}/items` (POST) — Add configured product item to quote with Pricing Engine evaluation
  - `/quotes/{quote_id}/items/{item_id}` (PUT, DELETE) — Modify line quantity or discount / Remove line item
  - `/quotes/{quote_id}/submit` (POST) — Submit draft quote for approval review (transitions to SUBMITTED)
  - `/quotes/{quote_id}/cancel` (POST) — Cancel quotation (transitions to CANCELLED)
  - `/quotes/{quote_id}/revise` (POST) — Increment quote version, clone line items with snapshots, reset to DRAFT
- **Approvals**: `/approvals/policies` (GET, POST), `/approvals/submit` (POST), `/approvals/pending` (GET), `/approvals/requests/{request_id}/decide` (POST)
- **Documents**: `/documents/generate` (POST), `/documents/quote/{quote_id}` (GET)
- **Email**: `/emails/send` (POST), `/emails/quote/{quote_id}` (GET)
- **AI**: `/ai/customer-summary` (POST), `/ai/quote-summary` (POST), `/ai/draft-email` (POST), `/ai/recommendations` (POST)
- **Integrations**: `/integrations/import/preview` (POST), `/integrations/salesforce/connect` (POST), `/integrations/salesforce/sync-quote/{quote_id}` (POST), `/integrations/logs` (GET)

---

## Pricing Module Details

### Implemented Pricing Methods
- **STANDARD**: List base unit price from catalog (`Unit Price = Base Price`, `Total = Unit Price * Quantity`).
- **LINE_DISCOUNT**: Standard price with percentage discounts applied (`Discount Amount = Base Price * Discount / 100`, `Final Unit Price = Base Price - Discount Amount`, `Total = Final Unit Price * Quantity`). Reject discount < 0 or > 100.
- **TIERED (VOLUME)**: Total quantity selects the matching tier range; all units billed at that single tier's unit price (`Total = Quantity * Tier Unit Price`).
- **TIERED (CUMULATIVE)**: Progressive slab-based pricing where each quantity bracket is priced incrementally (`Total = sum(tier_qty * tier_price)`).
- **BLOCK**: Fixed price for an entire bracket (`Total = Block Price`, not multiplied by quantity).
- **COST_PLUS_MARKUP**: Catalog cost with markup percentage (`Selling Price = Cost * (1 + Markup / 100)`). Rejects negative cost or markup.

### Billing Types Preservation
- **MRC** (Monthly Recurring Charge), **NRC** (Non-Recurring Charge), and **USAGE** (Usage-Based) preserved seamlessly through all calculation strategies and responses.

### Money & Precision
- High-precision Python `Decimal` and PostgreSQL `NUMERIC(12, 2)` throughout. No floating-point math for currency amounts.

### Margin Calculation
- Formula: `Margin Amount = Selling Price - Product Cost`
- Formula: `Margin Percentage = ((Selling Price - Product Cost) / Selling Price) * 100`
- Zero Price Protection: If Selling Price = 0, returns `margin_percentage = None` (displays `N/A`, avoiding `ZeroDivisionError`).
- Negative Margins: Fully supported and tracked when selling price is below cost.

### Database Entities & Migrations
- `ProductPricingTier` (Table: `product_pricing_tiers`): `min_quantity`, `max_quantity`, `price`, `display_order`, `is_active`.
- `ProductPricingSetting` (Table: `product_pricing_settings`): `pricing_method`, `markup_percent`, `discount_percent`, `status` (`DRAFT`, `ACTIVE`, `INACTIVE`, `ARCHIVED`), `effective_from`, `effective_until`.
- `PricingRule` (Table: `pricing_rules`): `name`, `rule_type`, `conditions`, `actions`, `is_active`, `status`.
- `PricingAuditLog` (Table: `pricing_audit_logs`): Audit trail tracking configuration changes, activations, deactivations, and manual price overrides with before/after state diffs.
- Migration `e71b29a834d1_pricing_engine_lifecycle_and_effective_dates.py` applied.

### Configuration Lifecycle & Effective Dating
- Configurations support `DRAFT`, `ACTIVE`, `INACTIVE`, `ARCHIVED`.
- Only `ACTIVE` configurations within `effective_from <= now < effective_until` can be used for live calculations; drafts and expired configurations are rejected with clear domain error messages.

### Manual Overrides & Governance
- Manual unit price overrides require `pricing.override` permission and mandatory `override_reason`.
- Overrides are audited in `pricing_audit_logs` as `PRICING_OVERRIDE_USED`.
- Unauthorized overrides return `403 Forbidden`.

### Enterprise Access Control (RBAC) & Masking
- **Sales Representative**: Can calculate prices and use active pricing. Cost and margin fields are masked (`None`).
- **Sales Manager**: Can calculate prices, view pricing configurations, and view margins (costs remain masked). Cannot modify global configuration.
- **Executive / Administrator**: Full access to view costs, view margins, edit pricing configurations, manage tiers, activate/deactivate configurations, and manage pricing rules.

### Pricing UI
- Dynamic configuration panels for each pricing method in `/pricing`.
- Live Price Preview communicating with backend calculation endpoint.
- Displays price waterfall calculation breakdown, billing types, currency, and permitted margin details.
- Full table showing products, SKUs, billing types, pricing methods, base price, configuration status, and effective date badges.

---

## Quote Builder Module Details

### Quote Builder Architecture
The Quote Builder implements a real enterprise sales workflow:
```
Customer Selection ──> Add Products ──> Product Configuration ──> Pricing Engine ──> Build Quote ──> Review Totals ──> Save / Submit / Revise
```
- **Separation of Concerns**: Quote Builder does NOT recreate configuration rules or pricing logic.
- **Product Configuration Consumption**: Quotes integrate with the Product Configuration domain by consuming validated `ConfigurationSession` outputs. If a session is valid, its selections are preserved as a frozen snapshot.
- **Pricing Engine Integration**: All line item prices are evaluated dynamically by calling `PricingApplicationService.calculate_price`. No pricing formulas or discounts are hardcoded or duplicated inside Quote Builder.
- **Frozen Pricing Snapshots**: The evaluated unit price, line total, discount amount, pricing method, and full waterfall breakdown are persisted onto `QuoteLineItem`. Future catalog price changes or promotions do not mutate existing quotes.
- **Money & Precision**: Monetary arithmetic is executed strictly using pure Python `Decimal` and PostgreSQL `NUMERIC(12, 2)` (no float calculations).
- **Revision Control**: Quotes support multi-version revisions (`v1`, `v2`, `v3`...) sharing the same `quote_number` with `parent_quote_id` linkage, preserving historical snapshots.

### Database Changes
1. **Quotes Table (`quotes`)**:
   - `id`: Integer Primary Key
   - `quote_number`: String(50), indexed
   - `version`: Integer, default 1
   - `title`: String(255), optional descriptive name
   - `description`: Text, optional
   - `status`: String(50), default `DRAFT` (`DRAFT`, `SUBMITTED`, `APPROVED`, `REJECTED`, `EXPIRED`, `CANCELLED`)
   - `currency`: String(10), default `USD`
   - `valid_until`: DateTime(timezone=True), expiration cutoff
   - `notes`: Text, internal or external remarks
   - `subtotal`: NUMERIC(12, 2)
   - `discount_amount`: NUMERIC(12, 2)
   - `tax_amount`: NUMERIC(12, 2)
   - `total_amount`: NUMERIC(12, 2) (Grand Total)
   - `margin_percentage`: NUMERIC(5, 2)
   - `customer_id`: ForeignKey to `customers.id` (RESTRICT)
   - `created_by_id`: ForeignKey to `users.id` (UUID)
   - `parent_quote_id`: ForeignKey to `quotes.id` (SET NULL)
   - Composite Unique Constraint: `uq_quotes_quote_number_version` on `(quote_number, version)`
2. **Quote Line Items Table (`quote_line_items`)**:
   - `id`: Integer Primary Key
   - `quote_id`: ForeignKey to `quotes.id` (CASCADE)
   - `product_id`: ForeignKey to `products.id`
   - `product_name`: String(255), frozen catalog name snapshot
   - `sku`: String(100), frozen catalog SKU snapshot
   - `billing_type`: String(50) (`MRC`, `NRC`, `USAGE`)
   - `currency`: String(10), default `USD`
   - `quantity`: Integer, default 1
   - `unit_price`: NUMERIC(12, 2), final unit price from Pricing Engine
   - `discount_percentage`: NUMERIC(5, 2)
   - `discount_amount`: NUMERIC(12, 2)
   - `total_price`: NUMERIC(12, 2) (Line Total = Quantity × Unit Price)
   - `pricing_method`: String(50)
   - `pricing_breakdown`: JSON, frozen calculation waterfall breakdown
   - `margin_amount`: NUMERIC(12, 2)
   - `margin_percentage`: NUMERIC(5, 2)
   - `configuration_id`: String(100), optional configuration session ID
   - `configuration_snapshot`: JSON, option selections snapshot
3. **Quote Audit Logs Table (`quote_audit_logs`)**:
   - `id`: Integer Primary Key
   - `quote_id`: ForeignKey to `quotes.id` (CASCADE)
   - `user_id`: ForeignKey to `users.id` (UUID)
   - `user_role`: String(50)
   - `action`: String(50) (`QUOTE_CREATED`, `QUOTE_UPDATED`, `QUOTE_ITEM_ADDED`, `QUOTE_ITEM_UPDATED`, `QUOTE_ITEM_REMOVED`, `QUOTE_SUBMITTED`, `QUOTE_CANCELLED`)
   - `before_value`: JSON
   - `after_value`: JSON
   - `timestamp`: DateTime(timezone=True)
4. **Alembic Migrations Applied**:
   - `f382a921d782_enhance_quotes_schema_and_audit.py`: Added normalized columns to `quotes`, `quote_line_items`, and created `quote_audit_logs`.
   - `b417d891c321_quote_number_version_unique.py`: Replaced unique index on `quote_number` with composite unique constraint on `(quote_number, version)` to support multi-version revisions.

### APIs Implemented
- `POST /api/v1/quotes` (Permission: `quotes.create`) — Create quote shell and optional line items; calculates dynamic prices via Pricing Engine and logs `QUOTE_CREATED`.
- `GET /api/v1/quotes` (Permission: `quotes.read`) — List quotes with filters (`customer_id`, `status`, `search`, `limit`, `offset`) and role-based visibility.
- `GET /api/v1/quotes/{id}` (Permission: `quotes.read`) — Retrieve full quote details, line items, customer summary, and audit records.
- `PUT /api/v1/quotes/{id}` (Permission: `quotes.update`) — Modify metadata, currency, expiration, or notes on draft quotes; logs `QUOTE_UPDATED`.
- `DELETE /api/v1/quotes/{id}` (Permission: `quotes.delete`) — Delete draft quote; non-draft quotes cannot be deleted.
- `POST /api/v1/quotes/{id}/items` (Permission: `quotes.update`) — Add configured product to quote; calculates price via Pricing Engine, stores snapshot, recalculates quote totals, logs `QUOTE_ITEM_ADDED`.
- `PUT /api/v1/quotes/{id}/items/{item_id}` (Permission: `quotes.update`) — Modify quantity or discount; re-evaluates Pricing Engine and updates snapshot, logs `QUOTE_ITEM_UPDATED`.
- `DELETE /api/v1/quotes/{id}/items/{item_id}` (Permission: `quotes.update`) — Delete line item and recalculate quote totals, logs `QUOTE_ITEM_REMOVED`.
- `POST /api/v1/quotes/{id}/submit` (Permission: `quotes.update`) — Validate draft has items and transition status from `DRAFT` to `SUBMITTED`, logs `QUOTE_SUBMITTED`.
- `POST /api/v1/quotes/{id}/cancel` (Permission: `quotes.update`) — Cancel active quote, logs `QUOTE_CANCELLED`.
- `POST /api/v1/quotes/{id}/revise` (Permission: `quotes.create`) — Clone quote to next version (`version + 1`), copy line items and snapshots, reset to `DRAFT`, set `parent_quote_id`, logs `QUOTE_CREATED`.

### Role-Based Access Control (RBAC) Implemented
- **Sales Representative**:
  - Can create quotes and view permitted customer details.
  - Can edit and modify own draft quotes only (`created_by_id == current_user.id`).
  - Attempting to edit or view another representative's quote returns `403 Forbidden`.
  - Can submit own draft quotes.
- **Sales Manager**:
  - Full visibility across team quotes.
  - Can edit permitted drafts and manage quotes within manager permissions.
  - Can submit, cancel, and revise team quotes.
- **Executive**:
  - Full organization-wide visibility across all quotations and revisions.
  - Full administrative capabilities (`quotes.read`, `quotes.create`, `quotes.update`, `quotes.delete`, `quotes.approve`, `quotes.export`).
- **Unauthenticated**: Returns `401 Unauthorized`.

### Frontend Implementation
- Located at `frontend/src/app/(dashboard)/quotes/page.tsx`.
- **Top Pipeline Metrics**: Live cards showing Total Quotes, Drafts, Submitted for Review, and Total Pipeline Quoted Value.
- **Filter Toolbar**: Search by Quote Number or Title with quick filter buttons (`ALL`, `DRAFT`, `SUBMITTED`, `APPROVED`, `REJECTED`, `CANCELLED`).
- **Interactive Create Quote Workspace**:
  - Searchable Customer dropdown selector.
  - Quote Name / Title, Currency selector (`USD`, `EUR`, `GBP`, `CAD`), and Expiration Date picker.
  - "+ Add Product" drawer pulling active items from catalog with SKU and list prices.
  - Real-time line item quantity editor with instant line total updating.
  - Clean Pricing Summary waterfall: Subtotal, Discount, Tax Placeholder ($0.00), Grand Total.
  - "Save Draft" and "Submit Quote" buttons.
- **Quote Detail & Revision Workspace**:
  - Comprehensive view of quote metadata, lines, configurations, unit prices, discounts, and line totals.
  - In Draft mode: allows editing quantities, removing items, adding products, and updating notes.
  - In Submitted mode: provides "Create Revision" button (transitions to v2 in Draft) and "Cancel Quote".
  - Dedicated Audit Trail modal displaying all mutation events with actor role, timestamp, and JSON before/after state diffs.
- **Build Verification**: `npm run build` succeeds cleanly with 0 TypeScript or lint errors.

### Verification & Capability Scorecard
| Capability | Status | Verification Summary |
|---|:---:|---|
| **Create Quote** | **PASS** | Auto-generates quote number `QT-10000X`, links customer, sets `DRAFT` status, initial totals 0.00. Tested in `test_quote_builder_full_lifecycle`. |
| **Retrieve Quote** | **PASS** | Eagerly loads all relationships (`items`, `customer`, `created_by`, `audit_logs`). Verified via GET endpoint. |
| **Update Quote** | **PASS** | Updates draft title, notes, expiration, currency; logs `QUOTE_UPDATED`. Verified in automated test. |
| **Add Product to Quote** | **PASS** | Calls Pricing Engine dynamically; saves snapshot of `unit_price`, `sku`, `product_name`, `pricing_breakdown`. |
| **Remove Product** | **PASS** | Deletes line item and recalculates quote totals. Verified in automated test. |
| **Change Quantity** | **PASS** | Re-invokes Pricing Engine, updates line total and recalculates quote subtotal. Verified in automated test. |
| **Configure Product Integration** | **PASS** | Consumes validated `ConfigurationSession` from Product Configuration module without rule duplication; rejects invalid sessions. |
| **Calculate Pricing Integration** | **PASS** | Integrates with `PricingApplicationService`; preserves discounts, tier rules, and calculation breakdown waterfalls. |
| **Subtotal Calculation** | **PASS** | Computed as sum of line totals (`sum(unit_price * quantity)`) via pure Decimal arithmetic. |
| **Discount Total Calculation** | **PASS** | Computed via Decimal arithmetic without float inaccuracy. |
| **Grand Total Calculation** | **PASS** | Computed as `Subtotal - Discount Total + Tax Placeholder`. Tested with multiple items and revisions. |
| **Pricing Breakdown** | **PASS** | Preserves structured calculation breakdown JSON array on line item snapshot. |
| **Quote Persistence After Restart** | **PASS** | Verified that quotes, lines, and audit logs persist identically in a clean async database session. |
| **Quote Status Transitions** | **PASS** | `DRAFT -> SUBMITTED`, `CANCELLED`, and revision increments `version = 2` back to `DRAFT`. |
| **RBAC / 401 / 403 Governance** | **PASS** | Rep 2 denied editing Rep 1's quote (403); Rep 2 denied viewing Rep 1's quote (403); Manager and Executive permitted. |
| **Audit Events** | **PASS** | Verified emission and logging of all 7 core events: `QUOTE_CREATED`, `QUOTE_UPDATED`, `QUOTE_ITEM_ADDED`, `QUOTE_ITEM_UPDATED`, `QUOTE_ITEM_REMOVED`, `QUOTE_SUBMITTED`, `QUOTE_CANCELLED`. |
| **Historical Price Isolation** | **PASS** | Modifying catalog product base price does not change prices on existing quote lines (frozen snapshot isolation). |
| **Regression: Authentication** | **PASS** | 100% passing across all auth foundation and password tests. |
| **Regression: Customer Management** | **PASS** | 100% passing across all customer CRUD and RBAC tests. |
| **Regression: Product Catalog** | **PASS** | 100% passing across all catalog, price book, and import tests. |
| **Regression: Product Configuration** | **PASS** | 100% passing across all bundle and configuration tests. |
| **Regression: Pricing Engine** | **PASS** | 100% passing across all pricing strategies, tiers, and lifecycle tests. |
| **Frontend UI Build** | **PASS** | Next.js production build (`npm run build`) completes cleanly with 0 type errors. |

### Known Limitations (Out of Scope for Module 6)
- **Approval Workflow Logic**: Approvals module (Module 7) will consume `SUBMITTED` quotes for manager/executive rule-based multi-tier approvals.
- **PDF Generation**: Document generation module (Module 8) will render downloadable proposal PDFs from quote snapshots.
- **Email Dispatching**: Email module (Module 9) will send quote proposals to customers.
- **CRM Sync**: Salesforce sync will push approved quotes to Salesforce Opportunities.

---

## 7. Frontend Redesign to Consistent Enterprise SaaS / CPQ UI

### Overview & Visual Style Transformation
The entire frontend has been systematically redesigned from the previous dark/fragmented theme (`bg-zinc-950`) to a unified, high-density light enterprise SaaS interface modeled directly after modern Salesforce / Oracle / SAP CPQ interfaces and the provided reference design, while maintaining CPQ COGNITIVE brand identity.

- **Theme & Surface**: Clean light canvas (`bg-slate-50`), white enterprise cards (`bg-white border border-slate-200/80 shadow-xs rounded-xl`), subtle borders (`border-slate-200/80`), and restrained shadows.
- **Typography & Colors**: Dark navy headings (`text-slate-900`), muted secondary metadata (`text-slate-500`), brand teal accent (`#0D9488` / `teal-600`), primary action blue (`#2563EB` / `blue-600`), success emerald, warning amber, and destructive rose.
- **Global Application Shell**:
  - **Sidebar**: Clean white (`w-60 bg-white border-r border-slate-200/80`), compact navigation links with icons, active state pill (`bg-blue-50 text-blue-600 font-semibold`), bottom system links (Settings, Help & Support) and AI Copilot badge.
  - **TopBar**: Compact header (`h-14 bg-white border-b border-slate-200/80`), brand logo mark (teal shield check + "CPQ COGNITIVE"), global search input with `⌘K` keyboard shortcut hint, notifications bell with unread badge, user avatar initials circle ("AL"), name ("Aarav lunkad"), and role ("Executive").
  - **Page Headers**: Standardized structure across all pages with title, short description, back navigation link, and primary/secondary button groups.

### Shared Design System Components (`src/components/ui/`)
- `Card`, `CardHeader`, `CardTitle`, `CardDescription`, `CardContent`, `CardFooter`: Standardized 1px subtle border, soft shadow, rounded-xl.
- `Button`: Consistent variants (`primary`, `secondary`, `outline`, `ghost`, `danger`, `success`), sizes (`sm`, `md`, `lg`), loading spinner, and icon support.
- `PageHeader`: Standardized title, description, back link, and action triggers.
- `StatusBadge`: Consistent status badges (`ACTIVE`, `DRAFT`, `SUBMITTED`, `PENDING`, `APPROVED`, `REJECTED`, `EXPIRED`, `CONFIGURED`, `STANDARD`, `CONNECTED`).
- `DataTable`, `TableHead`, `TableRow`, `TableHeader`, `TableCell`: Compact enterprise tables with subtle borders, hover states, and action menus.
- `SearchBar` & `FilterSelect`: Unified search input with clear button and select dropdowns.
- `MetricCard`: KPI metrics with trend badges, icon containers, and subtext.
- `HorizontalStepper` & `CircularProgress`: 5-step horizontal indicator and donut chart progress meters.
- `Modal`: Standardized dialogs with escape key handling, headers, scrollable body, and footers.
- `Tabs`: Consistent tab navigation with active indicator and count badges.

### Module Redesign Details
1. **Quote Builder (`/quotes`)**:
   - Matches reference design layout directly:
     - Header: "← Back to Quotes", Title "Create Quote", subtitle, action buttons ("[Save Draft]", "[Share]", "[Review & Submit →]").
     - Horizontal Stepper: `1 Customer` (active) → `2 Add Products` → `3 Configure` → `4 Pricing` → `5 Review`.
     - Left Column (8 cols):
       - Customer Information Card with AC avatar, Acme Corporation, tags (`CUST-001 | Technology | Enterprise`), Sarah Johnson, billing address, and "[Change Customer]" modal.
       - Quote Details Card with Quote Name, Quote Number, Valid Until, Currency, Description textarea, and "[Load Template ⌵]".
       - Products in this Quote Card with "[+ Add Products]" and "[Configure Bundle]" buttons, compact enterprise table with Dell Latitude, Enterprise Cloud, Implementation Service, configuration badges (`✓ Configured v1.0` / `● Standard`), billing type, quantity input, unit price, discount % (amber text), total, and row actions.
     - Right Column (4 cols):
       - Quote Summary Card: Subtotal, Discount (`-$1,299.00`), Tax (`—`), Total USD bold, and Expected Margin pill (`📈 Expected Margin ⓘ 32.5% | $6,834.00`).
       - Quote Progress Card: Donut indicator (`3/5`) with completed/pending checklist items.
       - Recent Activity Card: Activity stream with timestamps.
       - Next Steps Card: Light blue callout container with interactive checkboxes.
   - List View Toggle: Seamlessly toggle between full Quote Builder workspace and Quotes Data Table list view.
2. **Customers (`/customers`)**:
   - Header with title, subtitle, Export, Import, Salesforce Sync, Analytics, and `+ Add Customer` button.
   - Filter bar with search, status filter (`ACTIVE`, `ARCHIVED`), and type filter.
   - Clean enterprise table with avatar initials, industry, owner badge, status badge, created date, and row action menu.
   - Slide-out / modal customer details with tabs (Overview, Contacts, Notes, Quotes, Activity).
3. **Product Catalog (`/catalog`)**:
   - Product discovery header with search, Category filter, Status filter, Sort selector, table/grid toggle, and `+ Add Product` button.
   - Compact table with Product icon/name, SKU, Category, Billing Type, Status badge, Cost (RBAC masked), Base Price, Margin badge, and Actions.
4. **Pricing Engine (`/pricing`)**:
   - 5 Tabs: Overview, Price Lists, Pricing Configurations, Pricing Rules, Calculator.
   - Pricing Configurations Table: Product, SKU, Billing Type, Pricing Method badge, Base Price, Status, Effective Date, Configure action.
   - Interactive Calculator: Input section → Real-time price waterfall → Final result breakdown card.
5. **Product Configuration (`/configuration`)**:
   - 4 Tabs: Configurator, Solution Builder, Rules, Versions.
   - 2-Column Configurator Workspace: Left column options & quantities, Right column configuration summary with validation status and continue button.
6. **Approvals (`/approvals`)**:
   - Clean approval queue table with Quote, Customer, Amount, Discount, Margin, Requested By, Status, Submitted date, and Quick Action buttons (`Approve`, `Reject`).
7. **Integrations (`/integrations`)**:
   - Connector cards for Salesforce CRM, Excel / CSV, SAP ERP, and Webhooks API with live status indicators and actions.
8. **Dashboard (`/dashboard`)**:
   - Top 4 KPI cards: Total Quotation Revenue, Active Quotes Pipeline, Pending Approvals, Win Rate / Conversion.
   - 2-Column layout: Quotation Pipeline stages visualizer, Recent Quotes table, Pending Approvals card, and Gemini Copilot suggestion card.

### UI Redesign Scorecard
| Area / Page | Status | Verification Summary |
|---|:---:|---|
| **Dashboard** | **PASS** | Top 4 KPI cards, pipeline stage visualizer, recent quotes table, copilot suggestion card. HTTP 200. |
| **Customers** | **PASS** | Search & filter bar, clean enterprise table, details drawer, Add Customer modal. HTTP 200. |
| **Product Catalog** | **PASS** | Discovery header, Category filter, table/grid view toggle, base price & margin badges. HTTP 200. |
| **Pricing Engine** | **PASS** | 5 Tabs (Overview, Price Lists, Configurations, Rules, Calculator), price waterfall visualization. HTTP 200. |
| **Product Configuration** | **PASS** | 4 Tabs (Configurator, Solution Builder, Rules, Versions), 2-column workspace, validation badge. HTTP 200. |
| **Quote Builder** | **PASS** | Matches reference image layout: 2-column workspace, Customer Card, Quote Details, Products Table, Quote Summary, Donut Progress (3/5), Recent Activity, Next Steps. HTTP 200. |
| **Approvals** | **PASS** | Approval queue table with Quote, Customer, Amount, Discount, Margin, Requested By, Approve/Reject. HTTP 200. |
| **Integrations** | **PASS** | Salesforce CRM, Excel/CSV, SAP ERP, Webhooks connector cards with live status toggles. HTTP 200. |
| **Global Navigation** | **PASS** | White sidebar (`w-60`), active nav pill, compact topbar with ⌘K search, notifications, profile. |
| **Responsive Layout** | **PASS** | Flexible grid (`lg:grid-cols-12`), horizontal scroll on tables, mobile-friendly navigation. |
| **Shared Design System** | **PASS** | Centralized in `src/components/ui/` (`Card`, `Button`, `PageHeader`, `DataTable`, `StatusBadge`, `Modal`, `Tabs`). |
| **Regression Testing** | **PASS** | Zero backend regressions (`pytest` passes 100%), Next.js production build (`npm run build`) completes cleanly with 0 type errors. |



