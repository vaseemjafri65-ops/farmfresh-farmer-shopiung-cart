import os, secrets
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4
from fastapi import FastAPI, Depends, HTTPException, Header, Path
from fastapi.middleware.cors import CORSMiddleware
from jose import jwt
from passlib.context import CryptContext
from sqlalchemy import select, func
from sqlalchemy.orm import Session, joinedload
from .database import Base, engine, get_db
from .models import Product, CartItem, Order, OrderItem
from .schemas import ProductInput, ProductOut, QuantityInput, CheckoutInput, LoginInput, HealthOut, LoginOut, CartOut, CartWithIdOut, OkOut, CheckoutOut, OrderOut

Base.metadata.create_all(bind=engine)
from .database import SessionLocal
from .models import Product as SeedProduct
with SessionLocal() as seed_db:
    if seed_db.scalar(select(func.count(Product.id))) == 0:
        seed_db.add_all([
            SeedProduct(name="Heirloom tomatoes", category="Vegetables", farmer_name="Maya’s Garden", description="Sun-ripened, richly coloured heirloom tomatoes, picked fresh this morning.", price=120, stock=24, image_url="https://images.unsplash.com/photo-1546094096-0df4bcaaa337?auto=format&fit=crop&w=900&q=85"),
            SeedProduct(name="Kashmir apples", category="Fruits", farmer_name="Valley Roots Co.", description="Crisp, sweet apples grown on the foothills of the Himalayas.", price=180, stock=18, image_url="https://images.unsplash.com/photo-1560806887-1e4cd0b6cbd6?auto=format&fit=crop&w=900&q=85"),
            SeedProduct(name="Baby potatoes", category="Vegetables", farmer_name="Green Acre Farm", description="Tender little potatoes with delicate skins. Perfect for roasting.", price=80, stock=35, image_url="https://images.unsplash.com/photo-1518977676601-b53f82aba655?auto=format&fit=crop&w=900&q=85"),
            SeedProduct(name="Rainbow carrots", category="Vegetables", farmer_name="Maya’s Garden", description="A colourful bunch of sweet, soil-grown carrots.", price=95, stock=12, image_url="https://images.unsplash.com/photo-1445282768818-728615cc910a?auto=format&fit=crop&w=900&q=85"),
            SeedProduct(name="Fresh basil bunch", category="Herbs", farmer_name="Green Acre Farm", description="Fragrant basil, gathered by hand for your kitchen.", price=60, stock=20, image_url="https://images.unsplash.com/photo-1618375569909-3c8616cf7733?auto=format&fit=crop&w=900&q=85"),
            SeedProduct(name="Sweet strawberries", category="Fruits", farmer_name="Berry Patch Farm", description="Small-batch berries, naturally sweet and picked at their ripest.", price=220, stock=10, image_url="https://images.unsplash.com/photo-1464965911861-746a04b4bca6?auto=format&fit=crop&w=900&q=85"),
        ])
        seed_db.commit()
app = FastAPI(title="FarmFresh Market API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173").split(","), allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
JWT_SECRET = os.getenv("JWT_SECRET", "development-secret-change-me")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@farmfresh.com").lower()
ADMIN_HASH = pwd.hash(os.getenv("ADMIN_PASSWORD", "FarmFresh123!"))

