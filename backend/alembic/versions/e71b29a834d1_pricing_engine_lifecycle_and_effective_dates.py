"""pricing_engine_lifecycle_and_effective_dates

Revision ID: e71b29a834d1
Revises: 9e57e5256df4
Create Date: 2026-09-23 17:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e71b29a834d1'
down_revision: Union[str, None] = '9e57e5256df4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add lifecycle and effective dating columns to product_pricing_settings
    op.add_column('product_pricing_settings', sa.Column('status', sa.String(length=20), server_default='ACTIVE', nullable=False))
    op.add_column('product_pricing_settings', sa.Column('effective_from', sa.DateTime(timezone=True), nullable=True))
    op.add_column('product_pricing_settings', sa.Column('effective_until', sa.DateTime(timezone=True), nullable=True))
    op.add_column('product_pricing_settings', sa.Column('discount_percent', sa.Numeric(precision=5, scale=2), server_default='0.00', nullable=True))

    # Add display_order and is_active to product_pricing_tiers
    op.add_column('product_pricing_tiers', sa.Column('display_order', sa.Integer(), server_default='1', nullable=False))
    op.add_column('product_pricing_tiers', sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False))


def downgrade() -> None:
    op.drop_column('product_pricing_tiers', 'is_active')
    op.drop_column('product_pricing_tiers', 'display_order')
    op.drop_column('product_pricing_settings', 'discount_percent')
    op.drop_column('product_pricing_settings', 'effective_until')
    op.drop_column('product_pricing_settings', 'effective_from')
    op.drop_column('product_pricing_settings', 'status')
