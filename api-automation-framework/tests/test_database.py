from unittest.mock import MagicMock, patch

import pymysql
import pytest

from common.database import DatabaseClient, DatabaseConnectionError
from config.config import DatabaseSettings


pytestmark = pytest.mark.db


@pytest.fixture
def database_settings() -> DatabaseSettings:
    return DatabaseSettings(
        host="127.0.0.1",
        port=3308,
        user="api_test_user",
        password="unit_test_password",
        name="api_test",
        connect_timeout=3,
    )


def test_fetch_one_executes_parameterized_query_and_closes_connection(
    database_settings: DatabaseSettings,
) -> None:
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = {"status": "PAID"}

    with patch("common.database.pymysql.connect", return_value=connection) as connect:
        with DatabaseClient(database_settings) as database_client:
            row = database_client.fetch_one(
                "SELECT status FROM orders WHERE id = %s",
                (42,),
            )

    assert row == {"status": "PAID"}
    connect.assert_called_once_with(
        host="127.0.0.1",
        port=3308,
        user="api_test_user",
        password="unit_test_password",
        database="api_test",
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
        connect_timeout=3,
    )
    connection.ping.assert_called_once_with()
    cursor.execute.assert_called_once_with(
        "SELECT status FROM orders WHERE id = %s",
        (42,),
    )
    connection.close.assert_called_once_with()


def test_connection_error_does_not_expose_password(
    database_settings: DatabaseSettings,
) -> None:
    with patch(
        "common.database.pymysql.connect",
        side_effect=pymysql.OperationalError(2003, "Connection failed"),
    ):
        with pytest.raises(DatabaseConnectionError) as error:
            DatabaseClient(database_settings)

    assert str(error.value) == "Unable to connect to MySQL"
    assert database_settings.password not in str(error.value)


def test_execute_returns_affected_row_count(
    database_settings: DatabaseSettings,
) -> None:
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.execute.return_value = 1

    with patch("common.database.pymysql.connect", return_value=connection):
        with DatabaseClient(database_settings) as database_client:
            affected_rows = database_client.execute(
                "DELETE FROM orders WHERE id = %s",
                (42,),
            )

    assert affected_rows == 1
    connection.ping.assert_called_once_with()
    cursor.execute.assert_called_once_with(
        "DELETE FROM orders WHERE id = %s",
        (42,),
    )
