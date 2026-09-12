"""products 表的 SQLAlchemy 映射与数据库级数据约束。"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, Numeric, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Product(Base):
    """可下单商品；price 和 stock 同时受数据库 CheckConstraint 保护。"""

    __tablename__ = "products"
    # Pydantic 负责接口入口校验；这些约束防止绕过 API 的非法数据库写入。
    __table_args__ = (
        CheckConstraint("price > 0", name="ck_products_price_positive"),
        CheckConstraint("stock >= 0", name="ck_products_stock_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))  # 金额使用定点小数
    stock: Mapped[int] = mapped_column()
    status: Mapped[str] = mapped_column(
        String(20),
        default="ACTIVE",
        server_default=text("'ACTIVE'"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
    )
