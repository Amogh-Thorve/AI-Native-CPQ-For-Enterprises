"""add_pricing_rbac_and_audit

Revision ID: 1510ce09e8d1
Revises: b97fc420a234
Create Date: 2026-08-31 13:38:37.924736

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1510ce09e8d1'
down_revision: Union[str, None] = 'b97fc420a234'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add columns to pricing_rules
    op.add_column("pricing_rules", sa.Column("description", sa.String(length=500), nullable=True))
    op.add_column("pricing_rules", sa.Column("status", sa.String(length=20), nullable=True, server_default="ACTIVE"))
    op.add_column("pricing_rules", sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))
    op.add_column("pricing_rules", sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.func.now()))
    op.add_column("pricing_rules", sa.Column("updated_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))
    op.add_column("pricing_rules", sa.Column("updated_at", sa.DateTime(), nullable=True, server_default=sa.func.now()))

    # 2. Create pricing_audit_logs table
    op.create_table(
        "pricing_audit_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("user_role", sa.String(length=50), nullable=True),
        sa.Column("action", sa.String(length=50), nullable=True),
        sa.Column("pricing_config_id", sa.Integer(), nullable=True),
        sa.Column("product_id", sa.Integer(), nullable=True),
        sa.Column("timestamp", sa.DateTime(), nullable=True, server_default=sa.func.now()),
        sa.Column("before_value", sa.JSON(), nullable=True),
        sa.Column("after_value", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id")
    )
    op.create_index(op.f("ix_pricing_audit_logs_id"), "pricing_audit_logs", ["id"], unique=False)


def downgrade() -> None:
    # 1. Drop pricing_audit_logs table
    op.drop_index(op.f("ix_pricing_audit_logs_id"), table_name="pricing_audit_logs")
    op.drop_table("pricing_audit_logs")

    # 2. Drop columns from pricing_rules
    op.drop_column("pricing_rules", "updated_at")
    op.drop_column("pricing_rules", "updated_by")
    op.drop_column("pricing_rules", "created_at")
    op.drop_column("pricing_rules", "created_by")
    op.drop_column("pricing_rules", "status")
    op.drop_column("pricing_rules", "description")

