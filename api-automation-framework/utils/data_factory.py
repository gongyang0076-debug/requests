"""动态测试数据工厂。

DataFactory 使用 Faker 生成唯一且合法的用户名、邮箱、商品名等测试数据，
避免固定数据在历史记录、执行顺序或并行 worker 之间产生冲突。工厂本身不保存
任何测试状态，每次调用都生成新的数据；实际创建出来的资源 ID 由
TestDataManager 负责登记和清理。
"""

from collections.abc import Mapping
from typing import Any

from faker import Faker


class DataFactory:
    """构造合法且唯一的请求体，不保存任何测试状态。"""

    def __init__(self, faker: Faker | None = None) -> None:
        # 允许外部传入 Faker（便于固定随机种子做复现），否则用默认 en_US 实例
        if faker is None:
            faker = Faker("en_US")
            faker.seed_instance()
        self._faker = faker

    def user_payload(self, prefix: str = "api_auto") -> dict[str, Any]:
        """生成一个唯一的注册请求体。

        Args:
            prefix: 用户名前缀，便于在数据库里按前缀筛选自动化产生的用户。

        Returns:
            包含 username / email / password 的字典，三者都用 uuid 后缀
            保证唯一，密码满足服务端的强度要求。
        """
        suffix = self._suffix()
        # 截断 prefix 到 17 字符，留 1 位给下划线，避免用户名长度超限
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
        """生成一个商品请求体。

        Args:
            template: 可选的覆盖字段。会先填充默认值，再用 template 覆盖，
                      便于测试用例只指定自己关心的字段（如 price/stock）。

        Returns:
            商品字典，name 上追加 uuid 片段保证唯一。
        """
        # 默认商品数据
        payload: dict[str, Any] = {
            "name": "Automation Product",
            "price": "29.90",
            "stock": 5,
            "status": "ACTIVE",
        }
        # 用 template 覆盖默认值，定制用例需要的边界数据
        if template is not None:
            payload.update(template)

        # 给 name 追加 uuid 片段，避免同名商品与历史数据冲突
        name = payload.get("name")
        if isinstance(name, str) and name:
            payload["name"] = f"{name[:90]} {self._suffix()[:8]}"
        return payload

    @staticmethod
    def order_payload(product_id: int, quantity: int = 1) -> dict[str, int]:
        """构造下单请求体。

        静态方法：订单数据完全由调用方提供的 product_id / quantity 决定，
        无需随机性。
        """
        return {"product_id": product_id, "quantity": quantity}

    def _suffix(self) -> str:
        """生成唯一后缀：去掉横线的 uuid4，用于各类数据保证唯一性。"""
        return self._faker.uuid4().replace("-", "")
