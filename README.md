# AI-Native Enterprise CPQ Platform

A production-quality, modular monolith **Configure, Price, Quote** platform built with Domain-Driven Design, Google Gemini AI-powered workflows, and Salesforce CRM integration.

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | Python 3.12, FastAPI, SQLAlchemy 2.0 (Async), Pydantic v2 |
| **Database** | PostgreSQL 16 |
| **Migrations** | Alembic |
| **Authentication** | JWT (HS256) + bcrypt |
| **Frontend** | Next.js 16, React 19, TypeScript, Tailwind CSS v4 |
| **State Management** | TanStack Query v5 |
| **Forms** | React Hook Form + Zod v4 |
| **AI** | Google Gemini API (`google-genai`) |
| **Import/Export** | openpyxl (Excel), CSV |

---

## Module Status

| # | Domain | Backend | Frontend | Notes |
|---|---|---|---|---|
| 1 | **Authentication & RBAC** | ✅ Complete | ✅ Complete | JWT, roles, forgot/reset password |
| 2 | **Customer Management** | ✅ Complete | ✅ Complete | Contacts, ownership, RBAC |
| 3 | **Product Catalog** | ✅ Complete | ✅ Complete | Price books, Excel import, cost & margins |
| 4 | **Pricing Engine** | ✅ Complete | ✅ Complete | 5 methods (Standard, Discount, Tiered Volume/Cumulative, Block, Cost+Markup), lifecycle, effective dates, Decimal math, RBAC masking |
| 5 | **Product Configuration** | ✅ Complete | ✅ Complete | Attributes, options, constraints, bundles, validation wizard, versioning |
| 6 | **Quote Builder** | 🔲 Planned | 🔲 Planned | Quote lifecycle, revisions |
| 7 | **Approval Workflow** | 🔲 Planned | 🔲 Planned | Policies, multi-step approvals |
| 8 | **PDF Generation** | 🏗️ Scaffold | — | Document generation endpoint |
| 9 | **Email** | 🏗️ Scaffold | — | Email dispatcher |
| 10 | **AI Copilot** | 🏗️ Scaffold | — | Customer/quote summaries, draft emails |
| 11 | **Integrations** | 🏗️ Scaffold | — | CSV/Excel import, Salesforce sync |

---

## Prerequisites

- **Python** 3.12+
- **Node.js** 18+
- **Docker Desktop** (for PostgreSQL) — or a local PostgreSQL 16 installation

---

## Local Development Setup

> A fresh developer can reproduce the complete environment in ~5 minutes without any database dump.

### 1. Clone and configure environment

```bash
git clone https://github.com/your-org/cpq-pricing.git
cd cpq-pricing

# Copy the environment template and fill in your values
cp .env.example backend/.env
```

Edit `backend/.env` — at minimum, set `DATABASE_URL` and `JWT_SECRET`. See [`.env.example`](./.env.example) for all options.

---

### 2. Start PostgreSQL

```bash
# Option A — Docker (recommended)
docker compose up -d db

# Option B — Local PostgreSQL 16
createdb cpq_db
```

The Docker Compose service creates the `cpq_db` database with user `cpq_user` automatically.

---

### 3. Install all dependencies

```bash
# Install Python dependencies
pip install -r backend/requirements.txt

# Install Node dependencies
cd frontend && npm install && cd ..
```

Or use the Makefile shortcut:

```bash
make install
```

---

### 4. Run database migrations

```bash
cd backend && python -m alembic upgrade head && cd ..
```

Or:

```bash
make migrate
```

This creates all tables from scratch. No manual SQL required.

---

### 5. Seed the development environment

```bash
python scripts/seed_dev.py
```

This idempotently creates:
- All **permissions** and **roles** (Administrator, Sales Manager, Sales Rep, Executive, Viewer)
- **4 development user accounts** (one per role)
- **Product categories** and **14 DEV-\* catalog products** across Hardware, Software, Services, Accessories, and Bundles
- **3 development customers**

Running it multiple times is safe — it will never duplicate records.

#### Development Login Credentials

| Role | Email | Password |
|---|---|---|
| Administrator | admin@cpq.local | DevAdmin@2025! |
| Sales Manager | manager@cpq.local | DevManager@2025! |
| Sales Representative | rep@cpq.local | DevRep@2025! |
| Executive | executive@cpq.local | DevExec@2025! |

> **Security**: These credentials are for local development only. Never reuse them in staging or production.

#### Optional: Seed / clear catalog products only

```bash
# Seed only products and categories (subset of seed_dev.py)
python scripts/seed_products.py

# Clear only DEV-* prefixed products
python scripts/seed_products.py --clear
```

---

### 6. Start the backend API

```bash
python backend/run.py
# or
make backend
```

