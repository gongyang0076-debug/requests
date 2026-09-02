from unittest.mock import MagicMock

import pytest

from utils.data_lifecycle import TestDataCleanupError, TestDataManager


def _response(status_code: int, resource_id: int | None = None) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = {} if resource_id is None else {"id": resource_id}
    return response


def test_cleanup_uses_foreign_key_safe_order() -> None:
    events: list[tuple[str, int]] = []
    database_client = MagicMock()
    auth_api = MagicMock()
    product_api = MagicMock()
    order_api = MagicMock()
    auth_api.register.return_value = _response(201, 11)
    product_api.create_product.return_value = _response(201, 22)
    order_api.create_order.return_value = _response(201, 33)
    product_api.delete_product.side_effect = lambda product_id: (
        events.append(("product", product_id)) or _response(204)
    )

    def execute(query: str, params: tuple[int]) -> int:
        resource_type = "order" if "orders" in query else "user"
        events.append((resource_type, params[0]))
        return 1

    database_client.execute.side_effect = execute
    manager = TestDataManager(database_client, product_api)
    manager.register_user(auth_api, {"username": "user"})
    manager.create_product(product_api, {"name": "product"})
    manager.create_order(order_api, {"product_id": 22, "quantity": 1})

    manager.cleanup()

    assert events == [("order", 33), ("product", 22), ("user", 11)]


def test_failed_creations_are_not_registered_for_cleanup() -> None:
    database_client = MagicMock()
    auth_api = MagicMock()
    product_api = MagicMock()
    order_api = MagicMock()
    auth_api.register.return_value = _response(422)
    product_api.create_product.return_value = _response(422)
    order_api.create_order.return_value = _response(409)
    manager = TestDataManager(database_client, product_api)

    manager.register_user(auth_api, {})
    manager.create_product(product_api, {})
    manager.create_order(order_api, {})
    manager.cleanup()

    database_client.execute.assert_not_called()
    product_api.delete_product.assert_not_called()


def test_cleanup_reports_failures_after_attempting_every_resource() -> None:
    database_client = MagicMock()
    auth_api = MagicMock()
    product_api = MagicMock()
    order_api = MagicMock()
    auth_api.register.return_value = _response(201, 11)
    product_api.create_product.return_value = _response(201, 22)
    order_api.create_order.return_value = _response(201, 33)
    database_client.execute.side_effect = [RuntimeError("order locked"), 1]
    product_api.delete_product.return_value = _response(500)
    manager = TestDataManager(database_client, product_api)
    manager.register_user(auth_api, {})
    manager.create_product(product_api, {})
    manager.create_order(order_api, {})

    with pytest.raises(TestDataCleanupError) as error:
        manager.cleanup()

    assert "order 33" in str(error.value)
    assert "product 22" in str(error.value)
    assert database_client.execute.call_count == 2
    product_api.delete_product.assert_called_once_with(22)
