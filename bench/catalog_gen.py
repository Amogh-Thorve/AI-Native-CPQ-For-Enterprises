"""
Synthetic CPQ-Bench catalog.

`plan()` is pure and deterministic: the same (n_products, seed) always gives the same plan.
`generate()` persists a plan idempotently: every row is looked up by its natural key first and skipped if present.
Everything is labelled synthetic and keyed with the BENCH- prefix, so it never touches real rows.
"""
import random
import uuid
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Dict, List, Optional, Tuple

from sqlalchemy import func, select

from backend.app.core.security import get_password_hash
from backend.app.domains.auth.models import Role, User
from backend.app.domains.catalog.models import Category, PriceBook, PriceBookEntry, Product
from backend.app.domains.configuration.models import (
    Bundle, BundleComponent, ConfigurationRule, ProductConfigurationGroup, ProductConfigurationOption,
)
from backend.app.domains.customer.models import Customer, CustomerAddress
from backend.app.domains.pricing.models import ProductPricingSetting, ProductPricingTier
from backend.app.domains.tax.models import TaxRate

PREFIX = "BENCH-"
SYNTHETIC = "Synthetic CPQ-Bench data."
BENCH_PASSWORD = "BenchPass123!"
BENCH_COUNTRY = "Benchland"
BENCH_TAX_NAME = f"{PREFIX}VAT"
BENCH_TAX_RATE = Decimal("8.00")
ROLES = ["Administrator", "Sales Manager", "Sales Representative", "Executive", "Viewer"]

# (pricing_method, tiered_mode), assigned round-robin so every method is covered.
METHODS: List[Tuple[str, Optional[str]]] = [
    ("STANDARD", None),
    ("LINE_DISCOUNT", None),
    ("TIERED", "VOLUME"),
    ("TIERED", "CUMULATIVE"),
    ("BLOCK", None),
    ("COST_PLUS_MARKUP", None),
]
CATEGORY_COUNT = 12
CUSTOMER_COUNT = 20
BUNDLE_COUNT = 10
FILLER_OPTIONS = 8
FILLER_RULES = 16

Ref = Tuple[int, int]  # (group index, option index) inside one product


def _money(value) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def sku_for(i: int) -> str:
    return f"{PREFIX}P{i + 1:04d}"


def role_email(role: str) -> str:
    return f"bench-{role.lower().replace(' ', '-')}@bench-cpq.com"


@dataclass
class TierPlan:
    min_quantity: int
    max_quantity: Optional[int]
    price: Decimal
    mode: Optional[str]


@dataclass
class GroupPlan:
    name: str
    selection_type: str
    required: bool
    options: List[str]


@dataclass
class ProductPlan:
    index: int
    sku: str
    name: str
    category: str
    base_price: Decimal
    cost_price: Decimal
    billing_type: str
    method: str
    tiered_mode: Optional[str]
    markup_percent: Decimal
    tiers: List[TierPlan] = field(default_factory=list)
    groups: List[GroupPlan] = field(default_factory=list)
    rules: List[Tuple[str, Ref, Ref]] = field(default_factory=list)  # (REQUIRES|EXCLUDES, source, target)


@dataclass
class Plan:
    seed: int
    products: List[ProductPlan]
    categories: List[str]
    bundles: List[Tuple[str, List[Tuple[str, bool, int, Optional[int], int]]]]  # sku, [(product sku, required, min, max, default)]
    price_books: Dict[str, List[Tuple[str, Decimal]]]
    customers: List[Tuple[str, str, str]]  # number, name, country

    @property
    def rule_count(self) -> int:
        return sum(len(p.rules) for p in self.products)


def _tiers(rng: random.Random, method: str, mode: Optional[str], base: Decimal) -> List[TierPlan]:
    if method == "TIERED":
        return [
            TierPlan(1, 9, base, mode),
            TierPlan(10, 49, _money(base * Decimal("0.90")), mode),
            TierPlan(50, None, _money(base * Decimal("0.80")), mode),
        ]
    if method == "BLOCK":
        return [
            TierPlan(1, 10, _money(base * 8), None),
            TierPlan(11, 50, _money(base * 30), None),
            TierPlan(51, None, _money(base * 60), None),
        ]
    return []


def _configuration(rng: random.Random, product: ProductPlan) -> None:
    product.groups = [
        GroupPlan("Plan", "SINGLE_SELECT", True, ["Basic", "Standard", "Premium"]),
        GroupPlan("Add-ons", "MULTI_SELECT", False, ["Support", "Backup", "Analytics"]),
        GroupPlan("Extras", "MULTI_SELECT", False, [f"Extra {n}" for n in range(1, FILLER_OPTIONS + 1)]),
    ]
    # Fixed spine, so tasks can rely on it: Premium needs Support, Basic cannot have Analytics.
    product.rules = [("REQUIRES", (0, 2), (1, 0)), ("EXCLUDES", (0, 0), (1, 2))]
    seen = set()
    while len(seen) < FILLER_RULES:
        a, b = rng.sample(range(FILLER_OPTIONS), 2)
        if (a, b) in seen or (b, a) in seen:
            continue
        seen.add((a, b))
        product.rules.append((rng.choice(["REQUIRES", "EXCLUDES"]), (2, a), (2, b)))


