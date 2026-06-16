from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional
from uuid import UUID
from datetime import datetime
from ..models.order import OrderStatus


class OrderCreate(BaseModel):
    merchant_id: str = Field(..., min_length=3, max_length=100, example="merchant_001")
    customer_id: str = Field(..., min_length=3, max_length=100, example="cust_123")
    customer_email: str = Field(..., example="customer@example.com")
    amount: float = Field(..., gt=0, le=1_000_000, example=1999.00)
    currency: str = Field(default="INR", min_length=3, max_length=3, example="INR")
    description: Optional[str] = Field(None, max_length=500, example="Purchase of Laptop")

    @validator("currency")
    def currency_uppercase(cls, v):
        return v.upper()

    @validator("amount")
    def round_amount(cls, v):
        return round(v, 2)


class OrderResponse(BaseModel):
    id: UUID
    order_ref: str
    merchant_id: str
    customer_id: str
    customer_email: str
    amount: float
    currency: str
    status: OrderStatus
    description: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class OrderListResponse(BaseModel):
    total: int
    orders: list[OrderResponse]
