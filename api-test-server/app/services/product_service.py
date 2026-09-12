"""商品 CRUD 业务规则与删除冲突语义。"""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Order, Product


class ProductNotFoundError(ValueError):
    """请求的商品不存在。"""


class ProductInUseError(ValueError):
    """商品仍被订单引用，不能删除。"""


def create_product(
    session: Session,
    *,
    name: str,
    price: Decimal,
    stock: int,
    status: str,
) -> Product:
    """创建商品并刷新对象，以获得数据库生成的 ID 和时间字段。"""

    product = Product(name=name, price=price, stock=stock, status=status)
    session.add(product)
    session.commit()
    session.refresh(product)
    return product


def get_product(session: Session, product_id: int) -> Product:
    """按主键获取商品；不存在时抛业务异常而不是返回 None。"""

    product = session.get(Product, product_id)
    if product is None:
        raise ProductNotFoundError("Product not found")
    return product


def list_products(session: Session) -> list[Product]:
    """按 ID 升序返回当前全部商品，便于测试得到稳定顺序。"""

    return list(session.scalars(select(Product).order_by(Product.id)))


def update_product(
    session: Session,
    product_id: int,
    *,
    name: str,
    price: Decimal,
    stock: int,
    status: str,
) -> Product:
    """执行 PUT 语义的完整商品更新。"""

    product = get_product(session, product_id)
    product.name = name
    product.price = price
    product.stock = stock
    product.status = status
    session.commit()
    session.refresh(product)
    return product


def delete_product(session: Session, product_id: int) -> None:
    """删除没有订单引用的商品。

    主动检查关联订单并抛出 ProductInUseError，让 Router 返回 409；外键约束
    仍保留为并发或遗漏路径下的最终数据保护。
    """

    product = get_product(session, product_id)
    existing_order_id = session.scalar(
        select(Order.id).where(Order.product_id == product_id).limit(1)
    )
    if existing_order_id is not None:
        raise ProductInUseError(
            "Product cannot be deleted because it has existing orders"
        )

    # 只有确认没有订单引用后才删除，避免把数据库 IntegrityError 暴露给调用方。
    session.delete(product)
    session.commit()
