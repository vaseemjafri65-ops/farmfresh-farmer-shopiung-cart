from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

class ProductInput(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{
        "name": "Heirloom tomatoes", "category": "Vegetables", "farmer_name": "Maya’s Garden",
        "description": "Freshly picked heirloom tomatoes.", "price": 120, "stock": 24,
        "image_url": "https://example.com/tomatoes.jpg", "active": True,
    }]})
    name: str = Field(min_length=2, max_length=140)
    category: str = Field(min_length=2, max_length=80)
    farmer_name: str = Field(min_length=2, max_length=120)
    description: str = Field(default="", max_length=3000)
    price: float = Field(gt=0, le=1000000)
    stock: int = Field(ge=0, le=1000000)
    image_url: str = Field(default="", max_length=600)
    active: bool = True

    @field_validator("image_url")
    @classmethod
    def valid_image_url(cls, value: str) -> str:
        value = value.strip()
        if value and not value.startswith(("https://", "http://")):
            raise ValueError("Image URL must start with http:// or https://")
        return value

class ProductOut(ProductInput):
    id: int
    model_config = ConfigDict(from_attributes=True)

class QuantityInput(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"quantity": 2}]})
    quantity: int = Field(ge=1, le=10000)

class CheckoutInput(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{
        "customer_name": "Test Shopper", "email": "shopper@example.com",
        "address": "12 Market Lane, Sample City",
    }]})
    customer_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    address: str = Field(min_length=8, max_length=1000)

class LoginInput(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{
        "email": "admin@farmfresh.com", "password": "FarmFresh123!",
    }]})
    email: EmailStr
    password: str

class HealthOut(BaseModel):
    status: str

class LoginOut(BaseModel):
    access_token: str
    token_type: str

class CartLineOut(BaseModel):
    id: int
    quantity: int
    product: ProductOut
    line_total: float

class CartOut(BaseModel):
    items: list[CartLineOut]
    total: float
    count: int

class CartWithIdOut(CartOut):
    cart_id: str

class OkOut(BaseModel):
    ok: bool

class CheckoutOut(BaseModel):
    order_number: str
    total: float
    created_at: datetime

class OrderItemOut(BaseModel):
    name: str
    quantity: int
    unit_price: float

class OrderOut(BaseModel):
    order_number: str
    customer_name: str
    email: EmailStr
    address: str
    total: float
    created_at: datetime
    items: list[OrderItemOut]
