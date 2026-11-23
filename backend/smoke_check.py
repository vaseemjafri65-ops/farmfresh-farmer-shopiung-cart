"""Run an end-to-end API smoke check against a running local FarmFresh API."""
import json
import os
import urllib.error
import urllib.request
from uuid import uuid4

from app.database import SessionLocal
from app.models import CartItem, Order, OrderItem, Product

BASE = os.getenv("API_BASE", "http://localhost:8000/api")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@farmfresh.com")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "FarmFresh123!")
cart_id = f"smoke-{uuid4()}"
product_id = None
order_number = None
passed = []


def call(method, path, body=None, token=None, cart=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if cart:
        headers["X-Cart-Id"] = cart
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(f"{BASE}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            content = response.read()
            return response.status, json.loads(content) if content else None
    except urllib.error.HTTPError as exc:
        content = exc.read()
        try:
            payload = json.loads(content) if content else None
        except json.JSONDecodeError:
            payload = content.decode(errors="replace")
        return exc.code, payload


def check(name, condition):
    if not condition:
        raise AssertionError(f"FAILED: {name}")
    passed.append(name)
    print(f"PASS {name}")


def expect(method, path, expected, **kwargs):
    status, data = call(method, path, **kwargs)
    check(f"{method} {path} returns {expected}", status == expected)
    return data


try:
    expect("GET", "/health", 200)
    auth = expect("POST", "/auth/login", 200, body={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    token = auth["access_token"]
    expect("POST", "/auth/login", 401, body={"email": ADMIN_EMAIL, "password": "incorrect"})
    expect("GET", "/products?admin=true", 401)

    products = expect("GET", "/products", 200)
    check("public product catalog has active sample products", len(products) >= 1 and all(p["active"] for p in products))
    categories = expect("GET", "/products/categories", 200)
    check("category list is populated", len(categories) >= 1)
    expect("GET", f"/products/{products[0]['id']}", 200)

    product = {
        "name": f"Temporary verification produce {uuid4().hex[:6]}",
        "category": "Smoke verification",
        "farmer_name": "Automation Farm",
        "description": "Disposable record used to verify the requested API routes.",
        "price": 42.5,
        "stock": 17,
        "image_url": "https://example.com/verification.jpg",
        "active": True,
    }
    expect("POST", "/products", 401, body=product)
    created = expect("POST", "/products", 200, body=product, token=token)
    product_id = created["id"]
    check("created product fields are returned", created["name"] == product["name"] and created["stock"] == 17)

    public = expect("GET", "/products?search=Temporary%20verification", 200)
    check("search finds the new product", any(p["id"] == product_id for p in public))
    filtered = expect("GET", "/products?category=Smoke%20verification", 200)
    check("category filter finds the new product", any(p["id"] == product_id for p in filtered))
    expect("GET", f"/products/{product_id}", 200)
    all_products = expect("GET", "/products?admin=true", 200, token=token)
    check("admin catalog contains the new product", any(p["id"] == product_id for p in all_products))

    changed = {**product, "name": f"Updated {product['name']}", "stock": 20}
    updated = expect("PUT", f"/products/{product_id}", 200, body=changed, token=token)
    check("product update persists fields", updated["stock"] == 20 and updated["name"].startswith("Updated"))
    expect("POST", "/products", 422, body={**product, "price": -1}, token=token)

    changed["active"] = False
    expect("PUT", f"/products/{product_id}", 200, body=changed, token=token)
    public = expect("GET", "/products", 200)
    check("inactive product is hidden from customers", all(p["id"] != product_id for p in public))
    expect("GET", f"/products/{product_id}", 404)
    changed["active"] = True
    expect("PUT", f"/products/{product_id}", 200, body=changed, token=token)

    cart = expect("GET", "/cart", 200, cart=cart_id)
    check("new cart starts empty", cart["count"] == 0 and cart["total"] == 0)
    cart = expect("POST", f"/cart/items/{product_id}", 200, body={"quantity": 2}, cart=cart_id)
    check("add to cart calculates subtotal", cart["count"] == 2 and cart["total"] == 85)
    item_id = cart["items"][0]["id"]
    cart = expect("PUT", f"/cart/items/{item_id}", 200, body={"quantity": 3}, cart=cart_id)
    check("cart quantity update recalculates total", cart["count"] == 3 and cart["total"] == 127.5)
    expect("POST", f"/cart/items/{product_id}", 409, body={"quantity": 18}, cart=cart_id)
    expect("PUT", f"/cart/items/{item_id}", 422, body={"quantity": 0}, cart=cart_id)
    expect("DELETE", f"/cart/items/{item_id}", 200, cart=cart_id)
    cart = expect("GET", "/cart", 200, cart=cart_id)
    check("cart removal leaves cart empty", cart["count"] == 0)

    cart = expect("POST", f"/cart/items/{product_id}", 200, body={"quantity": 2}, cart=cart_id)
    invalid_checkout = expect("POST", "/orders/checkout", 422, body={"customer_name": "Test Shopper", "email": "invalid", "address": "12 Market Lane"}, cart=cart_id)
    check("invalid checkout data is rejected", bool(invalid_checkout))
    order = expect("POST", "/orders/checkout", 200, body={"customer_name": "Test Shopper", "email": "shopper@example.com", "address": "12 Market Lane, Sample City"}, cart=cart_id)
    order_number = order["order_number"]
    check("checkout total is correct", order["total"] == 85)
    cart = expect("GET", "/cart", 200, cart=cart_id)
    check("successful checkout clears cart", cart["count"] == 0)
    current = expect("GET", f"/products/{product_id}", 200)
    check("checkout decrements product stock", current["stock"] == 18)
    expect("GET", "/orders", 401)
    orders = expect("GET", "/orders", 200, token=token)
    check("admin order list includes checkout", any(o["order_number"] == order_number for o in orders))

    expect("DELETE", f"/products/{product_id}", 401)
    expect("DELETE", f"/products/{product_id}", 200, token=token)
    product_id = None
    expect("GET", f"/products/{created['id']}", 404)
finally:
    # Remove every test record and leave the sample catalog and inventory untouched.
    with SessionLocal() as db:
        if order_number:
            order_row = db.query(Order).filter(Order.order_number == order_number).first()
            if order_row:
                db.query(OrderItem).filter(OrderItem.order_id == order_row.id).delete(synchronize_session=False)
                db.delete(order_row)
        if product_id:
            db.query(CartItem).filter(CartItem.session_id == cart_id).delete(synchronize_session=False)
            product_row = db.get(Product, product_id)
            if product_row:
                db.delete(product_row)
        db.query(CartItem).filter(CartItem.session_id == cart_id).delete(synchronize_session=False)
        db.commit()

print(f"\n{len(passed)} checks passed; temporary data cleaned up.")
