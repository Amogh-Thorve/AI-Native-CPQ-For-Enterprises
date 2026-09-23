"""quote_number_version_unique

Revision ID: b417d891c321
Revises: f382a921d782
Create Date: 2026-09-23 17:31:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'b417d891c321'
down_revision = 'f382a921d782'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Drop unique index on quote_number alone
    op.drop_index('ix_quotes_quote_number', table_name='quotes')
    # Recreate index as non-unique for fast lookups
    op.create_index('ix_quotes_quote_number', 'quotes', ['quote_number'], unique=False)
    # Create composite unique constraint on (quote_number, version)
    op.create_unique_constraint('uq_quotes_quote_number_version', 'quotes', ['quote_number', 'version'])

def downgrade() -> None:
    op.drop_constraint('uq_quotes_quote_number_version', 'quotes', type_='unique')
    op.drop_index('ix_quotes_quote_number', table_name='quotes')
    op.create_index('ix_quotes_quote_number', 'quotes', ['quote_number'], unique=True)
