"""enhance_quotes_schema_and_audit

Revision ID: f382a921d782
Revises: e71b29a834d1
Create Date: 2026-09-23 17:25:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f382a921d782'
down_revision: Union[str, None] = 'e71b29a834d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add missing metadata and aggregate columns to quotes
    op.add_column('quotes', sa.Column('title', sa.String(length=255), nullable=True))
    op.add_column('quotes', sa.Column('description', sa.Text(), nullable=True))
    op.add_column('quotes', sa.Column('currency', sa.String(length=10), server_default='USD', nullable=False))
    op.add_column('quotes', sa.Column('valid_until', sa.DateTime(timezone=True), nullable=True))
    op.add_column('quotes', sa.Column('notes', sa.Text(), nullable=True))
    op.add_column('quotes', sa.Column('subtotal', sa.Numeric(precision=12, scale=2), server_default='0.00', nullable=False))
    op.add_column('quotes', sa.Column('tax_amount', sa.Numeric(precision=12, scale=2), server_default='0.00', nullable=False))

    # 2. Add historical snapshot columns to quote_line_items
    op.add_column('quote_line_items', sa.Column('product_name', sa.String(length=255), nullable=True))
    op.add_column('quote_line_items', sa.Column('sku', sa.String(length=100), nullable=True))
    op.add_column('quote_line_items', sa.Column('billing_type', sa.String(length=50), server_default='MRC', nullable=False))
    op.add_column('quote_line_items', sa.Column('currency', sa.String(length=10), server_default='USD', nullable=False))
    op.add_column('quote_line_items', sa.Column('configuration_id', sa.String(length=100), nullable=True))
    op.add_column('quote_line_items', sa.Column('configuration_snapshot', sa.JSON(), nullable=True))
    op.add_column('quote_line_items', sa.Column('discount_amount', sa.Numeric(precision=12, scale=2), server_default='0.00', nullable=False))
    op.add_column('quote_line_items', sa.Column('pricing_method', sa.String(length=50), nullable=True))
    op.add_column('quote_line_items', sa.Column('pricing_breakdown', sa.JSON(), nullable=True))
    op.add_column('quote_line_items', sa.Column('margin_amount', sa.Numeric(precision=12, scale=2), nullable=True))
    op.add_column('quote_line_items', sa.Column('margin_percentage', sa.Numeric(precision=5, scale=2), nullable=True))

    # 3. Create quote_audit_logs table
    op.create_table(
        'quote_audit_logs',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('quote_id', sa.Integer(), sa.ForeignKey('quotes.id', ondelete='CASCADE'), index=True, nullable=False),
        sa.Column('user_id', sa.Uuid(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('user_role', sa.String(length=50), nullable=True),
        sa.Column('action', sa.String(length=50), index=True, nullable=False),
        sa.Column('before_value', sa.JSON(), nullable=True),
        sa.Column('after_value', sa.JSON(), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    )


def downgrade() -> None:
    op.drop_table('quote_audit_logs')

    op.drop_column('quote_line_items', 'margin_percentage')
    op.drop_column('quote_line_items', 'margin_amount')
    op.drop_column('quote_line_items', 'pricing_breakdown')
    op.drop_column('quote_line_items', 'pricing_method')
    op.drop_column('quote_line_items', 'discount_amount')
    op.drop_column('quote_line_items', 'configuration_snapshot')
    op.drop_column('quote_line_items', 'configuration_id')
    op.drop_column('quote_line_items', 'currency')
    op.drop_column('quote_line_items', 'billing_type')
    op.drop_column('quote_line_items', 'sku')
    op.drop_column('quote_line_items', 'product_name')

    op.drop_column('quotes', 'tax_amount')
    op.drop_column('quotes', 'subtotal')
    op.drop_column('quotes', 'notes')
    op.drop_column('quotes', 'valid_until')
    op.drop_column('quotes', 'currency')
    op.drop_column('quotes', 'description')
    op.drop_column('quotes', 'title')
