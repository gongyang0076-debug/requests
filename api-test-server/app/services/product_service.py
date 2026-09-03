from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Order, Product


class ProductNotFoundError(ValueError):
    """Raised when a requested product does not exist."""


class ProductInUseError(ValueError):
    """Raised when an existing order still references a product."""


def create_product(
    session: Session,
    *,
    name: str,
    price: Decimal,
    stock: int,
    status: str,
) -> Product:
    product = Product(name=name, price=price, stock=stock, status=status)
    session.add(product)
    session.commit()
    session.refresh(product)
    return product


def get_product(session: Session, product_id: int) -> Product:
    product = session.get(Product, product_id)
    if product is None:
        raise ProductNotFoundError("Product not found")
    return product


def list_products(session: Session) -> list[Product]:
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
    product = get_product(session, product_id)
    product.name = name
    product.price = price
    product.stock = stock
    product.status = status
    session.commit()
    session.refresh(product)
    return product


def delete_product(session: Session, product_id: int) -> None:
    product = get_product(session, product_id)
    existing_order_id = session.scalar(
        select(Order.id).where(Order.product_id == product_id).limit(1)
    )
    if existing_order_id is not None:
        raise ProductInUseError(
            "Product cannot be deleted because it has existing orders"
        )

    session.delete(product)
    session.commit()
