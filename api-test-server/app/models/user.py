"""users 表的 SQLAlchemy 映射。"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class User(Base):
    """可登录用户；密码只以 password_hash 形式保存。"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))  # 不保存明文密码
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=text("1"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
    )
