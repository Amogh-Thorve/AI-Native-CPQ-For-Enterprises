"""Outbound webhook delivery. Failures are recorded but never break the originating business action."""
import hashlib
import hmac
import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.domains.integrations.models import WebhookConfig

logger = logging.getLogger(__name__)

SUPPORTED_EVENTS = [
    "quote.submitted", "quote.approved", "quote.rejected", "quote.sent", "quote.accepted",
]


def sign(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


async def get_config(db: AsyncSession) -> Optional[WebhookConfig]:
    return (await db.execute(select(WebhookConfig).limit(1))).scalars().first()


async def deliver(db: AsyncSession, cfg: WebhookConfig, event: str, data: Dict[str, Any]) -> tuple[bool, int, str]:
    """POSTs one signed event and records the outcome on the config row. Returns (ok, status_code, body_excerpt)."""
    payload = json.dumps({"id": f"evt_{uuid.uuid4().hex[:16]}", "event": event, "created_at": datetime.utcnow().isoformat() + "Z", "data": data}, default=str).encode()
    ok, code, body = False, 0, ""
    try:
        async with httpx.AsyncClient(timeout=8, follow_redirects=False) as client:
            r = await client.post(cfg.endpoint_url, content=payload, headers={
                "Content-Type": "application/json", "X-CPQ-Event": event, "X-CPQ-Signature": sign(cfg.secret_key, payload),
            })
        code, body, ok = r.status_code, r.text[:200], 200 <= r.status_code < 300
        cfg.last_delivery_status = f"{code} {'OK' if ok else 'Error'}"
    except Exception as exc:
        body = f"{type(exc).__name__}: {exc}"[:200]
        cfg.last_delivery_status = f"Failed: {body}"[:200]
    cfg.last_delivery_at = datetime.utcnow()
    db.add(cfg)
    await db.flush()
    return ok, code, body


async def emit(db: AsyncSession, event: str, data: Dict[str, Any]) -> None:
    """Deliver `event` if a webhook is enabled and subscribed to it. Never raises."""
    try:
        cfg = await get_config(db)
        if cfg and cfg.enabled and event in (cfg.events or []):
            await deliver(db, cfg, event, data)
    except Exception as exc:
        logger.warning("webhook emit failed for %s: %s", event, exc)
