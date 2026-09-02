from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ProductStatus = Literal["ACTIVE", "INACTIVE"]


class ProductCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=100)
    price: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    stock: int = Field(ge=0)
    status: ProductStatus = "ACTIVE"

    @field_validator("name")
    @classmethod
    def reject_html_markup(cls, value: str) -> str:
        if "<" in value or ">" in value:
            raise ValueError("name must not contain HTML markup")
        return value


class ProductUpdate(ProductCreate):
    """Full replacement payload used by PUT /api/products/{id}."""


class ProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    price: Decimal
    stock: int
    status: ProductStatus
    created_at: datetime
