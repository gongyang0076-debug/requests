"""orders 表的 SQLAlchemy 映射。"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Order(Base):
    """订单记录，关联用户和商品，并保存订单创建时计算出的总金额。"""

    __tablename__ = "orders"
    # 数据库层重复保护数量、金额和状态枚举，避免服务层遗漏造成脏数据。
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_orders_quantity_positive"),
        CheckConstraint("total_amount > 0", name="ck_orders_total_amount_positive"),
        CheckConstraint(
            "status IN ('CREATED', 'PAID', 'CANCELLED')",
            name="ck_orders_status_valid",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    quantity: Mapped[int] = mapped_column()
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    status: Mapped[str] = mapped_column(
        String(20),
        default="CREATED",
        server_default=text("'CREATED'"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
    )
