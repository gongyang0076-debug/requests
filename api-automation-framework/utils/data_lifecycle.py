from dataclasses import dataclass, field
from typing import Any, Mapping

from requests import Response

from api.auth_api import AuthApi
from api.order_api import OrderApi
from api.product_api import ProductApi
from common.database import DatabaseClient


class TestDataCleanupError(RuntimeError):
    """Raised after all cleanup attempts when at least one resource remains."""

    __test__ = False


@dataclass(slots=True)
class TestDataManager:
    """Register created resources and remove them in foreign-key-safe order."""

    __test__ = False

    database_client: DatabaseClient
    cleanup_product_api: ProductApi
    _user_ids: list[int] = field(default_factory=list, init=False)
    _product_ids: list[int] = field(default_factory=list, init=False)
    _order_ids: list[int] = field(default_factory=list, init=False)

    def register_user(
        self,
        auth_api: AuthApi,
        payload: Mapping[str, Any],
    ) -> Response:
        response = auth_api.register(payload)
        if response.status_code == 201:
            self._track(self._user_ids, int(response.json()["id"]))
        return response

    def create_product(
        self,
        product_api: ProductApi,
        payload: Mapping[str, Any],
    ) -> Response:
        response = product_api.create_product(payload)
        if response.status_code == 201:
            self._track(self._product_ids, int(response.json()["id"]))
        return response

    def create_order(
        self,
        order_api: OrderApi,
        payload: Mapping[str, Any],
    ) -> Response:
        response = order_api.create_order(payload)
        if response.status_code == 201:
            self._track(self._order_ids, int(response.json()["id"]))
        return response

    def cleanup(self) -> None:
        errors: list[str] = []

        for order_id in reversed(self._order_ids):
            try:
                self.database_client.execute(
                    "DELETE FROM orders WHERE id = %s",
                    (order_id,),
                )
            except Exception as error:  # Continue so independent resources are attempted.
                errors.append(f"order {order_id}: {error}")

        for product_id in reversed(self._product_ids):
            try:
                response = self.cleanup_product_api.delete_product(product_id)
                if response.status_code not in (204, 404):
                    errors.append(
                        f"product {product_id}: cleanup returned "
                        f"HTTP {response.status_code}"
                    )
            except Exception as error:  # Continue and report every cleanup failure.
                errors.append(f"product {product_id}: {error}")

        for user_id in reversed(self._user_ids):
            try:
                self.database_client.execute(
                    "DELETE FROM users WHERE id = %s",
                    (user_id,),
                )
            except Exception as error:  # Continue so all failures can be reported together.
                errors.append(f"user {user_id}: {error}")

        if errors:
            raise TestDataCleanupError("; ".join(errors))

    @staticmethod
    def _track(resource_ids: list[int], resource_id: int) -> None:
        if resource_id not in resource_ids:
            resource_ids.append(resource_id)
