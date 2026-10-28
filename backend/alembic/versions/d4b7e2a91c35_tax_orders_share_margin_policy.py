"""tax rates, orders, proposal share links, margin approval policies

Revision ID: d4b7e2a91c35
Revises: c3a91d5e7f20
Create Date: 2026-10-28 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'd4b7e2a91c35'
down_revision = 'c3a91d5e7f20'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tax_rates",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("country", sa.String(100), nullable=True),
        sa.Column("region", sa.String(100), nullable=True),
        sa.Column("rate_percent", sa.Numeric(5, 2), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_table(
        "orders",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("order_number", sa.String(50), nullable=False, unique=True, index=True),
        sa.Column("quote_id", sa.Integer(), sa.ForeignKey("quotes.id"), nullable=False, unique=True),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False),
        sa.Column("subtotal", sa.Numeric(12, 2), nullable=False),
        sa.Column("discount_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("tax_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("total_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "order_lines",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("product_name", sa.String(255), nullable=True),
        sa.Column("sku", sa.String(100), nullable=True),
        sa.Column("billing_type", sa.String(50), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("discount_percentage", sa.Numeric(5, 2), nullable=False),
        sa.Column("total_price", sa.Numeric(12, 2), nullable=False),
    )
    op.add_column("quotes", sa.Column("tax_rate_percent", sa.Numeric(5, 2), nullable=True))
    op.add_column("quotes", sa.Column("tax_label", sa.String(100), nullable=True))
    op.add_column("quotes", sa.Column("share_token", sa.String(64), nullable=True))
    op.create_index("ix_quotes_share_token", "quotes", ["share_token"], unique=True)
    op.add_column("quotes", sa.Column("customer_response_name", sa.String(255), nullable=True))
    op.add_column("quotes", sa.Column("customer_response_note", sa.Text(), nullable=True))
    op.add_column("quotes", sa.Column("customer_responded_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("approval_policies", sa.Column("policy_type", sa.String(20), nullable=False, server_default="DISCOUNT"))
    op.add_column("approval_policies", sa.Column("margin_threshold", sa.Numeric(5, 2), nullable=True))


def downgrade() -> None:
    op.drop_column("approval_policies", "margin_threshold")
    op.drop_column("approval_policies", "policy_type")
    for col in ("customer_responded_at", "customer_response_note", "customer_response_name"):
        op.drop_column("quotes", col)
    op.drop_index("ix_quotes_share_token", table_name="quotes")
    for col in ("share_token", "tax_label", "tax_rate_percent"):
        op.drop_column("quotes", col)
    op.drop_table("order_lines")
    op.drop_table("orders")
    op.drop_table("tax_rates")