| URL | Description |
|---|---|
| http://localhost:8000/docs | Swagger UI (interactive) |
| http://localhost:8000/redoc | ReDoc documentation |
| http://localhost:8000/health | Health check |

---

### 7. Start the frontend

```bash
cd frontend && npm run dev
# or
make frontend
```

Frontend: **http://localhost:3000**

---

## Makefile Reference

```bash
make help        # Show all available commands
make install     # Install Python + Node dependencies
make db-up       # Start PostgreSQL via Docker Compose
make db-down     # Stop PostgreSQL container
make migrate     # Run all pending Alembic migrations
make rollback    # Roll back the last Alembic migration
make backend     # Start the FastAPI dev server
make frontend    # Start the Next.js dev server
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | ✅ | Async PostgreSQL URL (`postgresql+asyncpg://...`) |
| `JWT_SECRET` | ✅ | Random secret for signing JWTs (`openssl rand -hex 32`) |
| `JWT_ALGORITHM` | — | Signing algorithm, default `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | — | Token TTL in minutes, default `60` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | — | Refresh token TTL in days, default `30` |
| `GEMINI_API_KEY` | Optional | Required for AI Copilot features |
| `SALESFORCE_CLIENT_ID` | Optional | Required for Salesforce integration |
| `SALESFORCE_CLIENT_SECRET` | Optional | Required for Salesforce integration |
| `SALESFORCE_REDIRECT_URI` | Optional | OAuth callback URL |
| `ENVIRONMENT` | — | `LOCAL_DEV` \| `STAGING` \| `PRODUCTION`, default `LOCAL_DEV` |

---

## Project Structure

```
/
├── backend/
│   ├── app/
│   │   ├── core/              # Config, DB engine, security, exceptions
│   │   └── domains/           # 11 business domains (DDD Modular Monolith)
│   │       ├── auth/          # JWT auth, RBAC, roles & permissions
│   │       ├── customer/      # Customer & contact management
│   │       ├── catalog/       # Products, categories, price books
│   │       ├── pricing/       # Pricing rules & discount engine
│   │       ├── configuration/ # Product configurator & validation rules
│   │       ├── quotes/        # Quote lifecycle & revisions
│   │       ├── approval/      # Approval policies & workflow
│   │       ├── document/      # PDF quote generation
│   │       ├── email/         # Email dispatcher
│   │       ├── ai/            # Gemini AI copilot
│   │       └── integrations/  # CSV/Excel import, Salesforce sync
│   ├── alembic/               # Database migrations
│   ├── requirements.txt
│   └── run.py                 # Dev server entrypoint
├── frontend/                  # Next.js 16 application (App Router)
│   └── src/
│       ├── app/               # Route pages & layouts
│       ├── components/        # Shared UI components
│       └── types/             # TypeScript type definitions
├── scripts/
│   ├── seed_dev.py            # Full dev environment seeder (users, roles, products, customers)
│   └── seed_products.py       # Catalog-only seeder / cleaner
├── docker-compose.yml         # PostgreSQL 16 service
├── Makefile                   # Developer workflow shortcuts
├── .env.example               # Environment variable template
└── PROJECT_STATE.md           # Living implementation tracker
```

---

## API Overview

All endpoints are prefixed under `/api/v1`. Visit `/docs` for the full interactive Swagger UI.

| Domain | Key Endpoints |
|---|---|
| **Auth** | `POST /auth/register`, `POST /auth/login`, `GET /auth/me`, `POST /auth/forgot-password`, `POST /auth/reset-password` |
| **Customers** | `GET /customers`, `POST /customers`, `GET /customers/{id}`, `PUT /customers/{id}`, `DELETE /customers/{id}`, `POST /customers/{id}/contacts` |
| **Catalog** | `GET /products`, `POST /products`, `PATCH /products/{id}/archive`, `GET /categories`, `POST /price-books`, `POST /price-books/{id}/entries` |
| **Pricing** | `POST /pricing/calculate`, `GET /pricing/products`, `GET /pricing/products/{id}/configuration`, `POST /pricing/products/{id}/configuration`, `POST /pricing/products/{id}/configuration/activate`, `POST /pricing/products/{id}/configuration/deactivate`, `GET, POST, DELETE /pricing/products/{id}/tiers`, `GET, POST /pricing/rules`, `PUT, DELETE /pricing/rules/{id}` |
| **Configuration** | `POST /configuration/validate`, `GET /configuration/rules`, `POST /configuration/rules` |
| **Quotes** | `GET /quotes`, `POST /quotes`, `GET /quotes/{id}`, `PUT /quotes/{id}`, `POST /quotes/{id}/revise` |
| **Approvals** | `GET /approvals/policies`, `POST /approvals/submit`, `GET /approvals/pending`, `POST /approvals/requests/{id}/decide` |
| **Documents** | `POST /documents/generate`, `GET /documents/quote/{id}` |
| **Email** | `POST /emails/send`, `GET /emails/quote/{id}` |
| **AI Copilot** | `POST /ai/customer-summary`, `POST /ai/quote-summary`, `POST /ai/draft-email`, `POST /ai/recommendations` |
| **Integrations** | `POST /integrations/import/preview`, `POST /integrations/salesforce/connect`, `POST /integrations/salesforce/sync-quote/{id}`, `GET /integrations/logs` |

---

## Enterprise Pricing Engine

The Pricing Engine is a backend-authoritative calculation and governance system designed to separate **what can be sold** (Product Configuration) from **how much it costs** (Pricing Engine).

### Supported Pricing Methods

1. **STANDARD**: Base unit price lookup from product catalog.
   - Formula: `Unit Price = Product Base Price`, `Total = Unit Price × Quantity`.
2. **LINE_DISCOUNT**: Percentage-based discount.
   - Formula: `Discount Amount = Base Price × Discount % / 100`, `Final Unit Price = Base Price - Discount Amount`.
   - Strict validation: `0 <= Discount <= 100`.
3. **TIERED (VOLUME & CUMULATIVE)**:
   - **Volume Mode**: Total quantity determines the single applicable bracket tier; all units use that tier price.
   - **Cumulative Mode**: Slabs calculated progressively across each quantity tier bracket.
   - Contiguity validation: Prevents gaps, overlapping tiers, inverted quantities, or duplicate brackets.
4. **BLOCK**: Fixed price for an entire quantity bracket (not multiplied by quantity).
5. **COST_PLUS_MARKUP**: Markup on top of catalog cost.
   - Formula: `Selling Price = Cost × (1 + Markup % / 100)`.
   - Rejects negative cost or markup.

### Core Financial & Money Handling
- **Pure Decimal Arithmetic**: Python `Decimal` and PostgreSQL `NUMERIC(12, 2)` throughout to prevent floating-point rounding errors.
- **Preserved Billing Types**: `MRC` (Monthly Recurring Charge), `NRC` (Non-Recurring Charge), and `USAGE` are preserved across all calculation strategies.
- **Derived Financial Margins**:
  - `Margin Amount = Selling Price - Product Cost`
  - `Margin % = ((Selling Price - Product Cost) / Selling Price) × 100`
  - Zero Selling Price: Returns `margin_percentage = null` (preventing zero-division errors).
  - Negative Margins: Permitted and audited when selling price is below cost.
- **Calculation Waterfall**: Returns a transparent, structured breakdown of each step, applied tier, and intermediate price.

### Lifecycle & Governance
- **Configuration Lifecycle**: `DRAFT`, `ACTIVE`, `INACTIVE`, `ARCHIVED`. Live calculations reject draft or inactive configurations.
- **Effective Dating**: `effective_from` and `effective_until` time-windows prevent stale or expired pricing configurations from being used.
- **Manual Price Overrides**: Requires `pricing.override` permission and a mandatory `override_reason`. Logged as `PRICING_OVERRIDE_USED` in `pricing_audit_logs`.
- **Sensitive Data Isolation (RBAC Masking)**:
  - `pricing.cost.view`: Required to see `unit_cost` and `total_cost`.
  - `pricing.margin.view`: Required to see `margin_amount` and `margin_percentage`.
  - Missing permissions automatically mask fields as `null` on the backend API layer.

---

## Testing

Comprehensive test suites validate domain calculations, edge cases, RBAC, API routes, and persistence across server restarts.

```bash
# Run Pricing Engine domain tests (30 tests)
python -m pytest backend/app/domains/pricing/tests/ -v

# Run entire platform regression test suite (39 tests)
python -m pytest -W ignore -q

# Run frontend production build validation
cd frontend && npm run build
```

---

## Architecture & Design Principles

- **Domain-Driven Design (DDD)** — 11 isolated business domains, each owning its own models, schemas, services, and routes
- **Modular Monolith** — single FastAPI runtime with strict boundary enforcement; no direct cross-domain model imports
- **Backend-Authoritative Pricing** — frontend only requests calculations and displays results; all calculations use Decimal precision
- **No business logic in routes** — routes delegate entirely to services; services delegate to repositories
- **Interface abstraction** — services and repositories inherit from protocols/ABCs for testability and replaceability
- **Async-first** — SQLAlchemy async engine and async FastAPI handlers throughout
- **Type safety** — Pydantic v2 schemas on all API inputs and outputs
- **Centralized error handling** — all exceptions caught at the app level with consistent JSON error responses

