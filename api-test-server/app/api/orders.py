"""订单 HTTP 路由，负责注入当前用户并映射业务异常。"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_database_session
from app.models import User
from app.schemas.order import OrderCreate, OrderResponse
from app.services.order_service import (
    InsufficientStockError,
    InvalidOrderStateError,
    OrderNotFoundError,
    ProductUnavailableError,
    cancel_order,
    create_order,
    get_order,
    pay_order,
)
from app.services.product_service import ProductNotFoundError

router = APIRouter(prefix="/api/orders", tags=["orders"])


def _http_error(exc: ValueError) -> HTTPException:
    """把不存在映射为 404，把库存/状态冲突映射为 409。"""

    if isinstance(exc, (OrderNotFoundError, ProductNotFoundError)):
        error_status = status.HTTP_404_NOT_FOUND
    else:
        error_status = status.HTTP_409_CONFLICT
    return HTTPException(status_code=error_status, detail=str(exc))


@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def create(
    payload: OrderCreate,
    session: Annotated[Session, Depends(get_database_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> OrderResponse:
    """以当前 JWT 用户创建订单，不接受客户端指定 user_id。"""

    try:
        order = create_order(
            session,
            user_id=current_user.id,
            product_id=payload.product_id,
            quantity=payload.quantity,
        )
    except (
        ProductNotFoundError,
        ProductUnavailableError,
        InsufficientStockError,
    ) as exc:
        raise _http_error(exc) from exc
    return OrderResponse.model_validate(order)


@router.get("/{order_id}", response_model=OrderResponse)
def get_by_id(
    order_id: int,
    session: Annotated[Session, Depends(get_database_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> OrderResponse:
    """读取当前用户自己的订单。"""

    try:
        order = get_order(session, order_id, current_user.id)
    except OrderNotFoundError as exc:
        raise _http_error(exc) from exc
    return OrderResponse.model_validate(order)


@router.post("/{order_id}/pay", response_model=OrderResponse)
def pay(
    order_id: int,
    session: Annotated[Session, Depends(get_database_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> OrderResponse:
    """支付当前用户自己的订单。"""

    try:
        order = pay_order(session, order_id, current_user.id)
    except (OrderNotFoundError, InvalidOrderStateError) as exc:
        raise _http_error(exc) from exc
    return OrderResponse.model_validate(order)


@router.post("/{order_id}/cancel", response_model=OrderResponse)
def cancel(
    order_id: int,
    session: Annotated[Session, Depends(get_database_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> OrderResponse:
    """取消当前用户自己的订单，并恢复库存。"""

    try:
        order = cancel_order(session, order_id, current_user.id)
    except (OrderNotFoundError, InvalidOrderStateError) as exc:
        raise _http_error(exc) from exc
    return OrderResponse.model_validate(order)
