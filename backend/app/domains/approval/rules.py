"""Loads the active rule-engine rows from the database and converts them to the pure engine's RuleRow."""
from decimal import Decimal
from typing import List

from backend.app.domains.approval.engine import Level, Metric, Op, RuleRow
from backend.app.domains.approval.repositories import ApprovalRepository


async def load_rule_rows(repo: ApprovalRepository) -> List[RuleRow]:
    rows = await repo.list_active_rules()
    return [
        RuleRow(
            rule_id=r.id, group=r.rule_group, metric=Metric(r.metric), op=Op(r.op),
            threshold=Decimal(str(r.threshold)), level=Level[r.required_level],
        )
        for r in rows
        if r.threshold is not None
    ]
