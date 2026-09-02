from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Order, Product
from app.services.product_service import ProductNotFoundError


class OrderNotFoundError(ValueError):
    """Raised when an order does not exist for the authenticated user."""


class InsufficientStockError(ValueError):
    """Raised when the requested quantity exceeds available stock."""


class ProductUnavailableError(ValueError):
    """Raised when an inactive product cannot be ordered."""


class InvalidOrderStateError(ValueError):
    """Raised when an order state transition is not allowed."""


def create_order(
    session: Session,
    *,
    user_id: int,
    product_id: int,
    quantity: int,
) -> Order:
    product = session.scalar(
        select(Product).where(Product.id == product_id).with_for_update()
    )
    if product is None:
        raise ProductNotFoundError("Product not found")
    if product.status != "ACTIVE":
        raise ProductUnavailableError("Product is inactive")
    if product.stock < quantity:
        raise InsufficientStockError("Insufficient stock")

    product.stock -= quantity
    order = Order(
        user_id=user_id,
        product_id=product.id,
        quantity=quantity,
        total_amount=product.price * quantity,
        status="CREATED",
    )
    session.add(order)
    session.commit()
    session.refresh(order)
    return order


def _get_user_order(
    session: Session,
    order_id: int,
    user_id: int,
    *,
    for_update: bool = False,
) -> Order:
    statement = select(Order).where(
        Order.id == order_id,
        Order.user_id == user_id,
    )
    if for_update:
        statement = statement.with_for_update()

    order = session.scalar(statement)
    if order is None:
        raise OrderNotFoundError("Order not found")
    return order


def get_order(session: Session, order_id: int, user_id: int) -> Order:
    return _get_user_order(session, order_id, user_id)


def pay_order(session: Session, order_id: int, user_id: int) -> Order:
    order = _get_user_order(session, order_id, user_id, for_update=True)
    if order.status != "CREATED":
        raise InvalidOrderStateError(
            f"Order cannot be paid when status is {order.status}"
        )

    order.status = "PAID"
    session.commit()
    session.refresh(order)
    return order


def cancel_order(session: Session, order_id: int, user_id: int) -> Order:
    order = _get_user_order(session, order_id, user_id, for_update=True)
    if order.status != "CREATED":
        raise InvalidOrderStateError(
            f"Order cannot be cancelled when status is {order.status}"
        )

    product = session.scalar(
        select(Product).where(Product.id == order.product_id).with_for_update()
    )
    if product is None:
        raise InvalidOrderStateError("Order product no longer exists")

    product.stock += order.quantity
    order.status = "CANCELLED"
    session.commit()
    session.refresh(order)
    return order
