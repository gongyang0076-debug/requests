"""测试数据生命周期管理。

TestDataManager 负责在用例执行过程中登记创建出来的资源 ID，并在用例结束时
按外键安全顺序清理它们，保证测试可重复运行、不污染数据库。

清理顺序（先删引用方，再删被引用对象）：
    Order → Product → User

- Order / User 没有业务删除接口，用参数化 SQL 直接删除；
- Product 有业务删除接口，优先走 API（可顺带验证 409 等业务规则），
  返回 404（资源已不存在）也视为清理成功。

清理器会尝试所有资源的删除，最后一次性汇总抛出所有失败，而不是遇到第一个
错误就中止，避免残留数据影响后续用例。
"""

from dataclasses import dataclass, field
from typing import Any, Mapping

from requests import Response

from api.auth_api import AuthApi
from api.order_api import OrderApi
from api.product_api import ProductApi
from common.database import DatabaseClient


class TestDataCleanupError(RuntimeError):
    """清理阶段结束时，若仍有资源未能删除，汇总抛出此异常。

    __test__ = False 告诉 pytest 不要把这个类当作测试用例收集。
    """

    __test__ = False


@dataclass(slots=True)
class TestDataManager:
    """登记已创建资源并按外键安全顺序删除。

    三个列表分别记录 user_id / product_id / order_id，创建成功才登记，
    用例结束调用 cleanup() 即可按依赖顺序清理。slots=True 节省内存。

    __test__ = False 避免被 pytest 当作测试类收集。
    """

    __test__ = False

    database_client: DatabaseClient  # 用于删除没有业务接口的 order / user
    cleanup_product_api: ProductApi  # 用于通过 API 删除 product
    # 以下三个列表不参与 __init__ 参数，由 dataclass 自动初始化为空列表
    _user_ids: list[int] = field(default_factory=list, init=False)
    _product_ids: list[int] = field(default_factory=list, init=False)
    _order_ids: list[int] = field(default_factory=list, init=False)

    def register_user(
        self,
        auth_api: AuthApi,
        payload: Mapping[str, Any],
    ) -> Response:
        """调用注册接口；201 时把返回的 user id 登记到清理列表。"""
        response = auth_api.register(payload)
        if response.status_code == 201:
            # 只在创建成功时登记，避免清理阶段去删一个不存在的 ID
            self._track(self._user_ids, int(response.json()["id"]))
        return response

    def create_product(
        self,
        product_api: ProductApi,
        payload: Mapping[str, Any],
    ) -> Response:
        """调用创建商品接口；201 时登记 product id。"""
        response = product_api.create_product(payload)
        if response.status_code == 201:
            self._track(self._product_ids, int(response.json()["id"]))
        return response

    def create_order(
        self,
        order_api: OrderApi,
        payload: Mapping[str, Any],
    ) -> Response:
        """调用下单接口；201 时登记 order id。"""
        response = order_api.create_order(payload)
        if response.status_code == 201:
            self._track(self._order_ids, int(response.json()["id"]))
        return response

    def cleanup(self) -> None:
        """按 Order → Product → User 顺序清理所有已登记资源。

        任何单个资源删除失败都不会立即抛出，而是记录到 errors 列表继续尝试
        其他资源，最后统一汇总抛出，便于一次性看到所有残留问题。
        """
        errors: list[str] = []

        # 1) 先删订单（它引用商品和用户），用 SQL 直接删
        # reversed 保证后创建的先删，栈式清理更接近依赖反序
        for order_id in reversed(self._order_ids):
            try:
                self.database_client.execute(
                    "DELETE FROM orders WHERE id = %s",
                    (order_id,),
                )
            except Exception as error:
                # 捕获异常继续清理独立资源，最后一起报错
                errors.append(f"order {order_id}: {error}")

        # 2) 再删商品（被订单引用），优先走业务 API
        for product_id in reversed(self._product_ids):
            try:
                response = self.cleanup_product_api.delete_product(product_id)
                # 204 = 删除成功；404 = 资源已不在（也算清理完成）
                if response.status_code not in (204, 404):
                    errors.append(
                        f"product {product_id}: cleanup returned "
                        f"HTTP {response.status_code}"
                    )
            except Exception as error:
                # 继续清理并记录每一次失败
                errors.append(f"product {product_id}: {error}")

        # 3) 最后删用户（仍可能被订单引用），用 SQL 直接删
        for user_id in reversed(self._user_ids):
            try:
                self.database_client.execute(
                    "DELETE FROM users WHERE id = %s",
                    (user_id,),
                )
            except Exception as error:
                # 继续清理，便于把所有失败一次性上报
                errors.append(f"user {user_id}: {error}")

        # 有任何失败就汇总抛出，不静默忽略
        if errors:
            raise TestDataCleanupError("; ".join(errors))

    @staticmethod
    def _track(resource_ids: list[int], resource_id: int) -> None:
        """把 id 加入清理列表，已存在则跳过，避免重复清理。"""
        if resource_id not in resource_ids:
            resource_ids.append(resource_id)
