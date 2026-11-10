from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from peewee import fn
from contextlib import asynccontextmanager

from database import db, init_db
from models import Medicine, Sale


# ============================================================
# Schemaهای Pydantic (برای ورودی/خروجی)
# ============================================================

class MedicineIn(BaseModel):
    name:  str = Field(..., min_length=1, max_length=150)
    price: int = Field(..., ge=0)
    stock: int = Field(0, ge=0)


class MedicineOut(BaseModel):
    id: int
    name: str
    price: int
    stock: int


class SellIn(BaseModel):
    quantity: int = Field(..., gt=0)


class SaleOut(BaseModel):
    id: int
    medicine_id: int
    medicine_name: str
    quantity: int
    total: int
    sold_at: str


# ============================================================
# Lifespan: اتصال/قطع دیتابیس هنگام start/stop
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield
    if not db.is_closed():
        db.close()


app = FastAPI(
    title="Pharmacy API",
    description="سیستم مدیریت داروخانه با FastAPI + Peewee",
    version="1.0.0",
    lifespan=lifespan,
)


# ============================================================
# Medicine endpoints
# ============================================================

@app.get("/medicines", response_model=list[MedicineOut], tags=["medicines"])
def list_medicines():
    """لیست همه داروها"""
    return [
        {"id": m.id, "name": m.name, "price": m.price, "stock": m.stock}
        for m in Medicine.select().order_by(Medicine.name)
    ]


@app.post("/medicines", response_model=MedicineOut, status_code=201, tags=["medicines"])
def add_medicine(data: MedicineIn):
    """افزودن دارو جدید"""
    med = Medicine.create(name=data.name, price=data.price, stock=data.stock)
    return {"id": med.id, "name": med.name, "price": med.price, "stock": med.stock}


@app.get("/medicines/{medicine_id}", response_model=MedicineOut, tags=["medicines"])
def get_medicine(medicine_id: int):
    """دریافت یک دارو با ID"""
    med = Medicine.get_or_none(Medicine.id == medicine_id)
    if med is None:
        raise HTTPException(404, "دارو یافت نشد")
    return {"id": med.id, "name": med.name, "price": med.price, "stock": med.stock}


# ============================================================
# Sale endpoints
# ============================================================

@app.post("/medicines/{medicine_id}/sell", response_model=SaleOut, status_code=201, tags=["sales"])
def sell(medicine_id: int, data: SellIn):
    """فروش دارو + کاهش اتمیک موجودی"""
    with db.atomic():
        med = Medicine.get_or_none(Medicine.id == medicine_id)
        if med is None:
            raise HTTPException(404, "دارو یافت نشد")
        if med.stock < data.quantity:
            raise HTTPException(400, f"موجودی کافی نیست (موجودی: {med.stock})")

        med.stock -= data.quantity
        med.save()

        sale = Sale.create(
            medicine=med,
            quantity=data.quantity,
            total=med.price * data.quantity,
        )

    return {
        "id": sale.id,
        "medicine_id": med.id,
        "medicine_name": med.name,
        "quantity": sale.quantity,
        "total": sale.total,
        "sold_at": sale.sold_at.isoformat(timespec="seconds"),
    }


@app.get("/sales", response_model=list[SaleOut], tags=["sales"])
def list_sales(limit: int = 50):
    """لیست آخرین فروش‌ها"""
    sales = (Sale.select(Sale, Medicine)
                 .join(Medicine)
                 .order_by(Sale.sold_at.desc())
                 .limit(limit))
    return [
        {
            "id": s.id,
            "medicine_id": s.medicine.id,
            "medicine_name": s.medicine.name,
            "quantity": s.quantity,
            "total": s.total,
            "sold_at": s.sold_at.isoformat(timespec="seconds"),
        }
        for s in sales
    ]


# ============================================================
# Report endpoints
# ============================================================

@app.get("/reports/revenue", tags=["reports"])
def total_revenue():
    """مجموع کل فروش"""
    total = Sale.select(fn.SUM(Sale.total)).scalar() or 0
    return {"total_revenue": total}


@app.get("/reports/top", tags=["reports"])
def top_selling(limit: int = 5):
    """پرفروش‌ترین داروها"""
    query = (
        Sale.select(
            Medicine.name,
            fn.SUM(Sale.quantity).alias("total_qty"),
            fn.SUM(Sale.total).alias("total_amount"),
        )
        .join(Medicine)
        .group_by(Medicine.id)
        .order_by(fn.SUM(Sale.quantity).desc())
        .limit(limit)
    )
    return [
        {"name": r.name, "quantity": r.total_qty, "amount": r.total_amount}
        for r in query
    ]


@app.get("/reports/low-stock", tags=["reports"])
def low_stock(threshold: int = 10):
    """داروهای رو به اتمام"""
    return [
        {"id": m.id, "name": m.name, "stock": m.stock}
        for m in Medicine.select()
                          .where(Medicine.stock < threshold)
                          .order_by(Medicine.stock)
    ]