"""订单创建、支付和取消的核心业务规则。

库存变化和订单状态都在数据库事务中完成。涉及库存或状态迁移时使用
``with_for_update()`` 锁定行，避免并发请求绕过检查后产生超卖或重复操作。
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Order, Product
from app.services.product_service import ProductNotFoundError


class OrderNotFoundError(ValueError):
    """当前用户没有对应订单，或订单不存在。"""


class InsufficientStockError(ValueError):
    """请求数量超过当前可用库存。"""


class ProductUnavailableError(ValueError):
    """商品已下架，不能创建订单。"""


class InvalidOrderStateError(ValueError):
    """订单当前状态不允许目标操作。"""


def create_order(
    session: Session,
    *,
    user_id: int,
    product_id: int,
    quantity: int,
) -> Order:
    """锁定商品、扣减库存并创建 CREATED 订单。"""

    # 先加行锁再读取库存，后到事务会看到前一个事务提交后的值。
    product = session.scalar(
        select(Product).where(Product.id == product_id).with_for_update()
    )
    if product is None:
        raise ProductNotFoundError("Product not found")
    if product.status != "ACTIVE":
        raise ProductUnavailableError("Product is inactive")
    if product.stock < quantity:
        raise InsufficientStockError("Insufficient stock")

    # 服务端按数据库价格计算金额，绝不信任客户端提交的总价。
    product.stock -= quantity
    order = Order(
        user_id=user_id,
        product_id=product.id,
        quantity=quantity,
        total_amount=product.price * quantity,
        status="CREATED",
    )
    # 库存扣减与订单插入在同一次 commit 中完成，保证原子性。
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
    """按“订单 ID + 当前用户 ID”查订单，可选地加状态迁移锁。"""

    # 归属条件避免已认证用户猜到订单 ID 后访问他人的订单。
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
    """读取当前用户自己的订单，无需写锁。"""

    return _get_user_order(session, order_id, user_id)


def pay_order(session: Session, order_id: int, user_id: int) -> Order:
    """把 CREATED 订单转换为 PAID，拒绝重复支付或取消后支付。"""

    order = _get_user_order(session, order_id, user_id, for_update=True)
    if order.status != "CREATED":
        raise InvalidOrderStateError(
            f"Order cannot be paid when status is {order.status}"
        )

    # 锁内检查与状态更新连续执行，避免两个支付请求同时通过 CREATED 判断。
    order.status = "PAID"
    session.commit()
    session.refresh(order)
    return order


def cancel_order(session: Session, order_id: int, user_id: int) -> Order:
    """取消 CREATED 订单并在同一事务中恢复库存。"""

    order = _get_user_order(session, order_id, user_id, for_update=True)
    if order.status != "CREATED":
        raise InvalidOrderStateError(
            f"Order cannot be cancelled when status is {order.status}"
        )

    # 商品也要加锁，防止取消恢复库存与新订单扣库存相互覆盖。
    product = session.scalar(
        select(Product).where(Product.id == order.product_id).with_for_update()
    )
    if product is None:
        raise InvalidOrderStateError("Order product no longer exists")

    # 状态更新和库存恢复同一次提交，失败时不会只完成其中一项。
    product.stock += order.quantity
    order.status = "CANCELLED"
    session.commit()
    session.refresh(order)
    return order
