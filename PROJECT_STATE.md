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
- [x] 4. **Pricing Engine** (Folder/Placeholder created: Yes | Fully implemented: Yes | Standard, Line Discount, Tiered, Block & Cost+Markup methods, Admin UI & Contiguity validations & Alembic schema)--->✅
- [x] 5. **Product Configuration** (Folder/Placeholder created: Yes | Fully implemented: Yes | Phase 1, 2 & 3 complete: Attributes, Options, Single/Multi select, Requires & Excludes constraints, Product Bundles, Component constraints, real-time Bundle Validator, Guided Config UI Wizard, Admin Builder UI, Versioning & Lifecycle draft promotion, Structural Comparer, Traceable historical sessions, Audit Integration, E2E tests passed)--->✅
- [ ] 6. **Quote Builder** (Folder/Placeholder created: No | Fully implemented: No)
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
- **Pricing**: `/pricing/calculate` (POST), `/pricing/products` (GET), `/pricing/products/{id}/configuration` (GET, POST), `/pricing/products/{id}/tiers` (GET, POST, DELETE)
- **Configuration**: `/configuration/validate` (POST), `/configuration/rules` (GET, POST)
- **Quotes**: `/quotes/` (GET, POST), `/quotes/{quote_id}` (GET, PUT), `/quotes/{quote_id}/revise` (POST)
- **Approvals**: `/approvals/policies` (GET, POST), `/approvals/submit` (POST), `/approvals/pending` (GET), `/approvals/requests/{request_id}/decide` (POST)
- **Documents**: `/documents/generate` (POST), `/documents/quote/{quote_id}` (GET)
- **Email**: `/emails/send` (POST), `/emails/quote/{quote_id}` (GET)
- **AI**: `/ai/customer-summary` (POST), `/ai/quote-summary` (POST), `/ai/draft-email` (POST), `/ai/recommendations` (POST)
- **Integrations**: `/integrations/import/preview` (POST), `/integrations/salesforce/connect` (POST), `/integrations/salesforce/sync-quote/{quote_id}` (POST), `/integrations/logs` (GET)

---

## Pricing Module Details

### Implemented Pricing Methods
- **STANDARD**: List base unit price lookup.
- **LINE_DISCOUNT**: Standard price with percentage discounts applied.
- **TIERED (VOLUME)**: Tiers contiguous ranges where the total quantity determines a single matching tier's unit price.
- **TIERED (CUMULATIVE)**: Tiers contiguous ranges priced segment-by-segment progressively.
- **BLOCK**: Fixed charge corresponding to the matched quantity bracket.
- **COST_PLUS_MARKUP**: Markup calculation: `Selling Price = Cost * (1 + Markup / 100)`.

### Database Entities
- `ProductPricingTier` (Table: `product_pricing_tiers`): Persists bracket ranges (`min_quantity`, `max_quantity`) and prices/blocks.
- `ProductPricingSetting` (Table: `product_pricing_settings`): Persists chosen product pricing method and markup percentage.

### Pricing Settings Modal Improvements
- **Product Pricing Summary**: Compact layout displaying Base Price, Product Cost, Billing Type, and Current Margin %.
- **Pricing Method Selection**: Standardized labels for all five methods (Standard, Line Discount, Tiered, Block, Cost+Markup).
- **Dynamic Pricing Configuration**: Responsive panels rendering the matching inputs, helpers, examples, and rules for the selected pricing method. Enforces validation bounds on quantities, prices, markup, and discounts.
- **Live Price Preview**: Interactive preview with adjustable quantity invoking the backend Pricing Engine API on-the-fly via new custom schemas request fields (`custom_tiers` / `custom_markup_percent`).
- **Unsaved Changes Guard**: Auto-disabled "Save Configuration" button when no changes exist, combined with a "Discard unsaved pricing changes?" warning confirmation dialog upon Cancel/X action.
- **Existing Configuration Warning**: Warning indicator displayed if a user modifies an existing saved pricing method strategy.
- **Feedback System**: Custom responsive floating success/error toast feedback.

### Enterprise Access Control (RBAC) & Governance
- **Role-Based Permissions**: Granular permissions registered in auth registry (`pricing.calculate`, `pricing.config.view`, `pricing.config.update`, `pricing.config.deactivate`, `pricing.cost.view`, `pricing.margin.view`, `pricing.rule.create`, `pricing.rule.view`, `pricing.rule.update`, `pricing.rule.delete`).
- **Access Control Model**:
  - **Sales Representative**: View products, view calculated selling prices, use active pricing configs. Cost & margin fields are automatically nullified on the backend API layer. "Configure" buttons are hidden on the UI.
  - **Sales Manager**: View pricing configurations, view margins (without seeing cost prices). All editing inputs and "Save Configuration" buttons are disabled in view-only mode.
  - **Executive & Admin**: Full permissions to view costs/margins, edit configurations, manage dynamic pricing rules, activate/deactivate configs.
- **Audit Logging**: Added `PricingAuditLog` model capturing user UUID, user role, action type (`PRICING_CONFIGURATION_CREATED`, `PRICING_CONFIGURATION_UPDATED`, `PRICING_CONFIGURATION_DEACTIVATED`, `PRICING_RULE_CREATED`, etc.), pricing configuration ID, product ID, and `before_value` / `after_value` state diff snapshots.
- **Rules Administration**: Governance columns (`description`, `status` [DRAFT, ACTIVE, INACTIVE], `created_by`, `updated_by`) mapped to `PricingRule`. Admin endpoints (POST, GET, PUT, DELETE `/pricing/rules`) secured and fully audited.

### Future Work Roadmap
- **Customer-Specific Pricing**: Custom override matrices mapped to specific accounts.
- **Price Books**: Multiple standard/custom books with currency support.
- **Contract Pricing**: Customer agreements overriding global list prices.
- **Promotions**: Coupon codes, seasonal discounts, and automated discount triggers.
- **Bundle Pricing**: Special bundle configurations and package discounts.
- **AI Pricing Recommendations**: Automated suggestions based on historic quotes, win/loss rates, and margin constraints.

