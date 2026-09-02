import re

from faker import Faker

from utils.data_factory import DataFactory


def _seeded_factory() -> DataFactory:
    faker = Faker("en_US")
    faker.seed_instance(20260902)
    return DataFactory(faker)


def test_user_payloads_are_valid_and_unique() -> None:
    factory = _seeded_factory()

    first = factory.user_payload("e2e")
    second = factory.user_payload("e2e")

    assert first != second
    assert re.fullmatch(r"[A-Za-z0-9_]{3,50}", first["username"])
    assert first["email"] == f"{first['username']}@example.com"
    assert 8 <= len(first["password"]) <= 128


def test_product_payload_preserves_template_and_uniquifies_name() -> None:
    factory = _seeded_factory()
    template = {
        "name": "Lifecycle Product",
        "price": 12.50,
        "stock": 2,
        "status": "INACTIVE",
    }

    payload = factory.product_payload(template)

    assert payload["name"].startswith("Lifecycle Product ")
    assert len(payload["name"]) <= 100
    assert payload["price"] == 12.50
    assert payload["stock"] == 2
    assert payload["status"] == "INACTIVE"
    assert template["name"] == "Lifecycle Product"


def test_order_payload_uses_dynamic_product_id() -> None:
    assert DataFactory.order_payload(37, quantity=2) == {
        "product_id": 37,
        "quantity": 2,
    }
