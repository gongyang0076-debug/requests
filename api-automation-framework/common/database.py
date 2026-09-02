from types import TracebackType
from typing import Any, Mapping, Sequence

import pymysql
from pymysql.connections import Connection
from pymysql.cursors import DictCursor

from config.config import DatabaseSettings

QueryParameters = Mapping[str, Any] | Sequence[Any]


class DatabaseConnectionError(RuntimeError):
    """Raised when the framework cannot connect to its configured MySQL database."""


class DatabaseClient:
    """Execute parameterized queries against MySQL."""

    def __init__(self, settings: DatabaseSettings) -> None:
        try:
            self._connection: Connection = pymysql.connect(
                host=settings.host,
                port=settings.port,
                user=settings.user,
                password=settings.password,
                database=settings.name,
                charset="utf8mb4",
                cursorclass=DictCursor,
                autocommit=True,
                connect_timeout=settings.connect_timeout,
            )
        except pymysql.MySQLError as exc:
            raise DatabaseConnectionError("Unable to connect to MySQL") from exc

    def fetch_one(
        self,
        query: str,
        params: QueryParameters | None = None,
    ) -> dict[str, Any] | None:
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
        self._connection.ping()
        with self._connection.cursor() as cursor:
            affected_rows = cursor.execute(query, params)
        return affected_rows

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> "DatabaseClient":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()
