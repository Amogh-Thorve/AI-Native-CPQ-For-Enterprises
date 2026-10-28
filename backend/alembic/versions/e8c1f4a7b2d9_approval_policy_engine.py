"""approval policy engine: rule conditions, request snapshots, two-step steps

Revision ID: e8c1f4a7b2d9
Revises: d4b7e2a91c35
Create Date: 2026-10-28 18:00:00.000000

Existing approval policies are deactivated and replaced by the default rule set. Pending requests from the
old engine are marked SUPERSEDED; their quotes can be resubmitted under the new rules.
"""
from alembic import op
import sqlalchemy as sa

revision = 'e8c1f4a7b2d9'
down_revision = 'd4b7e2a91c35'
branch_labels = None
depends_on = None

# (name, metric, op, threshold, required_level, rule_group)
DEFAULT_RULES = [
    ("Default: total at or above 50,000 needs manager", "TOTAL", "GE", 50000, "MANAGER", 1),
    ("Default: line discount at or above 10% needs manager", "MAX_LINE_DISCOUNT", "GE", 10, "MANAGER", 2),
    ("Default: line discount at or above 20% needs executive", "MAX_LINE_DISCOUNT", "GE", 20, "EXECUTIVE", 3),
    ("Default: margin below 20% needs executive", "MARGIN_PERCENT", "LT", 20, "EXECUTIVE", 4),
    ("Default: total at or above 250,000 with 20% discount needs two-step (total)", "TOTAL", "GE", 250000, "TWO_STEP", 5),
    ("Default: total at or above 250,000 with 20% discount needs two-step (discount)", "MAX_LINE_DISCOUNT", "GE", 20, "TWO_STEP", 5),
]


def upgrade() -> None:
    op.add_column("approval_policies", sa.Column("metric", sa.String(30), nullable=False, server_default="MAX_LINE_DISCOUNT"))
    op.add_column("approval_policies", sa.Column("op", sa.String(4), nullable=False, server_default="GE"))
    op.add_column("approval_policies", sa.Column("threshold", sa.Numeric(12, 2), nullable=True))
    op.add_column("approval_policies", sa.Column("required_level", sa.String(20), nullable=False, server_default="EXECUTIVE"))
    op.add_column("approval_policies", sa.Column("rule_group", sa.Integer(), nullable=False, server_default="0"))

    op.add_column("approval_requests", sa.Column("quote_version", sa.Integer(), nullable=True))
    op.add_column("approval_requests", sa.Column("snapshot_hash", sa.String(64), nullable=True))
    op.add_column("approval_requests", sa.Column("required_level", sa.String(20), nullable=True))
    op.add_column("approval_requests", sa.Column("requested_by_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True))
    op.add_column("approval_requests", sa.Column("request_reason", sa.String(500), nullable=True))

    op.create_table(
        "approval_request_steps",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("request_id", sa.Integer(), sa.ForeignKey("approval_requests.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("level", sa.String(20), nullable=False),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("decided_by_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
        sa.Column("comments", sa.String(500), nullable=True),
    )

    op.add_column("quotes", sa.Column("approved_snapshot_hash", sa.String(64), nullable=True))

    # Old policies are kept for history but no longer evaluated.
    op.execute("UPDATE approval_policies SET is_active = false WHERE is_active = true")

    for name, metric, operator, threshold, level, group in DEFAULT_RULES:
        role = "Sales Manager" if level == "MANAGER" else "Executive"
        policy_type = "MARGIN" if metric == "MARGIN_PERCENT" else "RULE"
        op.execute(sa.text(
            "INSERT INTO approval_policies "
            "(name, discount_threshold, role_required, is_active, policy_type, margin_threshold, "
            " metric, op, threshold, required_level, rule_group) "
            "VALUES (:name, 0, :role, true, :policy_type, NULL, :metric, :op, :threshold, :level, :grp)"
        ).bindparams(name=name, role=role, policy_type=policy_type, metric=metric, op=operator,
                     threshold=threshold, level=level, grp=group))

    # Requests created by the old engine have no snapshot, so they cannot be approved as they are.
    op.execute("UPDATE approval_requests SET status = 'SUPERSEDED' WHERE status = 'PENDING'")


def downgrade() -> None:
    op.execute("UPDATE approval_requests SET status = 'PENDING' WHERE status = 'SUPERSEDED'")
    op.execute("DELETE FROM approval_policies WHERE name LIKE 'Default: %'")
    op.execute("UPDATE approval_policies SET is_active = true WHERE rule_group = 0")
    op.drop_column("quotes", "approved_snapshot_hash")
    op.drop_table("approval_request_steps")
    for col in ("request_reason", "requested_by_id", "required_level", "snapshot_hash", "quote_version"):
        op.drop_column("approval_requests", col)
    for col in ("rule_group", "required_level", "threshold", "op", "metric"):
        op.drop_column("approval_policies", col)
