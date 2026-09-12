"""MySQL 客户端封装层。

DatabaseClient 基于 PyMySQL，用于在 API 断言之外，直接查询数据库验证关键
持久化结果（如订单支付后 orders.status 是否真的变成 PAID）。所有查询都使用
参数化查询，避免 SQL 注入。autocommit=True 让每条语句立即生效，适合测试断言。

数据库断言只检查订单状态等关键持久化结果，不重复验证每个响应字段，避免测试
与内部表结构过度耦合。
"""

from types import TracebackType
from typing import Any, Mapping, Sequence

import pymysql
from pymysql.connections import Connection
from pymysql.cursors import DictCursor

from config.config import DatabaseSettings

# 查询参数类型：dict-like 或序列，都由 PyMySQL 的参数化机制安全填充
QueryParameters = Mapping[str, Any] | Sequence[Any]


class DatabaseConnectionError(RuntimeError):
    """框架无法连接到配置的 MySQL 数据库时抛出。

    用专门的异常类型区分"连接失败"和"查询执行失败"，便于上层 Fixture
    在 setup 阶段快速判断是否是环境问题。
    """


class DatabaseClient:
    """对 MySQL 执行参数化查询的客户端。

    用法：
        with DatabaseClient(settings) as db:
            row = db.fetch_one("SELECT status FROM orders WHERE id = %s", (order_id,))

    所有方法在执行前会 ping 连接，避免长 Session 因 wait_timeout 被服务端断开。
    """

    def __init__(self, settings: DatabaseSettings) -> None:
        # 建立到 MySQL 的连接
        try:
            self._connection: Connection = pymysql.connect(
                host=settings.host,
                port=settings.port,
                user=settings.user,
                password=settings.password,
                database=settings.name,
                charset="utf8mb4",  # 支持 emoji 等 4 字节字符
                cursorclass=DictCursor,  # 查询结果返回 dict，按字段名取值更直观
                autocommit=True,  # 每条语句自动提交，断言场景下无需显式事务
                connect_timeout=settings.connect_timeout,
            )
        except pymysql.MySQLError as exc:
            # 连接失败包装成自定义异常，便于上层识别
            raise DatabaseConnectionError("Unable to connect to MySQL") from exc

    def fetch_one(
        self,
        query: str,
        params: QueryParameters | None = None,
    ) -> dict[str, Any] | None:
        """执行查询并返回单行（dict），无结果时返回 None。

        Args:
            query: SQL 语句，用 %s 占位，由 PyMySQL 参数化填充。
            params: 占位参数，避免拼接 SQL 导致注入。
        """
        # ping(reconnect=True) 默认行为：连接失效时自动重连
        self._connection.ping()
        with self._connection.cursor() as cursor:
            cursor.execute(query, params)
            row = cursor.fetchone()
        return row

    def execute(
        self,
        query: str,
        params: QueryParameters | None = None,
    ) -> int:
        """执行单条语句（UPDATE/DELETE/INSERT），返回受影响行数。

        主要用于测试结束时的数据清理（Teardown）。
        """
        self._connection.ping()
        with self._connection.cursor() as cursor:
            affected_rows = cursor.execute(query, params)
        return affected_rows

    def close(self) -> None:
        """关闭数据库连接。"""
        self._connection.close()

    # 支持 with 语法，离开作用域自动 close
    def __enter__(self) -> "DatabaseClient":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()
