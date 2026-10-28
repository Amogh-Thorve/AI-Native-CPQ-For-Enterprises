from typing import List, Optional
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from backend.app.domains.catalog.models import Category, Product, PriceBook, PriceBookEntry
from backend.app.domains.catalog.schemas import (
    CategoryCreate, CategoryUpdate,
    ProductCreate, ProductUpdate,
    PriceBookCreate, PriceBookUpdate,
    PriceBookEntryCreate, PriceBookEntryUpdate
)

class CategoryRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, category_id: int) -> Optional[Category]:
        result = await self.db.execute(select(Category).where(Category.id == category_id))
        return result.scalars().first()

    async def get_by_name(self, name: str) -> Optional[Category]:
        result = await self.db.execute(select(Category).where(Category.name == name))
        return result.scalars().first()

    async def list(self) -> List[Category]:
        result = await self.db.execute(select(Category))
        return list(result.scalars().all())

    async def create(self, schema: CategoryCreate) -> Category:
        db_category = Category(**schema.model_dump())
        self.db.add(db_category)
        await self.db.flush()
        return db_category

    async def update(self, db_category: Category, schema: CategoryUpdate) -> Category:
        for field, value in schema.model_dump(exclude_unset=True).items():
            setattr(db_category, field, value)
        self.db.add(db_category)
        await self.db.flush()
        return db_category


class ProductRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, product_id: int) -> Optional[Product]:
        result = await self.db.execute(
            select(Product)
            .where(Product.id == product_id)
            .options(selectinload(Product.category))
        )
        return result.scalars().first()

    async def get_by_sku(self, sku: str) -> Optional[Product]:
        result = await self.db.execute(select(Product).where(Product.sku == sku))
        return result.scalars().first()

    async def get_by_external_id(self, external_crm_id: str) -> Optional[Product]:
        result = await self.db.execute(select(Product).where(Product.external_crm_id == external_crm_id))
        return result.scalars().first()

    async def list(
        self, limit: int = 100, offset: int = 0, category_id: Optional[int] = None,
        search: Optional[str] = None, is_active: Optional[bool] = None
    ) -> List[Product]:
        stmt = select(Product).options(selectinload(Product.category))
        if category_id is not None:
            stmt = stmt.where(Product.category_id == category_id)
        if is_active is not None:
            stmt = stmt.where(Product.is_active.is_(is_active))
        if search and search.strip():
            pattern = f"%{search.strip()}%"
            stmt = stmt.where(or_(Product.name.ilike(pattern), Product.sku.ilike(pattern)))
        stmt = stmt.order_by(Product.id).limit(limit).offset(offset)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def create(self, schema: ProductCreate) -> Product:
        db_product = Product(**schema.model_dump())
        self.db.add(db_product)
        await self.db.flush()
        return db_product

    async def update(self, db_product: Product, schema: ProductUpdate) -> Product:
        for field, value in schema.model_dump(exclude_unset=True).items():
            setattr(db_product, field, value)
        self.db.add(db_product)
        await self.db.flush()
        return db_product

    async def delete(self, db_product: Product) -> None:
        await self.db.delete(db_product)
        await self.db.flush()


class PriceBookRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, price_book_id: int) -> Optional[PriceBook]:
        result = await self.db.execute(
            select(PriceBook)
            .where(PriceBook.id == price_book_id)
            .options(
                selectinload(PriceBook.entries)
                .selectinload(PriceBookEntry.product)
            )
        )
        return result.scalars().first()

    async def get_standard_price_book(self) -> Optional[PriceBook]:
        result = await self.db.execute(
            select(PriceBook)
            .where(PriceBook.is_standard == True)
            .options(
                selectinload(PriceBook.entries)
                .selectinload(PriceBookEntry.product)
            )
        )
        return result.scalars().first()

    async def list(self) -> List[PriceBook]:
        result = await self.db.execute(select(PriceBook))
        return list(result.scalars().all())

    async def create(self, schema: PriceBookCreate) -> PriceBook:
        db_price_book = PriceBook(**schema.model_dump())
        self.db.add(db_price_book)
        await self.db.flush()
        return db_price_book

    async def update(self, db_price_book: PriceBook, schema: PriceBookUpdate) -> PriceBook:
        for field, value in schema.model_dump(exclude_unset=True).items():
            setattr(db_price_book, field, value)
        self.db.add(db_price_book)
        await self.db.flush()
        return db_price_book

    async def add_entry(self, price_book_id: int, schema: PriceBookEntryCreate) -> PriceBookEntry:
        # Check if entry already exists to avoid duplication
        existing = await self.db.execute(
            select(PriceBookEntry)
            .where(
                PriceBookEntry.price_book_id == price_book_id,
                PriceBookEntry.product_id == schema.product_id
            )
        )
        db_entry = existing.scalars().first()
        if db_entry:
            db_entry.custom_price = schema.custom_price
            db_entry.is_active = schema.is_active
        else:
            db_entry = PriceBookEntry(price_book_id=price_book_id, **schema.model_dump())
            self.db.add(db_entry)
        
        await self.db.flush()
        return db_entry
