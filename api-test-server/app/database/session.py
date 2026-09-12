"""MySQL Engine 的创建、初始化和可用性检查。"""

from sqlalchemy import Engine, URL, create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import Settings
from app.database.base import Base
# 导入模型以注册 SQLAlchemy metadata；create_all 才能看到三张业务表。
from app.models import Order, Product, User  # noqa: F401


class DatabaseUnavailableError(RuntimeError):
    """MySQL 无法完成初始化或健康检查时的统一异常。"""


def create_database_engine(settings: Settings) -> Engine:
    """根据环境配置创建可复用的 MySQL 连接池。"""

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
        # 取连接前先探测，避免连接池中失效连接直接导致请求失败。
        pool_pre_ping=True,
        # 防止长时间空闲的 MySQL 连接被服务端回收后仍留在连接池里。
        pool_recycle=1800,
        connect_args={"connect_timeout": 3},
    )


def initialize_database(engine: Engine) -> None:
    """创建当前模型缺失的表；测试项目暂不处理 Schema 版本迁移。"""

    try:
        Base.metadata.create_all(engine)
    except SQLAlchemyError as exc:
        raise DatabaseUnavailableError("Database unavailable") from exc


def verify_database_connection(engine: Engine) -> None:
    """执行最小 SQL 探测，确认应用账号真的可以访问数据库。"""

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1")).scalar_one()
    except SQLAlchemyError as exc:
        raise DatabaseUnavailableError("Database unavailable") from exc
