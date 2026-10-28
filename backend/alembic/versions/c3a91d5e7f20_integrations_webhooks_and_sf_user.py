"""integrations: webhook config table and salesforce user email

Revision ID: c3a91d5e7f20
Revises: b417d891c321
Create Date: 2026-10-28 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'c3a91d5e7f20'
down_revision = 'b417d891c321'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "webhook_configs",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("endpoint_url", sa.String(500), nullable=False),
        sa.Column("secret_key", sa.String(100), nullable=False),
        sa.Column("events", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_delivery_status", sa.String(200), nullable=True),
        sa.Column("last_delivery_at", sa.DateTime(), nullable=True),
    )
    op.add_column("salesforce_tokens", sa.Column("user_email", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("salesforce_tokens", "user_email")
    op.drop_table("webhook_configs")
