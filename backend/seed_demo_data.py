"""
Demo Data Seeder for CPQ Platform Project Review.
Ensures idempotent creation and verification of:
1. Customer: Acme Corporation (Enterprise, Technology, Active)
2. Products: Dell Latitude 7440, Enterprise Cloud Subscription, Implementation Consulting Service
3. Product Configuration: Dell Latitude 7440 groups, options, and compatibility rules
4. Pricing Settings: Standard, Tiered Volume pricing, and pricing rules
5. Demo Quote: Q-2026-0001 'Acme IT Infrastructure Upgrade'
6. Demo User: Executive user with full permissions
"""
import sys
import os
import uuid
import asyncio
from decimal import Decimal
from datetime import datetime, timezone, timedelta

# Ensure project root is on sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from sqlalchemy import select
from backend.app.core.database import SessionLocal
from backend.app.core.security import get_password_hash
from backend.app.domains.auth.models import User, Role, UserRole
from backend.app.domains.customer.models import Customer, Contact, CustomerAddress, CustomerType, CustomerStatus, AddressType
from backend.app.domains.catalog.models import Product, Category, PriceBook, PriceBookEntry
from backend.app.domains.configuration.models import ProductConfigurationGroup, ProductConfigurationOption, ConfigurationRule, ConfigRuleType
from backend.app.domains.pricing.models import ProductPricingSetting, ProductPricingTier, PricingRule, PricingRuleType
from backend.app.domains.quotes.models import Quote, QuoteLineItem, QuoteStatus

