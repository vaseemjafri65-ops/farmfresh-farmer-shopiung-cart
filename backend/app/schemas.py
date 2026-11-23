from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

class ProductInput(BaseModel):
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
    quantity: int = Field(ge=1, le=10000)

class CheckoutInput(BaseModel):
    customer_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    address: str = Field(min_length=8, max_length=1000)

class LoginInput(BaseModel):
    email: EmailStr
    password: str