def admin_guard(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Admin sign-in required")
    try:
        payload = jwt.decode(authorization[7:], JWT_SECRET, algorithms=["HS256"])
        if payload.get("sub") != ADMIN_EMAIL: raise ValueError()
    except Exception:
        raise HTTPException(401, "Your session has expired. Please sign in again.")

def cart_payload(db: Session, sid: str):
    rows = db.scalars(select(CartItem).options(joinedload(CartItem.product)).where(CartItem.session_id == sid)).all()
    items = [{"id": r.id, "quantity": r.quantity, "product": ProductOut.model_validate(r.product).model_dump(), "line_total": round(float(r.product.price) * r.quantity, 2)} for r in rows]
    return {"items": items, "total": round(sum(x["line_total"] for x in items), 2), "count": sum(x["quantity"] for x in items)}

@app.get("/api/health", response_model=HealthOut)
def health(): return {"status": "ok"}

@app.post("/api/auth/login", response_model=LoginOut)
def login(data: LoginInput):
    if data.email.lower() != ADMIN_EMAIL or not pwd.verify(data.password, ADMIN_HASH): raise HTTPException(401, "Email or password is incorrect")
    return {"access_token": jwt.encode({"sub": ADMIN_EMAIL, "exp": datetime.now(timezone.utc) + timedelta(hours=12)}, JWT_SECRET, algorithm="HS256"), "token_type": "bearer"}

@app.get("/api/products", response_model=list[ProductOut])
def products(search: str = "", category: str = "", admin: bool = False, authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    if admin: admin_guard(authorization)
    q = select(Product).order_by(Product.created_at.desc())
    if not admin: q = q.where(Product.active.is_(True))
    if search.strip(): q = q.where(Product.name.ilike(f"%{search.strip()}%"))
    if category.strip() and category != "All": q = q.where(Product.category == category)
    return db.scalars(q).all()

@app.get("/api/products/categories", response_model=list[str])
def categories(db: Session = Depends(get_db)):
    return db.scalars(select(Product.category).where(Product.active.is_(True)).distinct().order_by(Product.category)).all()

@app.get("/api/products/{product_id}", response_model=ProductOut)
def get_product(product_id: int, admin: bool = False, authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    if admin: admin_guard(authorization)
    product = db.get(Product, product_id)
    if not product or (not product.active and not admin): raise HTTPException(404, "Product not found")
    return product

@app.post("/api/products", response_model=ProductOut, dependencies=[Depends(admin_guard)])
def create_product(data: ProductInput, db: Session = Depends(get_db)):
    product = Product(**data.model_dump()); db.add(product); db.commit(); db.refresh(product); return product

@app.put("/api/products/{product_id}", response_model=ProductOut, dependencies=[Depends(admin_guard)])
def update_product(product_id: int, data: ProductInput, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if not product: raise HTTPException(404, "Product not found")
    for key, value in data.model_dump().items(): setattr(product, key, value)
    db.commit(); db.refresh(product); return product

@app.delete("/api/products/{product_id}", response_model=OkOut, dependencies=[Depends(admin_guard)])
def delete_product(product_id: int = Path(..., description="Required. Use an existing product ID from GET /api/products."), db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if not product: raise HTTPException(404, "Product not found")
    db.delete(product); db.commit(); return {"ok": True}

@app.get("/api/cart", response_model=CartOut)
def get_cart(x_cart_id: str | None = Header(default=None), db: Session = Depends(get_db)):
    return cart_payload(db, x_cart_id or "")

@app.post("/api/cart/items/{product_id}", response_model=CartWithIdOut)
def add_cart(product_id: int, data: QuantityInput, x_cart_id: str | None = Header(default=None), db: Session = Depends(get_db)):
    sid = x_cart_id or str(uuid4()); product = db.get(Product, product_id)
    if not product or not product.active: raise HTTPException(404, "Product is unavailable")
    row = db.scalar(select(CartItem).where(CartItem.session_id == sid, CartItem.product_id == product_id))
    new_qty = (row.quantity if row else 0) + data.quantity
    if new_qty > product.stock: raise HTTPException(409, f"Only {product.stock} available")
    if row: row.quantity = new_qty
    else: db.add(CartItem(session_id=sid, product_id=product_id, quantity=data.quantity))
    db.commit(); return {**cart_payload(db, sid), "cart_id": sid}

@app.put("/api/cart/items/{item_id}", response_model=CartOut)
def update_cart(item_id: int, data: QuantityInput, x_cart_id: str | None = Header(default=None), db: Session = Depends(get_db)):
    row = db.scalar(select(CartItem).options(joinedload(CartItem.product)).where(CartItem.id == item_id, CartItem.session_id == (x_cart_id or "")))
    if not row: raise HTTPException(404, "Cart item not found")
    if data.quantity > row.product.stock: raise HTTPException(409, f"Only {row.product.stock} available")
    row.quantity = data.quantity; db.commit(); return cart_payload(db, row.session_id)

@app.delete("/api/cart/items/{item_id}", response_model=CartOut)
def remove_cart(item_id: int, x_cart_id: str | None = Header(default=None), db: Session = Depends(get_db)):
    row = db.scalar(select(CartItem).where(CartItem.id == item_id, CartItem.session_id == (x_cart_id or "")))
    if row: db.delete(row); db.commit()
    return cart_payload(db, x_cart_id or "")

@app.post("/api/orders/checkout", response_model=CheckoutOut)
def checkout(data: CheckoutInput, x_cart_id: str | None = Header(default=None), db: Session = Depends(get_db)):
    sid = x_cart_id or ""; rows = db.scalars(select(CartItem).options(joinedload(CartItem.product)).where(CartItem.session_id == sid).with_for_update()).all()
    if not rows: raise HTTPException(400, "Your cart is empty")
    for row in rows:
        if not row.product.active or row.quantity > row.product.stock: raise HTTPException(409, f"Stock changed for {row.product.name}. Please review your cart.")
    total = sum((Decimal(row.product.price) * row.quantity for row in rows), Decimal("0.00"))
    order = Order(order_number=f"FF-{secrets.token_hex(4).upper()}", customer_name=data.customer_name, email=data.email, address=data.address, total=total)
    for row in rows:
        row.product.stock -= row.quantity
        order.items.append(OrderItem(product_id=row.product_id, product_name=row.product.name, unit_price=row.product.price, quantity=row.quantity))
        db.delete(row)
    db.add(order); db.commit(); db.refresh(order)
    return {"order_number": order.order_number, "total": float(order.total), "created_at": order.created_at}

@app.get("/api/orders", response_model=list[OrderOut], dependencies=[Depends(admin_guard)])
def list_orders(db: Session = Depends(get_db)):
    orders = db.scalars(select(Order).options(joinedload(Order.items)).order_by(Order.created_at.desc())).unique().all()
    return [{"order_number": o.order_number, "customer_name": o.customer_name, "email": o.email, "address": o.address, "total": float(o.total), "created_at": o.created_at, "items": [{"name": i.product_name, "quantity": i.quantity, "unit_price": float(i.unit_price)} for i in o.items]} for o in orders]