async def seed_demo_data():
    async with SessionLocal() as db:
        try:
            print("=" * 60)
            print("SEEDING CPQ DEMO DATA FOR ACME CORPORATION SCENARIO")
            print("=" * 60)

            # ---------------------------------------------------------
            # 1. DEMO USER & ROLES
            # ---------------------------------------------------------
            print("\n[1/6] Verifying Demo User and Roles...")
            res = await db.execute(select(Role).where(Role.name == "Executive"))
            exec_role = res.scalar_one_or_none()
            if not exec_role:
                exec_role = Role(name="Executive", description="Executive leadership with organizational oversight")
                db.add(exec_role)
                await db.flush()

            res = await db.execute(select(Role).where(Role.name == "Administrator"))
            admin_role = res.scalar_one_or_none()
            if not admin_role:
                admin_role = Role(name="Administrator", description="System administrator")
                db.add(admin_role)
                await db.flush()

            res = await db.execute(select(Role).where(Role.name == "Sales Representative"))
            sales_rep_role = res.scalar_one_or_none()
            if not sales_rep_role:
                sales_rep_role = Role(name="Sales Representative", description="Sales representative")
                db.add(sales_rep_role)
                await db.flush()

            res = await db.execute(select(User).where(User.email == "aarav.lunkad@enterprise.com"))
            demo_user = res.scalar_one_or_none()
            if not demo_user:
                demo_user = User(
                    id=uuid.uuid4(),
                    email="aarav.lunkad@enterprise.com",
                    hashed_password=get_password_hash("Password123!"),
                    first_name="Aarav",
                    last_name="Lunkad",
                    is_active=True,
                    is_verified=True
                )
                db.add(demo_user)
                await db.flush()
                print(f"  Created demo user: {demo_user.email}")
            else:
                demo_user.hashed_password = get_password_hash("Password123!")
                demo_user.is_active = True
                await db.flush()
                print(f"  Updated demo user: {demo_user.email}")

            # Ensure demo user has Executive and Admin roles
            res = await db.execute(select(UserRole.role_id).where(UserRole.user_id == demo_user.id))
            existing_roles = set(res.scalars().all())
            if exec_role.id not in existing_roles:
                db.add(UserRole(user_id=demo_user.id, role_id=exec_role.id))
            if admin_role.id not in existing_roles:
                db.add(UserRole(user_id=demo_user.id, role_id=admin_role.id))
            await db.flush()

            # ---------------------------------------------------------
            # 2. DEMO CUSTOMER: ACME CORPORATION
            # ---------------------------------------------------------
            print("\n[2/6] Verifying Demo Customer (Acme Corporation)...")
            tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
            res = await db.execute(select(Customer).where(Customer.legal_name == "Acme Corporation"))
            acme = res.scalar_one_or_none()
            if not acme:
                acme = Customer(
                    tenant_id=tenant_id,
                    customer_number="DEV-CUST-001",
                    legal_name="Acme Corporation",
                    display_name="Acme Corp",
                    customer_type=CustomerType.BUSINESS.value,
                    industry="Technology",
                    website="https://acme.example.com",
                    email="sarah.johnson@acme.com",
                    phone="+1 (415) 555-0123",
                    status=CustomerStatus.ACTIVE.value,
                    currency="USD",
                    notes="Primary enterprise demo customer account for CPQ review.",
                    owner_id=demo_user.id
                )
                db.add(acme)
                await db.flush()
                print(f"  Created Customer: Acme Corporation (ID: {acme.id})")
            else:
                acme.customer_number = "DEV-CUST-001"
                acme.display_name = "Acme Corp"
                acme.industry = "Technology"
                acme.status = CustomerStatus.ACTIVE.value
                acme.email = "sarah.johnson@acme.com"
                acme.phone = "+1 (415) 555-0123"
                acme.currency = "USD"
                await db.flush()
                print(f"  Reusing existing Customer: Acme Corporation (ID: {acme.id})")

            # Contact: Sarah Johnson
            res = await db.execute(select(Contact).where(Contact.customer_id == acme.id, Contact.email == "sarah.johnson@acme.com"))
            contact = res.scalar_one_or_none()
            if not contact:
                contact = Contact(
                    customer_id=acme.id,
                    first_name="Sarah",
                    last_name="Johnson",
                    email="sarah.johnson@acme.com",
                    phone="+1 (415) 555-0123",
                    job_title="VP of Information Technology",
                    department="IT Infrastructure",
                    is_primary=True
                )
                db.add(contact)
                await db.flush()
                print(f"  Added primary contact: Sarah Johnson")

            # Address
            res = await db.execute(select(CustomerAddress).where(CustomerAddress.customer_id == acme.id))
            addr = res.scalar_one_or_none()
            if not addr:
                addr = CustomerAddress(
                    customer_id=acme.id,
                    address_type=AddressType.BILLING.value,
                    line1="123 Market Street, Suite 400",
                    city="San Francisco",
                    state="CA",
                    postal_code="94105",
                    country="USA",
                    is_primary=True
                )
                db.add(addr)
                await db.flush()
                print(f"  Added billing address: 123 Market St, San Francisco, CA")

            # ---------------------------------------------------------
            # 3. DEMO PRODUCTS & CATEGORIES
            # ---------------------------------------------------------
            print("\n[3/6] Verifying Demo Products...")
            res = await db.execute(select(Category).where(Category.name == "Hardware"))
            cat_hw = res.scalar_one_or_none()
            if not cat_hw:
                cat_hw = Category(name="Hardware", description="Enterprise computing systems, laptops, and peripherals")
                db.add(cat_hw)
                await db.flush()

            res = await db.execute(select(Category).where(Category.name == "Cloud Services"))
            cat_cloud = res.scalar_one_or_none()
            if not cat_cloud:
                cat_cloud = Category(name="Cloud Services", description="Cloud infrastructure and subscription licenses")
                db.add(cat_cloud)
                await db.flush()

            res = await db.execute(select(Category).where(Category.name == "Professional Services"))
            cat_svc = res.scalar_one_or_none()
            if not cat_svc:
                cat_svc = Category(name="Professional Services", description="Implementation, onboarding, and advisory services")
                db.add(cat_svc)
                await db.flush()

            # Product 1: Dell Latitude 7440
            res = await db.execute(select(Product).where(Product.sku == "DEV-LAP-001"))
            p_laptop = res.scalar_one_or_none()
            if not p_laptop:
                p_laptop = Product(
                    sku="DEV-LAP-001",
                    name="Dell Latitude 7440",
                    description="14-inch premium commercial business laptop with Intel 13th Gen processors.",
                    base_price=1299.00,
                    cost_price=850.00,
                    currency="USD",
                    billing_type="NRC",
                    is_active=True,
                    category_id=cat_hw.id
                )
                db.add(p_laptop)
                await db.flush()
                print(f"  Created Product 1: Dell Latitude 7440 (ID: {p_laptop.id})")
            else:
                p_laptop.name = "Dell Latitude 7440"
                p_laptop.base_price = 1299.00
                p_laptop.cost_price = 850.00
                p_laptop.billing_type = "NRC"
                p_laptop.is_active = True
                p_laptop.category_id = cat_hw.id
                await db.flush()
                print(f"  Reusing Product 1: Dell Latitude 7440 (ID: {p_laptop.id})")

            # Product 2: Enterprise Cloud Subscription
            res = await db.execute(select(Product).where(Product.sku == "SaaS-TIER-SEED"))
            p_cloud = res.scalar_one_or_none()
            if not p_cloud:
                p_cloud = Product(
                    sku="SaaS-TIER-SEED",
                    name="Enterprise Cloud Subscription",
                    description="Monthly per-user enterprise cloud platform subscription with volume tiering.",
                    base_price=49.00,
                    cost_price=20.00,
                    currency="USD",
                    billing_type="MRC",
                    is_active=True,
                    category_id=cat_cloud.id
                )
                db.add(p_cloud)
                await db.flush()
                print(f"  Created Product 2: Enterprise Cloud Subscription (ID: {p_cloud.id})")
            else:
                p_cloud.name = "Enterprise Cloud Subscription"
                p_cloud.base_price = 49.00
                p_cloud.cost_price = 20.00
                p_cloud.billing_type = "MRC"
                p_cloud.is_active = True
                p_cloud.category_id = cat_cloud.id
                await db.flush()
                print(f"  Reusing Product 2: Enterprise Cloud Subscription (ID: {p_cloud.id})")

            # Product 3: Implementation Consulting Service
            res = await db.execute(select(Product).where(Product.sku == "DEV-SVC-IMP"))
            p_svc = res.scalar_one_or_none()
            if not p_svc:
                p_svc = Product(
                    sku="DEV-SVC-IMP",
                    name="Implementation Consulting Service",
                    description="Professional deployment, environment setup, and migration advisory package.",
                    base_price=1500.00,
                    cost_price=900.00,
                    currency="USD",
                    billing_type="NRC",
                    is_active=True,
                    category_id=cat_svc.id
                )
                db.add(p_svc)
                await db.flush()
                print(f"  Created Product 3: Implementation Consulting Service (ID: {p_svc.id})")
            else:
                p_svc.name = "Implementation Consulting Service"
                p_svc.base_price = 1500.00
                p_svc.cost_price = 900.00
                p_svc.billing_type = "NRC"
                p_svc.is_active = True
                p_svc.category_id = cat_svc.id
                await db.flush()
                print(f"  Reusing Product 3: Implementation Consulting Service (ID: {p_svc.id})")

            # ---------------------------------------------------------
            # 4. PRODUCT CONFIGURATION: DELL LATITUDE 7440
            # ---------------------------------------------------------
            print("\n[4/6] Verifying Product Configuration Groups, Options & Rules...")
            groups_def = [
                {
                    "name": "Processor",
                    "description": "Select high-performance Intel CPU",
                    "required": True,
                    "selection_type": "SINGLE_SELECT",
                    "display_order": 1,
                    "options": [
                        {"name": "Intel Core i7-13700H (14-Core, up to 5.0GHz)", "value": "i7-13700H", "display_order": 1},
                        {"name": "Intel Core i5-13500H (12-Core, up to 4.7GHz)", "value": "i5-13500H", "display_order": 2},
                    ]
                },
                {
                    "name": "Memory",
                    "description": "System RAM capacity",
                    "required": True,
                    "selection_type": "SINGLE_SELECT",
                    "display_order": 2,
                    "options": [
                        {"name": "16 GB DDR5 5200MHz", "value": "16GB", "display_order": 1},
                        {"name": "32 GB DDR5 5200MHz", "value": "32GB", "display_order": 2},
                    ]
                },
                {
                    "name": "Storage",
                    "description": "High-speed PCIe NVMe SSD",
                    "required": True,
                    "selection_type": "SINGLE_SELECT",
                    "display_order": 3,
                    "options": [
                        {"name": "512 GB PCIe NVMe SSD", "value": "512GB", "display_order": 1},
                        {"name": "1 TB PCIe NVMe SSD", "value": "1TB", "display_order": 2},
                    ]
                },
                {
                    "name": "Support",
                    "description": "Warranty and enterprise support tier",
                    "required": True,
                    "selection_type": "SINGLE_SELECT",
                    "display_order": 4,
                    "options": [
                        {"name": "Standard 1-Year Basic Support", "value": "STANDARD", "display_order": 1},
                        {"name": "Premium 3-Year ProSupport Plus", "value": "PREMIUM", "display_order": 2},
                    ]
                },
            ]

            saved_options = {}

            for g_data in groups_def:
                res = await db.execute(
                    select(ProductConfigurationGroup).where(
                        ProductConfigurationGroup.product_id == p_laptop.id,
                        ProductConfigurationGroup.name == g_data["name"]
                    )
                )
                group = res.scalar_one_or_none()

                if not group:
                    group = ProductConfigurationGroup(
                        product_id=p_laptop.id,
                        name=g_data["name"],
                        description=g_data["description"],
                        required=g_data["required"],
                        selection_type=g_data["selection_type"],
                        display_order=g_data["display_order"],
                        is_active=True
                    )
                    db.add(group)
                    await db.flush()
                    print(f"  Created config group: {group.name}")
                else:
                    group.required = g_data["required"]
                    group.selection_type = g_data["selection_type"]
                    group.display_order = g_data["display_order"]
                    await db.flush()

                for opt_data in g_data["options"]:
                    res = await db.execute(
                        select(ProductConfigurationOption).where(
                            ProductConfigurationOption.group_id == group.id,
                            ProductConfigurationOption.value == opt_data["value"]
                        )
                    )
                    option = res.scalar_one_or_none()

                    if not option:
                        option = ProductConfigurationOption(
                            group_id=group.id,
                            name=opt_data["name"],
                            value=opt_data["value"],
                            display_order=opt_data["display_order"],
                            is_active=True
                        )
                        db.add(option)
                        await db.flush()
                        print(f"    Created option: {option.name}")
                    else:
                        option.name = opt_data["name"]
                        option.display_order = opt_data["display_order"]
                        await db.flush()

                    saved_options[opt_data["value"]] = option

            # Validation Rule: Premium Support REQUIRES 32 GB Memory
            premium_opt = saved_options.get("PREMIUM")
            ram_32_opt = saved_options.get("32GB")

            if premium_opt and ram_32_opt:
                res = await db.execute(
                    select(ConfigurationRule).where(
                        ConfigurationRule.product_id == p_laptop.id,
                        ConfigurationRule.source_option_id == premium_opt.id,
                        ConfigurationRule.target_option_id == ram_32_opt.id
                    )
                )
                rule = res.scalar_one_or_none()

                if not rule:
                    rule = ConfigurationRule(
                        product_id=p_laptop.id,
                        rule_type=ConfigRuleType.REQUIRES.value,
                        source_option_id=premium_opt.id,
                        target_option_id=ram_32_opt.id,
                        message="Premium 3-Year ProSupport Plus requires 32 GB DDR5 Memory for advanced diagnostics.",
                        is_active=True
                    )
                    db.add(rule)
                    await db.flush()
                    print(f"  Configured Rule: Premium Support REQUIRES 32 GB Memory")

            # ---------------------------------------------------------
            # 5. PRICING SETTINGS & TIERS
            # ---------------------------------------------------------
            print("\n[5/6] Verifying Pricing Settings and Volume Tiers...")
            # Dell Laptop Pricing Setting
            res = await db.execute(select(ProductPricingSetting).where(ProductPricingSetting.product_id == p_laptop.id))
            lap_setting = res.scalar_one_or_none()
            if not lap_setting:
                lap_setting = ProductPricingSetting(
                    product_id=p_laptop.id,
                    pricing_method="STANDARD",
                    markup_percent=0.00
                )
                db.add(lap_setting)
                await db.flush()
            else:
                lap_setting.pricing_method = "STANDARD"
                await db.flush()

            # Implementation Service Pricing Setting
            res = await db.execute(select(ProductPricingSetting).where(ProductPricingSetting.product_id == p_svc.id))
            svc_setting = res.scalar_one_or_none()
            if not svc_setting:
                svc_setting = ProductPricingSetting(
                    product_id=p_svc.id,
                    pricing_method="STANDARD",
                    markup_percent=0.00
                )
                db.add(svc_setting)
                await db.flush()
            else:
                svc_setting.pricing_method = "STANDARD"
                await db.flush()

            # Cloud Subscription Pricing Setting (TIERED - VOLUME)
            res = await db.execute(select(ProductPricingSetting).where(ProductPricingSetting.product_id == p_cloud.id))
            cloud_setting = res.scalar_one_or_none()
            if not cloud_setting:
                cloud_setting = ProductPricingSetting(
                    product_id=p_cloud.id,
                    pricing_method="TIERED",
                    markup_percent=0.00
                )
                db.add(cloud_setting)
                await db.flush()
            else:
                cloud_setting.pricing_method = "TIERED"
                await db.flush()

            # Tiers for Cloud Subscription:
            # 1-20: $49/mo, 21-50: $45/mo, 51+: $39/mo
            res = await db.execute(select(ProductPricingTier).where(ProductPricingTier.product_id == p_cloud.id))
            existing_tiers = res.scalars().all()
            if not existing_tiers:
                tiers_data = [
                    {"min_quantity": 1, "max_quantity": 20, "price": 49.00, "order": 1},
                    {"min_quantity": 21, "max_quantity": 50, "price": 45.00, "order": 2},
                    {"min_quantity": 51, "max_quantity": None, "price": 39.00, "order": 3},
                ]
                for t in tiers_data:
                    tier = ProductPricingTier(
                        product_id=p_cloud.id,
                        pricing_method="TIERED",
                        tiered_mode="VOLUME",
                        min_quantity=t["min_quantity"],
                        max_quantity=t["max_quantity"],
                        price=t["price"],
                        display_order=t["order"],
                        is_active=True
                    )
                    db.add(tier)
                await db.flush()
                print("  Created Volume Tiers for Enterprise Cloud Subscription (1-20: $49, 21-50: $45, 51+: $39)")

            # ---------------------------------------------------------
            # 6. DEMO QUOTE: ACME IT INFRASTRUCTURE UPGRADE
            # ---------------------------------------------------------
            print("\n[6/6] Verifying Demo Quote 'Acme IT Infrastructure Upgrade'...")
            res = await db.execute(select(Quote).where(Quote.quote_number == "Q-2026-0001"))
            quote = res.scalar_one_or_none()
            if not quote:
                quote = Quote(
                    quote_number="Q-2026-0001",
                    version=1,
                    customer_id=acme.id,
                    title="Acme IT Infrastructure Upgrade",
                    description="Comprehensive IT infrastructure upgrade including Dell developer workstations, enterprise cloud subscriptions, and professional implementation consulting.",
                    status=QuoteStatus.DRAFT,
                    currency="USD",
                    valid_until=datetime.now(timezone.utc) + timedelta(days=30),
                    notes="Standard commercial terms. Volume hardware discount pre-applied.",
                    subtotal=Decimal("15641.00"),
                    discount_amount=Decimal("1299.00"),
                    tax_amount=Decimal("0.00"),
                    total_amount=Decimal("14342.00"),
                    margin_percentage=Decimal("34.46"),
                    created_by_id=demo_user.id
                )
                db.add(quote)
                await db.flush()

                # Line Item 1: 10 Dell Latitude 7440 laptops @ $1299, 10% discount = $11,691
                item1 = QuoteLineItem(
                    quote_id=quote.id,
                    product_id=p_laptop.id,
                    product_name=p_laptop.name,
                    sku=p_laptop.sku,
                    billing_type=p_laptop.billing_type,
                    currency="USD",
                    quantity=10,
                    unit_price=Decimal("1299.00"),
                    discount_percentage=Decimal("10.00"),
                    discount_amount=Decimal("1299.00"),
                    total_price=Decimal("11691.00"),
                    pricing_method="STANDARD",
                    margin_amount=Decimal("3191.00"),
                    margin_percentage=Decimal("27.29")
                )
                db.add(item1)

                # Line Item 2: 50 Enterprise Cloud Subscriptions @ $49/mo = $2,450
                item2 = QuoteLineItem(
                    quote_id=quote.id,
                    product_id=p_cloud.id,
                    product_name=p_cloud.name,
                    sku=p_cloud.sku,
                    billing_type=p_cloud.billing_type,
                    currency="USD",
                    quantity=50,
                    unit_price=Decimal("49.00"),
                    discount_percentage=Decimal("0.00"),
                    discount_amount=Decimal("0.00"),
                    total_price=Decimal("2450.00"),
                    pricing_method="TIERED",
                    margin_amount=Decimal("1450.00"),
                    margin_percentage=Decimal("59.18")
                )
                db.add(item2)

                # Line Item 3: 1 Implementation Consulting Service @ $1500 = $1,500
                item3 = QuoteLineItem(
                    quote_id=quote.id,
                    product_id=p_svc.id,
                    product_name=p_svc.name,
                    sku=p_svc.sku,
                    billing_type=p_svc.billing_type,
                    currency="USD",
                    quantity=1,
                    unit_price=Decimal("1500.00"),
                    discount_percentage=Decimal("0.00"),
                    discount_amount=Decimal("0.00"),
                    total_price=Decimal("1500.00"),
                    pricing_method="STANDARD",
                    margin_amount=Decimal("600.00"),
                    margin_percentage=Decimal("40.00")
                )
                db.add(item3)
                await db.flush()
                print(f"  Created Demo Quote: Q-2026-0001 (DRAFT, Total: $14,342.00)")
            else:
                print(f"  Reusing existing Demo Quote: Q-2026-0001 (Status: {quote.status})")

            await db.commit()
            print("\n" + "=" * 60)
            print("DEMO DATA SEEDING COMPLETE AND IDEMPOTENT!")
            print("=" * 60)
            return True

        except Exception as e:
            await db.rollback()
            print(f"\n[ERROR] Seeding failed: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    success = asyncio.run(seed_demo_data())
    sys.exit(0 if success else 1)
