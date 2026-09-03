from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_database_session
from app.models import User
from app.schemas.product import ProductCreate, ProductResponse, ProductUpdate
from app.services.product_service import (
    ProductInUseError,
    ProductNotFoundError,
    create_product,
    delete_product,
    get_product,
    list_products,
    update_product,
)

router = APIRouter(prefix="/api/products", tags=["products"])


def _not_found(exc: ProductNotFoundError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=str(exc),
    )


def _conflict(exc: ProductInUseError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=str(exc),
    )


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def create(
    payload: ProductCreate,
    session: Annotated[Session, Depends(get_database_session)],
    _current_user: Annotated[User, Depends(get_current_user)],
) -> ProductResponse:
    product = create_product(session, **payload.model_dump())
    return ProductResponse.model_validate(product)


@router.get("", response_model=list[ProductResponse])
def get_all(
    session: Annotated[Session, Depends(get_database_session)],
    _current_user: Annotated[User, Depends(get_current_user)],
) -> list[ProductResponse]:
    return [ProductResponse.model_validate(product) for product in list_products(session)]


@router.get("/{product_id}", response_model=ProductResponse)
def get_by_id(
    product_id: int,
    session: Annotated[Session, Depends(get_database_session)],
    _current_user: Annotated[User, Depends(get_current_user)],
) -> ProductResponse:
    try:
        product = get_product(session, product_id)
    except ProductNotFoundError as exc:
        raise _not_found(exc) from exc
    return ProductResponse.model_validate(product)


@router.put("/{product_id}", response_model=ProductResponse)
def update(
    product_id: int,
    payload: ProductUpdate,
    session: Annotated[Session, Depends(get_database_session)],
    _current_user: Annotated[User, Depends(get_current_user)],
) -> ProductResponse:
    try:
        product = update_product(session, product_id, **payload.model_dump())
    except ProductNotFoundError as exc:
        raise _not_found(exc) from exc
    return ProductResponse.model_validate(product)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete(
    product_id: int,
    session: Annotated[Session, Depends(get_database_session)],
    _current_user: Annotated[User, Depends(get_current_user)],
) -> Response:
    try:
        delete_product(session, product_id)
    except ProductNotFoundError as exc:
        raise _not_found(exc) from exc
    except ProductInUseError as exc:
        raise _conflict(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
