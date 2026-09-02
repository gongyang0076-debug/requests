from collections.abc import Mapping
from typing import Any

from faker import Faker


class DataFactory:
    """Build valid, unique payloads without storing test state."""

    def __init__(self, faker: Faker | None = None) -> None:
        if faker is None:
            faker = Faker("en_US")
            faker.seed_instance()
        self._faker = faker

    def user_payload(self, prefix: str = "api_auto") -> dict[str, Any]:
        suffix = self._suffix()
        username = f"{prefix[:17]}_{suffix}"
        return {
            "username": username,
            "email": f"{username}@example.com",
            "password": f"AutomationPassword_{suffix}",
        }

    def product_payload(
        self,
        template: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": "Automation Product",
            "price": "29.90",
            "stock": 5,
            "status": "ACTIVE",
        }
        if template is not None:
            payload.update(template)

        name = payload.get("name")
        if isinstance(name, str) and name:
            payload["name"] = f"{name[:90]} {self._suffix()[:8]}"
        return payload

    @staticmethod
    def order_payload(product_id: int, quantity: int = 1) -> dict[str, int]:
        return {"product_id": product_id, "quantity": quantity}

    def _suffix(self) -> str:
        return self._faker.uuid4().replace("-", "")
