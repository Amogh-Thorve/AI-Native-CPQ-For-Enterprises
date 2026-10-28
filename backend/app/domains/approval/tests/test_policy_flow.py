"""
Approval flow tests against the local dev database: routing, decisions, self-approval, role checks,
two-step order, content drift, the send guard, and the tool-layer checker.
"""
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select

from backend.app.core.database import SessionLocal
from backend.app.core.exceptions import CPQException, DomainValidationError
from backend.app.domains.ai.tests.test_tools import ensure_user, load_user
from backend.app.domains.ai.tools.policy import Allow, Deny, NeedsApproval
from backend.app.domains.ai.tools.schemas import AddQuoteItemIn
from backend.app.domains.approval.checker import ApprovalPolicyChecker
from backend.app.domains.approval.models import ApprovalStatus
from backend.app.domains.approval.schemas import DecideApprovalRequest, SubmitApprovalRequest
from backend.app.domains.approval.services import ApprovalService
from backend.app.domains.catalog.models import Category, Product
from backend.app.domains.customer.schemas import CustomerCreate
from backend.app.domains.customer.services import CustomerService
from backend.app.domains.pricing.models import ProductPricingSetting
from backend.app.domains.quotes.models import QuoteAuditLog
from backend.app.domains.quotes.schemas import QuoteCreate, QuoteLineItemCreate
from backend.app.domains.quotes.services import QuoteService


async def world(db):
    rep = await ensure_user(db, "approval.rep@cpq.com", "Sales Representative")
    mgr = await ensure_user(db, "approval.mgr@cpq.com", "Sales Manager")
    exe = await ensure_user(db, "approval.exec@cpq.com", "Executive")
    suffix = uuid.uuid4().hex[:6]
    cat = Category(name=f"Approval_{suffix}", description="approval tests")
    db.add(cat)
    await db.flush()
    product = Product(
        sku=f"APP-{suffix}", name=f"Approval Laptop {suffix}", base_price=Decimal("1000.00"),
        cost_price=Decimal("700.00"), currency="USD", is_active=True, billing_type="NRC", category_id=cat.id,
    )
    db.add(product)
    await db.flush()
    db.add(ProductPricingSetting(product_id=product.id, pricing_method="STANDARD", markup_percent=Decimal("0"), status="ACTIVE"))
    cust = await CustomerService(db).create_customer(
        rep.id, CustomerCreate(customer_number=f"AP-{suffix}", legal_name=f"Approval Co {suffix}"), current_user=rep,
    )
    await db.commit()
    return {"rep": rep.id, "mgr": mgr.id, "exe": exe.id, "product": product.id, "customer": cust.id}


async def quote_with(db, w, *, qty: int, discount: str, submit: bool) -> int:
    rep = await load_user(db, w["rep"])
    qs = QuoteService(db)
    q = await qs.create_quote(
        creator_id=rep.id,
        schema=QuoteCreate(
            customer_id=w["customer"], title="Approval test",
            items=[QuoteLineItemCreate(product_id=w["product"], quantity=qty, discount_percentage=Decimal(discount))],
        ),
        current_user=rep,
    )
    await db.commit()
    if submit:
        await qs.submit_quote(q.id, current_user=rep)
        await db.commit()
    return q.id


async def reload(db, quote_id: int, rep_id):
    rep = await load_user(db, rep_id)
    return await QuoteService(db).get_quote(quote_id, rep)


async def decide(db, actor_id, request_id: int, status: ApprovalStatus, comments=None):
    actor = await load_user(db, actor_id)
    roles = [r.name for r in actor.roles]
    perms = {p.name for r in actor.roles for p in r.permissions}
    out = await ApprovalService(db).decide_request(
        request_id, actor.id, roles, perms, DecideApprovalRequest(status=status, comments=comments),
    )
    await db.commit()
    return out


async def open_requests(db, quote_id: int):
    return await ApprovalService(db).approval_repo.list_requests_for_quote(quote_id)


