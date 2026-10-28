from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.core.exceptions import EntityNotFoundError
from backend.app.domains.auth.dependencies import get_current_user
from backend.app.domains.auth.models import User
from backend.app.domains.tax.models import TaxRate

router = APIRouter(prefix="/tax-rates", tags=["tax"])

ADMIN_ROLES = {"Administrator", "Executive"}


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if not ADMIN_ROLES.intersection(r.name for r in current_user.roles):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only Administrators and Executives can manage tax rates.")
    return current_user


class TaxRateBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    country: Optional[str] = Field(default=None, max_length=100)
    region: Optional[str] = Field(default=None, max_length=100)
    rate_percent: Decimal = Field(..., ge=0, le=100)
    is_default: bool = False
    is_active: bool = True


class TaxRateRead(TaxRateBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


@router.get("/", response_model=List[TaxRateRead])
async def list_tax_rates(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    return list((await db.execute(select(TaxRate).order_by(TaxRate.country, TaxRate.region, TaxRate.id))).scalars().all())


async def _single_default(db: AsyncSession, keep_id: int) -> None:
    await db.execute(update(TaxRate).where(TaxRate.id != keep_id).values(is_default=False))


@router.post("/", response_model=TaxRateRead, status_code=status.HTTP_201_CREATED)
async def create_tax_rate(body: TaxRateBase, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_admin)):
    rate = TaxRate(**body.model_dump())
    db.add(rate)
    await db.flush()
    if rate.is_default:
        await _single_default(db, rate.id)
    await db.commit()
    return rate


@router.put("/{rate_id}", response_model=TaxRateRead)
async def update_tax_rate(rate_id: int, body: TaxRateBase, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_admin)):
    rate = await db.get(TaxRate, rate_id)
    if not rate:
        raise EntityNotFoundError(f"Tax rate {rate_id} not found.")
    for k, v in body.model_dump().items():
        setattr(rate, k, v)
    await db.flush()
    if rate.is_default:
        await _single_default(db, rate.id)
    await db.commit()
    return rate


@router.delete("/{rate_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tax_rate(rate_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_admin)):
    rate = await db.get(TaxRate, rate_id)
    if not rate:
        raise EntityNotFoundError(f"Tax rate {rate_id} not found.")
    await db.delete(rate)
    await db.commit()
