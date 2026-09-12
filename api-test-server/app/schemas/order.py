"""订单接口的输入和输出 Schema。"""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

OrderStatus = Literal["CREATED", "PAID", "CANCELLED"]


class OrderCreate(BaseModel):
    """下单输入只接受商品和数量；用户与金额由服务端决定。"""

    product_id: int = Field(gt=0)
    quantity: int = Field(gt=0, le=10_000)


class OrderResponse(BaseModel):
    """订单持久化结果的响应模型。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    product_id: int
    quantity: int
    total_amount: Decimal
    status: OrderStatus
    created_at: datetime