async def audit_actions(db, quote_id: int) -> set:
    rows = (await db.execute(select(QuoteAuditLog.action).where(QuoteAuditLog.quote_id == quote_id))).scalars().all()
    return set(rows)


@pytest.mark.asyncio
async def test_small_quote_is_auto_approved_with_its_hash():
    async with SessionLocal() as db:
        w = await world(db)
        qid = await quote_with(db, w, qty=1, discount="0", submit=True)
        q = await reload(db, qid, w["rep"])
        assert q.status == "APPROVED"
        assert q.approved_snapshot_hash
        assert await open_requests(db, qid) == []
        assert "QUOTE_AUTO_APPROVED" in await audit_actions(db, qid)


@pytest.mark.asyncio
async def test_manager_approval_applies_to_the_exact_reviewed_content():
    async with SessionLocal() as db:
        w = await world(db)
        qid = await quote_with(db, w, qty=10, discount="12", submit=True)
        reqs = await open_requests(db, qid)
        assert len(reqs) == 1
        req = reqs[0]
        assert req.required_level == "MANAGER"
        assert [s.role for s in req.steps] == ["Sales Manager"]
        assert (await reload(db, qid, w["rep"])).status == "SUBMITTED"

        await decide(db, w["mgr"], req.id, ApprovalStatus.APPROVED, "looks fine")
        q = await reload(db, qid, w["rep"])
        assert q.status == "APPROVED"
        assert q.approved_snapshot_hash == req.snapshot_hash
        assert "QUOTE_APPROVED" in await audit_actions(db, qid)


@pytest.mark.asyncio
async def test_submitter_cannot_approve_their_own_quote():
    async with SessionLocal() as db:
        w = await world(db)
        qid = await quote_with(db, w, qty=10, discount="12", submit=False)
        mgr = await load_user(db, w["mgr"])
        await QuoteService(db).submit_quote(qid, current_user=mgr)  # the manager submits it
        await db.commit()
        req = (await open_requests(db, qid))[0]
        with pytest.raises(CPQException) as exc:
            await decide(db, w["mgr"], req.id, ApprovalStatus.APPROVED)
        assert exc.value.error_code == "SELF_APPROVAL_NOT_ALLOWED"


@pytest.mark.asyncio
async def test_only_the_step_role_may_decide():
    async with SessionLocal() as db:
        w = await world(db)
        qid = await quote_with(db, w, qty=10, discount="12", submit=True)
        req = (await open_requests(db, qid))[0]
        with pytest.raises(CPQException) as exc:  # an executive cannot take a manager step
            await decide(db, w["exe"], req.id, ApprovalStatus.APPROVED)
        assert exc.value.error_code == "APPROVER_ROLE_REQUIRED"
        assert (await reload(db, qid, w["rep"])).status == "SUBMITTED"


@pytest.mark.asyncio
async def test_two_step_runs_manager_then_executive_in_order():
    async with SessionLocal() as db:
        w = await world(db)
        qid = await quote_with(db, w, qty=400, discount="20", submit=True)  # 320,000 at 20%: TWO_STEP
        req = (await open_requests(db, qid))[0]
        assert req.required_level == "TWO_STEP"
        assert [s.role for s in req.steps] == ["Sales Manager", "Executive"]

        with pytest.raises(CPQException) as exc:  # the executive cannot take the first step
            await decide(db, w["exe"], req.id, ApprovalStatus.APPROVED)
        assert exc.value.error_code == "APPROVER_ROLE_REQUIRED"

        after_manager = await decide(db, w["mgr"], req.id, ApprovalStatus.APPROVED)
        assert after_manager.status == "PENDING"
        assert after_manager.assigned_role == "Executive"
        assert (await reload(db, qid, w["rep"])).status == "SUBMITTED"

        with pytest.raises(CPQException) as exc:  # the manager cannot take the second step
            await decide(db, w["mgr"], req.id, ApprovalStatus.APPROVED)
        assert exc.value.error_code == "APPROVER_ROLE_REQUIRED"

        done = await decide(db, w["exe"], req.id, ApprovalStatus.APPROVED)
        assert done.status == "APPROVED"
        assert (await reload(db, qid, w["rep"])).status == "APPROVED"