def plan(n_products: int = 300, seed: int = 1234) -> Plan:
    rng = random.Random(seed)
    categories = [f"{PREFIX}Cat-{c + 1:02d}" for c in range(CATEGORY_COUNT)]
    products: List[ProductPlan] = []
    for i in range(n_products):
        method, mode = METHODS[i % len(METHODS)]
        base = _money(Decimal(rng.randint(5_000, 2_000_000)) / 100)
        cost = _money(base * Decimal(str(round(rng.uniform(0.40, 0.80), 2))))
        p = ProductPlan(
            index=i, sku=sku_for(i), name=f"{PREFIX}Product {i + 1:04d} (synthetic)",
            category=categories[i % CATEGORY_COUNT], base_price=base, cost_price=cost,
            billing_type="MRC" if i % 3 else "NRC", method=method, tiered_mode=mode,
            markup_percent=_money(rng.randint(15, 60)) if method == "COST_PLUS_MARKUP" else Decimal("0.00"),
        )
        p.tiers = _tiers(rng, method, mode, base)
        if i % 5 < 2:
            _configuration(rng, p)
        products.append(p)

    bundles = []
    for b in range(BUNDLE_COUNT):
        picks = rng.sample(range(n_products), min(3, n_products))
        comps = [(sku_for(k), n == 0, 1, 10, 1) for n, k in enumerate(picks)]
        bundles.append((f"{PREFIX}BUN-{b + 1:03d}", comps))

    price_books = {}
    for name in (f"{PREFIX}PB-Partner", f"{PREFIX}PB-Enterprise"):
        entries = []
        for k in rng.sample(range(n_products), max(1, n_products // 5)):
            entries.append((sku_for(k), _money(products[k].base_price * Decimal(str(round(rng.uniform(0.85, 0.95), 2))))))
        price_books[name] = entries

    customers = []
    for c in range(CUSTOMER_COUNT):
        customers.append((f"{PREFIX}C{c + 1:03d}", f"{PREFIX}Customer {c + 1:03d} (synthetic)", BENCH_COUNTRY if c < 10 else "Nowhere"))
    return Plan(seed, products, categories, bundles, price_books, customers)


@dataclass
class GenReport:
    counts: Dict[str, int]
    product_ids: Dict[str, int]
    customer_ids: Dict[str, int]
    user_ids: Dict[str, uuid.UUID]
    price_book_ids: Dict[str, int]
    rule_count: int


async def _ids(db, model, key_col, prefix_col=None) -> Dict[str, int]:
    rows = (await db.execute(select(key_col, model.id).where(key_col.like(f"{PREFIX}%")))).all()
    return {k: i for k, i in rows}


async def _count(db, model, col) -> int:
    return (await db.execute(select(func.count()).select_from(model).where(col.like(f"{PREFIX}%")))).scalar_one()


async def generate(db, n_products: int = 300, seed: int = 1234) -> GenReport:
    """Persists the plan. Safe to call repeatedly: existing BENCH- rows are left as they are."""
    pl = plan(n_products, seed)

    roles = {r.name: r for r in (await db.execute(select(Role).where(Role.name.in_(ROLES)))).scalars()}
    missing = [r for r in ROLES if r not in roles]
    if missing:
        raise RuntimeError(f"Roles missing from the database: {missing}. Run scripts/seed_dev.py first.")

    # Users: one per role.
    for role in ROLES:
        email = role_email(role)
        if (await db.execute(select(User).where(User.email == email))).scalars().first() is None:
            user = User(
                email=email, hashed_password=get_password_hash(BENCH_PASSWORD), first_name="Bench",
                last_name=role, username=email.split("@")[0], is_active=True, is_verified=True,
            )
            user.roles = [roles[role]]
            db.add(user)
    await db.flush()

    # Categories.
    cat_ids: Dict[str, int] = await _ids(db, Category, Category.name)
    for name in pl.categories:
        if name not in cat_ids:
            c = Category(name=name, description=SYNTHETIC)
            db.add(c)
            await db.flush()
            cat_ids[name] = c.id

    # Products with pricing settings, tiers and configuration.
    existing = await _ids(db, Product, Product.sku)
    for p in pl.products:
        if p.sku in existing:
            continue
        prod = Product(
            sku=p.sku, name=p.name, description=SYNTHETIC, base_price=p.base_price, cost_price=p.cost_price,
            currency="USD", is_active=True, billing_type=p.billing_type, category_id=cat_ids[p.category],
        )
        db.add(prod)
        await db.flush()
        existing[p.sku] = prod.id
        db.add(ProductPricingSetting(
            product_id=prod.id, pricing_method=p.method, markup_percent=p.markup_percent,
            status="ACTIVE", discount_percent=Decimal("0.00"),
        ))
        for order, t in enumerate(p.tiers, start=1):
            db.add(ProductPricingTier(
                product_id=prod.id, pricing_method=p.method, tiered_mode=t.mode, min_quantity=t.min_quantity,
                max_quantity=t.max_quantity, price=t.price, display_order=order, is_active=True,
            ))
        option_ids: Dict[Ref, int] = {}
        for gi, g in enumerate(p.groups):
            group = ProductConfigurationGroup(
                product_id=prod.id, name=g.name, description=SYNTHETIC, required=g.required,
                selection_type=g.selection_type, display_order=gi, is_active=True,
            )
            db.add(group)
            await db.flush()
            for oi, name in enumerate(g.options):
                opt = ProductConfigurationOption(
                    group_id=group.id, name=name, description=SYNTHETIC, value=name.lower().replace(" ", "-"),
                    display_order=oi, is_active=True,
                )
                db.add(opt)
                await db.flush()
                option_ids[(gi, oi)] = opt.id
        for rule_type, src, tgt in p.rules:
            db.add(ConfigurationRule(
                product_id=prod.id, rule_type=rule_type, source_option_id=option_ids[src],
                target_option_id=option_ids[tgt], message=f"{SYNTHETIC} {rule_type} rule", is_active=True,
            ))
    await db.flush()

    # Bundles.
    bundle_ids = await _ids(db, Bundle, Bundle.sku)
    for sku, comps in pl.bundles:
        if sku in bundle_ids:
            continue
        bundle = Bundle(name=f"{sku} (synthetic)", description=SYNTHETIC, sku=sku, is_active=True)
        db.add(bundle)
        await db.flush()
        for order, (psku, required, lo, hi, default) in enumerate(comps):
            db.add(BundleComponent(
                bundle_id=bundle.id, product_id=existing[psku], required=required, default_selected=True,
                min_quantity=lo, max_quantity=hi, default_quantity=default, display_order=order, is_active=True,
            ))
    await db.flush()

    # Price books. Deliberately not flagged standard, so they never change real price resolution.
    pb_ids = await _ids(db, PriceBook, PriceBook.name)
    for name, entries in pl.price_books.items():
        if name in pb_ids:
            continue
        book = PriceBook(name=name, description=SYNTHETIC, is_active=True, is_standard=False)
        db.add(book)
        await db.flush()
        pb_ids[name] = book.id
        for psku, price in entries:
            db.add(PriceBookEntry(price_book_id=book.id, product_id=existing[psku], custom_price=price, is_active=True))
    await db.flush()

    # Tax rate and customers (each with a primary address).
    if (await db.execute(select(TaxRate).where(TaxRate.name == BENCH_TAX_NAME))).scalars().first() is None:
        db.add(TaxRate(name=BENCH_TAX_NAME, country=BENCH_COUNTRY, region=None, rate_percent=BENCH_TAX_RATE,
                       is_default=False, is_active=True))
    rep_id = (await db.execute(select(User.id).where(User.email == role_email("Sales Representative")))).scalar_one()
    # The tool layer scopes a Sales Representative to customers they own in their own tenant.
    existing_customers = (await db.execute(
        select(Customer).where(Customer.customer_number.like(f"{PREFIX}%"))
    )).scalars().all()
    cust_ids = {}
    for cust in existing_customers:
        cust_ids[cust.customer_number] = cust.id
        if cust.tenant_id != rep_id or cust.owner_id != rep_id:
            cust.tenant_id = rep_id
            cust.owner_id = rep_id
    for number, name, country in pl.customers:
        if number in cust_ids:
            continue
        cust = Customer(
            tenant_id=rep_id, owner_id=rep_id, customer_number=number, legal_name=name, display_name=name,
            customer_type="BUSINESS", status="ACTIVE", currency="USD", notes=SYNTHETIC,
        )
        db.add(cust)
        await db.flush()
        cust_ids[number] = cust.id
        db.add(CustomerAddress(
            customer_id=cust.id, address_type="BILLING", line1="1 Synthetic Way", city="Benchtown",
            state="BN", postal_code="00000", country=country, is_primary=True,
        ))
    await db.commit()

    users = {
        r: (await db.execute(select(User.id).where(User.email == role_email(r)))).scalar_one() for r in ROLES
    }
    counts = {
        "products": await _count(db, Product, Product.sku),
        "categories": await _count(db, Category, Category.name),
        "bundles": await _count(db, Bundle, Bundle.sku),
        "price_books": await _count(db, PriceBook, PriceBook.name),
        "customers": len(cust_ids),
        "users": len(users),
        "rules": (await db.execute(
            select(func.count()).select_from(ConfigurationRule).join(Product, Product.id == ConfigurationRule.product_id)
            .where(Product.sku.like(f"{PREFIX}%"))
        )).scalar_one(),
    }
    return GenReport(
        counts=counts, product_ids=await _ids(db, Product, Product.sku), customer_ids=cust_ids,
        user_ids=users, price_book_ids=pb_ids, rule_count=counts["rules"],
    )
