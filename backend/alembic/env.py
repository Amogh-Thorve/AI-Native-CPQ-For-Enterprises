import asyncio
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# 1. Import declarative base from core
from backend.app.core.database import Base
from backend.app.core.config import settings

# 2. Import all domain models so they register on Base.metadata
from backend.app.domains.auth.models import User, Role, Permission, UserRole, RolePermission, AuthenticationSession, RefreshToken, PasswordResetToken, EmailVerificationToken
from backend.app.domains.customer.models import Customer, Contact, CustomerAddress
from backend.app.domains.catalog.models import Category, Product, PriceBook, PriceBookEntry
from backend.app.domains.pricing.models import PricingRule, ProductPricingTier, ProductPricingSetting
from backend.app.domains.configuration.models import ConfigurationRule
from backend.app.domains.quotes.models import Quote, QuoteLineItem
from backend.app.domains.approval.models import ApprovalPolicy, ApprovalRequest
from backend.app.domains.document.models import QuoteDocument
from backend.app.domains.email.models import EmailLog
from backend.app.domains.integrations.models import IntegrationSyncLog, SalesforceToken

# Alembic Config object, which provides access to values within the .ini file.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set target metadata for autogenerate migrations support
target_metadata = Base.metadata

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = settings.DATABASE_URL
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()

async def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    # Build engine configuration, injecting settings database url
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = settings.DATABASE_URL
    
    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()

if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
