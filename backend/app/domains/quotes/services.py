from typing import List, Optional, Dict, Any, Set
import uuid
from decimal import Decimal
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.domains.quotes.repositories import QuoteRepository
from backend.app.domains.quotes.models import Quote, QuoteLineItem, QuoteStatus
from backend.app.domains.quotes.schemas import (
    QuoteCreate, QuoteUpdate, QuoteLineItemCreate, QuoteLineItemUpdate
)
from backend.app.domains.pricing.application.services import PricingApplicationService
from backend.app.domains.pricing.api.schemas import CalculatePriceRequest
from backend.app.domains.pricing.domain.enums import PricingMethod
from backend.app.domains.configuration.services import ConfigurationService
from backend.app.domains.catalog.services import CatalogService
from backend.app.domains.customer.services import CustomerService
from backend.app.domains.auth.models import User
from backend.app.core.exceptions import EntityNotFoundError, DomainValidationError

def _status_str(val: Any) -> str:
    if val is None:
        return ""
    if hasattr(val, "value"):
        return str(val.value)
    return str(val)

class QuoteService:
    """
    Business service layer managing enterprise quote lifecycles, lines, and revisions.
    Consumes validated Product Configuration and Pricing Engine calculations.
    """
    def __init__(self, db: AsyncSession):
        self.db = db
        self.quote_repo = QuoteRepository(db)
        self.pricing_service = PricingApplicationService(db)
        self.catalog_service = CatalogService(db)
        self.config_service = ConfigurationService(db)
        self.customer_service = CustomerService(db)

    def _extract_user_context(self, current_user: Optional[User]) -> tuple[List[str], Set[str]]:
        if not current_user or not hasattr(current_user, "roles"):
            return [], set()
        user_roles = [r.name for r in current_user.roles]
        user_permissions = {p.name for r in current_user.roles for p in getattr(r, "permissions", [])}
        return user_roles, user_permissions

    def _check_read_access(self, quote: Quote, current_user: Optional[User]) -> None:
        if not current_user:
            return
        user_roles, _ = self._extract_user_context(current_user)
        # Admins, Executives, Sales Managers have team/org visibility
        if any(role in user_roles for role in ["Administrator", "Executive", "Sales Manager"]):
            return
        # Sales Representatives can only view their own quotes
        if quote.created_by_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Sales Representatives can only view their own quotes."
            )

    def _check_write_access(self, quote: Quote, current_user: Optional[User]) -> None:
        if not current_user:
            return
        user_roles, _ = self._extract_user_context(current_user)
        if any(role in user_roles for role in ["Administrator", "Executive", "Sales Manager"]):
            return
        if quote.created_by_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Sales Representatives can only edit their own draft quotes."
            )

    async def create_quote(
        self,
        creator_id: uuid.UUID,
        schema: QuoteCreate,
        current_user: Optional[User] = None
    ) -> Quote:
        """
        Creates a new quote:
        1. Validates customer exists and is not deleted.
        2. Generates quote number sequence.
        3. Persists quote header shell in DRAFT status.
        4. Adds validated products with Pricing Engine evaluation snapshots.
        5. Computes totals and logs QUOTE_CREATED audit event.
        """
        customer = await self.customer_service.customer_repo.get_by_id(None, schema.customer_id)
        if not customer:
            raise EntityNotFoundError(f"Customer with ID {schema.customer_id} does not exist.")

        quote_number = await self.quote_repo.generate_next_quote_number()
        quote = await self.quote_repo.create(
            creator_id=creator_id,
            schema=schema,
            quote_number=quote_number,
            version=1
        )

        user_roles, user_permissions = self._extract_user_context(current_user)

        # Populate initial line items
        for item in schema.items:
            await self._add_line_item_internal(
                quote=quote,
                item_data=item,
                user_permissions=user_permissions,
                user_id=creator_id,
                user_role=user_roles[0] if user_roles else None
            )

        # Final totals recalculation
        quote = await self.quote_repo.recalculate_totals(quote)

        # Audit event
        await self.quote_repo.log_audit(
            quote_id=quote.id,
            action="QUOTE_CREATED",
            user_id=creator_id,
            user_role=user_roles[0] if user_roles else None,
            after_value={
                "quote_number": quote.quote_number,
                "customer_id": quote.customer_id,
                "status": quote.status.value if hasattr(quote.status, "value") else str(quote.status),
                "total_amount": f"{quote.total_amount:.2f}",
                "line_items_count": len(schema.items)
            }
        )

        return await self.get_quote(quote.id, current_user)

    async def get_quote(self, quote_id: int, current_user: Optional[User] = None) -> Quote:
        quote = await self.quote_repo.get_by_id(quote_id)
        if not quote:
            raise EntityNotFoundError(f"Quote with ID {quote_id} not found.")
        self._check_read_access(quote, current_user)
        return quote

    async def list_quotes(
        self,
        customer_id: Optional[int] = None,
        status: Optional[QuoteStatus] = None,
        search: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        current_user: Optional[User] = None
    ) -> List[Quote]:
        user_roles, _ = self._extract_user_context(current_user)
        filter_created_by: Optional[uuid.UUID] = None
        # Sales Representatives are restricted to their own quotes
        if current_user and not any(r in user_roles for r in ["Administrator", "Executive", "Sales Manager"]):
            filter_created_by = current_user.id

        return await self.quote_repo.list_quotes(
            customer_id=customer_id,
            status=status,
            search=search,
            created_by_id=filter_created_by,
            limit=limit,
            offset=offset
        )

    async def update_quote(
        self,
        quote_id: int,
        schema: QuoteUpdate,
        current_user: Optional[User] = None
    ) -> Quote:
        quote = await self.get_quote(quote_id, current_user)
        self._check_write_access(quote, current_user)

        if quote.status != QuoteStatus.DRAFT:
            raise DomainValidationError("Only quotes in DRAFT status can be modified.")

        before_state = {
            "title": quote.title,
            "description": quote.description,
            "currency": quote.currency,
            "valid_until": quote.valid_until.isoformat() if quote.valid_until else None,
            "notes": quote.notes,
            "status": quote.status.value if hasattr(quote.status, "value") else str(quote.status)
        }

        update_dict = schema.model_dump(exclude_unset=True)
        # Recalculate if totals or currency modified
        updated_quote = await self.quote_repo.update(quote, update_dict)
        updated_quote = await self.quote_repo.recalculate_totals(updated_quote)

        user_roles, _ = self._extract_user_context(current_user)
        await self.quote_repo.log_audit(
            quote_id=quote.id,
            action="QUOTE_UPDATED",
            user_id=current_user.id if current_user else quote.created_by_id,
            user_role=user_roles[0] if user_roles else None,
            before_value=before_state,
            after_value=update_dict
        )

        return updated_quote

    async def delete_quote(self, quote_id: int, current_user: Optional[User] = None) -> None:
        quote = await self.get_quote(quote_id, current_user)
        self._check_write_access(quote, current_user)

        if quote.status != QuoteStatus.DRAFT:
            raise DomainValidationError("Only quotes in DRAFT status can be deleted.")

        await self.quote_repo.delete(quote)

    async def add_item(
        self,
        quote_id: int,
        schema: QuoteLineItemCreate,
        current_user: Optional[User] = None
    ) -> QuoteLineItem:
        quote = await self.get_quote(quote_id, current_user)
        self._check_write_access(quote, current_user)

        if quote.status != QuoteStatus.DRAFT:
            raise DomainValidationError("Cannot add items to a non-draft quote.")

        user_roles, user_permissions = self._extract_user_context(current_user)
        item = await self._add_line_item_internal(
            quote=quote,
            item_data=schema,
            user_permissions=user_permissions,
            user_id=current_user.id if current_user else quote.created_by_id,
            user_role=user_roles[0] if user_roles else None
        )

        await self.quote_repo.recalculate_totals(quote)

        # Audit event
        await self.quote_repo.log_audit(
            quote_id=quote.id,
            action="QUOTE_ITEM_ADDED",
            user_id=current_user.id if current_user else quote.created_by_id,
            user_role=user_roles[0] if user_roles else None,
            after_value={
                "line_item_id": item.id,
                "product_id": item.product_id,
                "sku": item.sku,
                "quantity": item.quantity,
                "unit_price": f"{item.unit_price:.2f}",
                "total_price": f"{item.total_price:.2f}"
            }
        )

        return item

    async def update_item(
        self,
        quote_id: int,
        item_id: int,
        schema: QuoteLineItemUpdate,
        current_user: Optional[User] = None
    ) -> QuoteLineItem:
        quote = await self.get_quote(quote_id, current_user)
        self._check_write_access(quote, current_user)

        if quote.status != QuoteStatus.DRAFT:
            raise DomainValidationError("Cannot update items in a non-draft quote.")

        item = await self.quote_repo.get_line_item(item_id)
        if not item or item.quote_id != quote.id:
            raise EntityNotFoundError(f"Line item with ID {item_id} not found in this quote.")

        before_state = {
            "quantity": item.quantity,
            "discount_percentage": f"{item.discount_percentage:.2f}",
            "unit_price": f"{item.unit_price:.2f}",
            "total_price": f"{item.total_price:.2f}"
        }

        # Apply new quantity or discount
        new_quantity = schema.quantity if schema.quantity is not None else item.quantity
        new_discount = schema.discount_percentage if schema.discount_percentage is not None else item.discount_percentage
        new_config_id = schema.configuration_id if schema.configuration_id is not None else item.configuration_id

        user_roles, user_permissions = self._extract_user_context(current_user)

        # Check configuration session if changed
        config_snapshot = item.configuration_snapshot
        if new_config_id and new_config_id != item.configuration_id:
            config_snapshot = await self._resolve_configuration_snapshot(item.product_id, new_config_id)

        # Recalculate line pricing via Pricing Engine
        price_resp = await self._calculate_item_pricing(
            product_id=item.product_id,
            quantity=new_quantity,
            discount_percentage=new_discount,
            price_book_id=quote.price_book_id,
            user_permissions=user_permissions,
            user_id=current_user.id if current_user else quote.created_by_id,
            user_role=user_roles[0] if user_roles else None
        )

        update_data = {
            "quantity": new_quantity,
            "discount_percentage": price_resp.discount_percent,
            "discount_amount": price_resp.discount_amount,
            "unit_price": price_resp.final_unit_price,
            "total_price": price_resp.total_price,
            "pricing_method": price_resp.pricing_method.value if hasattr(price_resp.pricing_method, "value") else str(price_resp.pricing_method),
            "pricing_breakdown": price_resp.calculation_breakdown,
            "margin_amount": price_resp.margin_amount,
            "margin_percentage": price_resp.margin_percentage,
            "configuration_id": new_config_id,
            "configuration_snapshot": config_snapshot
        }

        updated_item = await self.quote_repo.update_line_item(item, update_data)
        await self.quote_repo.recalculate_totals(quote)

        await self.quote_repo.log_audit(
            quote_id=quote.id,
            action="QUOTE_ITEM_UPDATED",
            user_id=current_user.id if current_user else quote.created_by_id,
            user_role=user_roles[0] if user_roles else None,
            before_value=before_state,
            after_value={
                "quantity": updated_item.quantity,
                "unit_price": f"{updated_item.unit_price:.2f}",
                "total_price": f"{updated_item.total_price:.2f}"
            }
        )

        return updated_item

    async def delete_item(
        self,
        quote_id: int,
        item_id: int,
        current_user: Optional[User] = None
    ) -> None:
        quote = await self.get_quote(quote_id, current_user)
        self._check_write_access(quote, current_user)

        if quote.status != QuoteStatus.DRAFT:
            raise DomainValidationError("Cannot delete items from a non-draft quote.")

        item = await self.quote_repo.get_line_item(item_id)
        if not item or item.quote_id != quote.id:
            raise EntityNotFoundError(f"Line item with ID {item_id} not found in this quote.")

        before_state = {
            "line_item_id": item.id,
            "product_id": item.product_id,
            "sku": item.sku,
            "total_price": f"{item.total_price:.2f}"
        }

        if hasattr(quote, "items") and quote.items and item in quote.items:
            quote.items.remove(item)

        await self.quote_repo.delete_line_item(item)
        await self.quote_repo.recalculate_totals(quote)

        user_roles, _ = self._extract_user_context(current_user)
        await self.quote_repo.log_audit(
            quote_id=quote.id,
            action="QUOTE_ITEM_REMOVED",
            user_id=current_user.id if current_user else quote.created_by_id,
            user_role=user_roles[0] if user_roles else None,
            before_value=before_state
        )

    async def submit_quote(self, quote_id: int, current_user: Optional[User] = None) -> Quote:
        quote = await self.get_quote(quote_id, current_user)
        self._check_write_access(quote, current_user)

        status_str = _status_str(quote.status)
        if status_str != QuoteStatus.DRAFT.value:
            raise DomainValidationError(f"Only quotes in DRAFT status can be submitted. Current status: {status_str}.")

        if not quote.items or len(quote.items) == 0:
            raise DomainValidationError("Cannot submit an empty quote. Please add at least one product.")

        quote.status = QuoteStatus.SUBMITTED
        self.db.add(quote)
        await self.db.flush()

        user_roles, _ = self._extract_user_context(current_user)
        await self.quote_repo.log_audit(
            quote_id=quote.id,
            action="QUOTE_SUBMITTED",
            user_id=current_user.id if current_user else quote.created_by_id,
            user_role=user_roles[0] if user_roles else None,
            after_value={"status": _status_str(quote.status), "grand_total": f"{quote.total_amount:.2f}"}
        )

        return quote

    async def cancel_quote(self, quote_id: int, current_user: Optional[User] = None) -> Quote:
        quote = await self.get_quote(quote_id, current_user)
        self._check_write_access(quote, current_user)

        status_str = _status_str(quote.status)
        if status_str in (QuoteStatus.CANCELLED.value, QuoteStatus.REJECTED.value):
            raise DomainValidationError(f"Quote is already {status_str}.")

        before_status = status_str
        quote.status = QuoteStatus.CANCELLED
        self.db.add(quote)
        await self.db.flush()

        user_roles, _ = self._extract_user_context(current_user)
        await self.quote_repo.log_audit(
            quote_id=quote.id,
            action="QUOTE_CANCELLED",
            user_id=current_user.id if current_user else quote.created_by_id,
            user_role=user_roles[0] if user_roles else None,
            before_value={"status": before_status},
            after_value={"status": _status_str(quote.status)}
        )

        return quote

    async def revise_quote(self, quote_id: int, current_user: Optional[User] = None) -> Quote:
        """
        Creates a new version (revision) of an existing quote.
        Clones properties, increments version count, sets status back to DRAFT,
        and links to the parent quote ID for history audits.
        Preserves frozen pricing snapshots.
        """
        parent_quote = await self.get_quote(quote_id, current_user)

        next_version = parent_quote.version + 1
        creator_id = current_user.id if current_user else parent_quote.created_by_id

        schema = QuoteCreate(
            customer_id=parent_quote.customer_id,
            title=f"{parent_quote.title or parent_quote.quote_number} (Rev {next_version})",
            description=parent_quote.description,
            currency=parent_quote.currency,
            valid_until=parent_quote.valid_until,
            notes=parent_quote.notes,
            price_book_id=parent_quote.price_book_id,
            external_opportunity_id=parent_quote.external_opportunity_id,
            items=[]
        )

        new_quote = await self.quote_repo.create(
            creator_id=creator_id,
            schema=schema,
            quote_number=parent_quote.quote_number,
            version=next_version,
            parent_id=parent_quote.id
        )

        # Clone line items with frozen pricing snapshots
        for item in parent_quote.items:
            await self.quote_repo.add_line_item(
                quote_id=new_quote.id,
                product_id=item.product_id,
                product_name=item.product_name,
                sku=item.sku,
                billing_type=item.billing_type,
                currency=item.currency,
                quantity=item.quantity,
                unit_price=item.unit_price,
                discount_percentage=item.discount_percentage,
                discount_amount=item.discount_amount,
                total_price=item.total_price,
                pricing_method=item.pricing_method,
                pricing_breakdown=item.pricing_breakdown,
                margin_amount=item.margin_amount,
                margin_percentage=item.margin_percentage,
                configuration_id=item.configuration_id,
                configuration_snapshot=item.configuration_snapshot
            )

        new_quote = await self.quote_repo.recalculate_totals(new_quote)

        user_roles, _ = self._extract_user_context(current_user)
        await self.quote_repo.log_audit(
            quote_id=new_quote.id,
            action="QUOTE_CREATED",
            user_id=creator_id,
            user_role=user_roles[0] if user_roles else None,
            after_value={
                "quote_number": new_quote.quote_number,
                "version": new_quote.version,
                "parent_quote_id": parent_quote.id,
                "status": _status_str(new_quote.status)
            }
        )

        return new_quote

    # --- Internal Helpers ---

    async def _resolve_configuration_snapshot(self, product_id: int, configuration_id: str) -> Dict[str, Any]:
        """
        Validates that a configuration session exists and is valid.
        Does not perform configuration validation inside Quote Builder.
        Consumes the validated result.
        """
        try:
            sess_uuid = uuid.UUID(configuration_id)
            session = await self.config_service.get_session(sess_uuid)
            if session.product_id != product_id:
                raise DomainValidationError(f"Configuration session does not belong to product ID {product_id}.")
            if not session.is_valid:
                raise DomainValidationError(f"Configuration session {configuration_id} is invalid. Complete validation before adding to quote.")
            return {"session_id": str(session.id), "selections": session.selections}
        except ValueError:
            return {"reference": configuration_id}

    async def _calculate_item_pricing(
        self,
        product_id: int,
        quantity: int,
        discount_percentage: Decimal,
        price_book_id: Optional[int],
        user_permissions: Set[str],
        user_id: Optional[uuid.UUID],
        user_role: Optional[str]
    ):
        """
        Invokes PricingApplicationService dynamically.
        Never duplicates pricing formulas.
        """
        setting = await self.pricing_service.setting_repo.get_by_product_id(product_id)
        method = None
        if discount_percentage > Decimal("0.00"):
            if not setting or setting.pricing_method in (PricingMethod.STANDARD.value, PricingMethod.LINE_DISCOUNT.value):
                method = PricingMethod.LINE_DISCOUNT

        price_req = CalculatePriceRequest(
            product_id=product_id,
            quantity=quantity,
            discount_percent=discount_percentage,
            pricing_method=method,
            price_book_id=price_book_id
        )

        return await self.pricing_service.calculate_price(
            request=price_req,
            user_permissions=user_permissions | {"pricing.margin.view", "pricing.cost.view"},
            user_id=user_id,
            user_role=user_role
        )

    async def _add_line_item_internal(
        self,
        quote: Quote,
        item_data: QuoteLineItemCreate,
        user_permissions: Set[str],
        user_id: Optional[uuid.UUID],
        user_role: Optional[str]
    ) -> QuoteLineItem:
        product = await self.catalog_service.get_product(item_data.product_id)
        if not product:
            raise EntityNotFoundError(f"Product ID {item_data.product_id} not found.")
        if not product.is_active:
            raise DomainValidationError(f"Product '{product.name}' is inactive and cannot be quoted.")

        config_snapshot = item_data.configuration_snapshot
        if item_data.configuration_id and not config_snapshot:
            config_snapshot = await self._resolve_configuration_snapshot(product.id, item_data.configuration_id)

        price_resp = await self._calculate_item_pricing(
            product_id=product.id,
            quantity=item_data.quantity,
            discount_percentage=item_data.discount_percentage,
            price_book_id=quote.price_book_id,
            user_permissions=user_permissions,
            user_id=user_id,
            user_role=user_role
        )

        return await self.quote_repo.add_line_item(
            quote_id=quote.id,
            product_id=product.id,
            product_name=product.name,
            sku=product.sku,
            billing_type=price_resp.billing_type or getattr(product, "billing_type", "MRC") or "MRC",
            currency=quote.currency,
            quantity=item_data.quantity,
            unit_price=price_resp.final_unit_price,
            discount_percentage=price_resp.discount_percent,
            discount_amount=price_resp.discount_amount,
            total_price=price_resp.total_price,
            pricing_method=price_resp.pricing_method.value if hasattr(price_resp.pricing_method, "value") else str(price_resp.pricing_method),
            pricing_breakdown=price_resp.calculation_breakdown,
            margin_amount=price_resp.margin_amount,
            margin_percentage=price_resp.margin_percentage,
            configuration_id=item_data.configuration_id,
            configuration_snapshot=config_snapshot
        )