@pytest.mark.asyncio
async def test_rejection_at_any_step_rejects_the_quote():
    async with SessionLocal() as db:
        w = await world(db)
        qid = await quote_with(db, w, qty=10, discount="12", submit=True)
        req = (await open_requests(db, qid))[0]
        out = await decide(db, w["mgr"], req.id, ApprovalStatus.REJECTED, "discount too deep")
        assert out.status == "REJECTED"
        assert (await reload(db, qid, w["rep"])).status == "REJECTED"
        assert "QUOTE_REJECTED" in await audit_actions(db, qid)


@pytest.mark.asyncio
async def test_changing_the_quote_after_submission_makes_the_approval_stale():
    async with SessionLocal() as db:
        w = await world(db)
        qid = await quote_with(db, w, qty=10, discount="12", submit=True)
        req = (await open_requests(db, qid))[0]

        q = await reload(db, qid, w["rep"])
        q.items[0].quantity = 11  # a change the approver never reviewed
        await db.commit()

        out = await decide(db, w["mgr"], req.id, ApprovalStatus.APPROVED)
        assert out.status == "STALE"
        q = await reload(db, qid, w["rep"])
        assert q.status == "DRAFT"
        assert q.approved_snapshot_hash is None
        assert "QUOTE_APPROVAL_STALE" in await audit_actions(db, qid)


@pytest.mark.asyncio
async def test_an_approval_stops_applying_once_the_quote_changes():
    async with SessionLocal() as db:
        w = await world(db)
        qid = await quote_with(db, w, qty=10, discount="12", submit=True)
        req = (await open_requests(db, qid))[0]
        await decide(db, w["mgr"], req.id, ApprovalStatus.APPROVED)
        assert (await reload(db, qid, w["rep"])).status == "APPROVED"

        q = await reload(db, qid, w["rep"])
        q.items[0].quantity = 12
        await db.commit()

        rep = await load_user(db, w["rep"])
        with pytest.raises(DomainValidationError) as exc:
            await QuoteService(db).mark_sent(qid, current_user=rep)
        assert "changed after it was approved" in str(exc.value.detail)


@pytest.mark.asyncio
async def test_resubmitting_supersedes_the_open_request():
    async with SessionLocal() as db:
        w = await world(db)
        qid = await quote_with(db, w, qty=10, discount="12", submit=True)
        first = (await open_requests(db, qid))[0]
        rep = await load_user(db, w["rep"])
        quote = await reload(db, qid, w["rep"])  # resubmission is allowed from SUBMITTED, via the approval API path
        await ApprovalService(db).check_and_submit_quote(SubmitApprovalRequest(quote_id=qid), current_user=rep)
        await db.commit()
        await db.refresh(first)  # the supersede is a bulk update; read the stored status
        assert first.status == "SUPERSEDED"
        with pytest.raises(DomainValidationError):
            await decide(db, w["mgr"], first.id, ApprovalStatus.APPROVED)


@pytest.mark.asyncio
async def test_policy_checker_allows_small_lines_and_asks_for_large_ones_never_denies():
    async with SessionLocal() as db:
        w = await world(db)
        qid = await quote_with(db, w, qty=1, discount="0", submit=False)
        rep = await load_user(db, w["rep"])
        quote = await reload(db, qid, w["rep"])
        checker = ApprovalPolicyChecker(db)

        small = await checker.check_line(rep, quote, AddQuoteItemIn(quote_id=qid, product_id=w["product"], quantity=1))
        assert isinstance(small, Allow)

        deep = await checker.check_line(
            rep, quote, AddQuoteItemIn(quote_id=qid, product_id=w["product"], quantity=10, discount_percent=Decimal("12")),
        )
        assert isinstance(deep, NeedsApproval)
        assert "manager" in deep.reason
        assert not isinstance(deep, Deny)
