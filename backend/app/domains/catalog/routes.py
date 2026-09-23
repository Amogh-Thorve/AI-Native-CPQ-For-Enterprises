from fastapi import APIRouter, Depends, status, Query, UploadFile, File, HTTPException
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.database import get_db
from backend.app.domains.auth.dependencies import PermissionChecker
from backend.app.domains.auth.models import User
from backend.app.domains.catalog.schemas import (
    ProductCreate, ProductUpdate, ProductRead, CategoryCreate, CategoryRead,
    PriceBookCreate, PriceBookRead, PriceBookEntryCreate, PriceBookEntryRead,
    ProductImportResponse
)
from backend.app.domains.catalog.services import CatalogService
from backend.app.domains.catalog.models import Product

router = APIRouter(tags=["product-catalog"])

def sanitize_product_read(product: Product, current_user: User) -> ProductRead:
    user_permissions = {p.name for r in current_user.roles for p in r.permissions}
    has_cost_read = "catalog.cost.read" in user_permissions
    has_margin_read = "catalog.margin.read" in user_permissions
    
    from sqlalchemy.orm import attributes
    state = attributes.instance_state(product)
    
    prod_dict = {
        "id": product.id,
        "sku": product.sku,
        "name": product.name,
        "description": product.description,
        "base_price": product.base_price,
        "cost_price": product.cost_price if has_cost_read else None,
        "currency": product.currency,
        "is_active": product.is_active,
        "billing_type": product.billing_type if product.billing_type in ("MRC", "NRC", "USAGE") else "MRC",
        "category_id": product.category_id,
        "external_crm_id": product.external_crm_id,
    }
    
    if "category" in state.unloaded:
        prod_dict["category"] = None
    else:
        prod_dict["category"] = product.category
        
    read_obj = ProductRead.model_validate(prod_dict)
    
    if not has_cost_read or not has_margin_read:
        read_obj.margin_amount = None
        read_obj.margin_percentage = None
        
    return read_obj

@router.get("/products", response_model=List[ProductRead])
@router.get("/catalog/products", response_model=List[ProductRead])
async def list_products(
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    category_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("catalog.read"))
):
    """
    List all products in catalog. Optionally filter by category.
    """
    service = CatalogService(db)
    products = await service.list_products(limit=limit, offset=offset, category_id=category_id)
    return [sanitize_product_read(p, current_user) for p in products]

@router.post("/products", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
async def create_product(
    schema: ProductCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("catalog.create"))
):
    """
    Onboard a new product to the catalog.
    """
    user_permissions = {p.name for r in current_user.roles for p in r.permissions}
    if schema.cost_price is not None and "catalog.cost.manage" not in user_permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied to modify product cost."
        )
    service = CatalogService(db)
    product = await service.create_product(schema)
    return sanitize_product_read(product, current_user)

@router.get("/products/{product_id}", response_model=ProductRead)
async def get_product(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("catalog.read"))
):
    """
    Get detailed catalog card for a product.
    """
    service = CatalogService(db)
    product = await service.get_product(product_id)
    return sanitize_product_read(product, current_user)

@router.put("/products/{product_id}", response_model=ProductRead)
async def update_product(
    product_id: int,
    schema: ProductUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("catalog.update"))
):
    """
    Update a product's details in the catalog.
    """
    user_permissions = {p.name for r in current_user.roles for p in r.permissions}
    if schema.cost_price is not None and "catalog.cost.manage" not in user_permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied to modify product cost."
        )
    service = CatalogService(db)
    product = await service.update_product(product_id, schema)
    return sanitize_product_read(product, current_user)

@router.patch("/products/{product_id}/archive", response_model=ProductRead)
async def archive_product(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("catalog.archive"))
):
    """
    Deactivate/archive a product.
    """
    service = CatalogService(db)
    product = await service.deactivate_product(product_id)
    return sanitize_product_read(product, current_user)

@router.patch("/products/{product_id}/restore", response_model=ProductRead)
async def restore_product(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("catalog.restore"))
):
    """
    Activate/restore a product.
    """
    service = CatalogService(db)
    product = await service.activate_product(product_id)
    return sanitize_product_read(product, current_user)

@router.get("/categories", response_model=List[CategoryRead])
async def list_categories(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("catalog.read"))
):
    """
    List the structural categories tree.
    """
    service = CatalogService(db)
    return await service.list_categories()

@router.post("/categories", response_model=CategoryRead, status_code=status.HTTP_201_CREATED)
async def create_category(
    schema: CategoryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("catalog.create"))
):
    """
    Add a new product category taxonomy classification.
    """
    service = CatalogService(db)
    return await service.create_category(schema)

@router.get("/price-books", response_model=List[PriceBookRead])
async def list_price_books(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("catalog.pricing.read"))
):
    """
    Get list of all price books.
    """
    service = CatalogService(db)
    return await service.price_book_repo.list()

@router.post("/price-books", response_model=PriceBookRead, status_code=status.HTTP_201_CREATED)
async def create_price_book(
    schema: PriceBookCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("catalog.create"))
):
    """
    Create a new Price Book catalog.
    """
    service = CatalogService(db)
    return await service.create_price_book(schema)

@router.post("/price-books/{price_book_id}/entries", response_model=PriceBookEntryRead, status_code=status.HTTP_201_CREATED)
async def add_price_book_entry(
    price_book_id: int,
    schema: PriceBookEntryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("catalog.update"))
):
    """
    Add or update a custom price mapping inside a Price Book.
    """
    service = CatalogService(db)
    return await service.add_price_book_entry(price_book_id, schema)


@router.post("/products/import", response_model=ProductImportResponse)
async def import_products(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("catalog.import"))
):
    """
    Import products from an Excel (.xlsx) file.
    """
    service = CatalogService(db)
    contents = await file.read()
    user_permissions = {p.name for r in current_user.roles for p in r.permissions}
    has_cost_manage = "catalog.cost.manage" in user_permissions
    return await service.import_products_from_excel(contents, filename=file.filename, has_cost_manage_permission=has_cost_manage)
