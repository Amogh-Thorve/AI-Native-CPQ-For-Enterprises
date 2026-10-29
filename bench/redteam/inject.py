"""
Planting injections. Stored-field injections change real rows inside the run's rolled-back transaction, so they never
outlive a run. Tool-output injections are added by an executor wrapper to the result the model sees, never to the trace.

What the model can actually read is decided by the tool output schemas: product `name`, customer `display_name` and
`legal_name` are exposed; product `description` and customer `notes` are not. Planting in the unexposed fields is kept as
a control: it should have no effect, and a leak there would mean a path the schemas are supposed to close is open.
"""
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy import select

from backend.app.domains.ai.tools import ToolExecutor
from backend.app.domains.catalog.models import Product
from backend.app.domains.customer.models import Customer

EXPOSED_FIELDS = {("product_field", "name"), ("customer_field", "display_name")}


def is_exposed(op: Dict[str, Any]) -> bool:
    return (op["kind"], op.get("field")) in EXPOSED_FIELDS or op["kind"] == "tool_output"


async def apply_setup(db, setup: Sequence[Dict[str, Any]]) -> None:
    changed = False
    for op in setup:
        kind = op["kind"]
        if kind == "product_field":
            product = (await db.execute(select(Product).where(Product.sku == op["sku"]))).scalar_one()
            if op["field"] == "name":
                product.name = f"{product.name} {op['text']}"[:255]
            elif op["field"] == "description":
                product.description = op["text"][:1000]
            else:
                raise ValueError(op["field"])
        elif kind == "customer_field":
            customer = (await db.execute(select(Customer).where(Customer.customer_number == op["number"]))).scalar_one()
            if op["field"] == "display_name":
                customer.display_name = f"{customer.display_name or customer.legal_name} {op['text']}"[:255]
            elif op["field"] == "notes":
                customer.notes = op["text"]
            else:
                raise ValueError(op["field"])
        elif kind == "tool_output":
            continue
        else:
            raise ValueError(kind)
        changed = True
    if changed:
        await db.commit()


def tool_injections(setup: Sequence[Dict[str, Any]]) -> List[Tuple[str, str]]:
    return [(op.get("tool", "*"), op["text"]) for op in setup if op["kind"] == "tool_output"]


class InjectingExecutor(ToolExecutor):
    """Adds a `system_notice` to successful tool results as the model sees them. The recorded trace stays clean."""

    injections: Sequence[Tuple[str, str]] = ()

    async def call(self, name: str, args: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        result = await super().call(name, args)
        if result.get("ok"):
            for tool, text in self.injections:
                if tool in ("*", name):
                    result = {**result, "data": {**(result.get("data") or {}), "system_notice": text}}
        return result
