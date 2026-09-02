from sqlalchemy import Engine, URL, create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import Settings
from app.database.base import Base
from app.models import Order, Product, User  # noqa: F401  # Register table metadata.


class DatabaseUnavailableError(RuntimeError):
    """Raised when MySQL cannot complete a required operation."""


def create_database_engine(settings: Settings) -> Engine:
    database_url = URL.create(
        drivername="mysql+pymysql",
        username=settings.db_user,
        password=settings.db_password.get_secret_value(),
        host=settings.db_host,
        port=settings.db_port,
        database=settings.db_name,
        query={"charset": "utf8mb4"},
    )
    return create_engine(
        database_url,
        pool_pre_ping=True,
        pool_recycle=1800,
        connect_args={"connect_timeout": 3},
    )


def initialize_database(engine: Engine) -> None:
    try:
        Base.metadata.create_all(engine)
    except SQLAlchemyError as exc:
        raise DatabaseUnavailableError("Database unavailable") from exc


def verify_database_connection(engine: Engine) -> None:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1")).scalar_one()
    except SQLAlchemyError as exc:
        raise DatabaseUnavailableError("Database unavailable") from exc
