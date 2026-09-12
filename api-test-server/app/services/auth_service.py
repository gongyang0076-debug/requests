"""用户注册和登录的业务规则。

Router 只负责把 HTTP 请求转换成 Schema；用户名/邮箱唯一性、密码哈希和登录
失败语义集中在本模块，便于服务测试和接口测试从不同层验证。
"""

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models import User


class UserAlreadyExistsError(ValueError):
    """用户名或邮箱已被占用。"""


class InvalidCredentialsError(ValueError):
    """用户名、密码或用户状态无法完成认证。"""


def register_user(
    session: Session,
    *,
    username: str,
    email: str,
    password: str,
) -> User:
    """注册用户，并将并发唯一键冲突映射为稳定业务异常。"""

    existing_user_id = session.scalar(
        select(User.id).where(or_(User.username == username, User.email == email))
    )
    if existing_user_id is not None:
        raise UserAlreadyExistsError("Username or email already exists")

    # 只把哈希写入数据库，明文 password 不会进入 User 模型。
    user = User(
        username=username,
        email=email,
        password_hash=hash_password(password),
    )
    session.add(user)

    try:
        session.commit()
    except IntegrityError as exc:
        # 预查询与插入之间仍可能有并发注册，数据库约束是最终保护。
        session.rollback()
        raise UserAlreadyExistsError("Username or email already exists") from exc

    session.refresh(user)
    return user


def authenticate_user(session: Session, *, username: str, password: str) -> User:
    """验证凭据并返回活动用户，避免泄漏“用户名是否存在”。"""

    user = session.scalar(select(User).where(User.username == username))
    if user is None or not user.is_active:
        raise InvalidCredentialsError("Invalid username or password")

    # 对明文输入与哈希比较，而非读取或恢复原密码。
    if not verify_password(password, user.password_hash):
        raise InvalidCredentialsError("Invalid username or password")

    return user
