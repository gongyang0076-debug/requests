"""密码哈希和 JWT 访问令牌的最小安全封装。"""

from datetime import datetime, timedelta, timezone

import jwt
from jwt import InvalidTokenError
from pwdlib import PasswordHash

from app.core.config import AuthSettings

# pwdlib 选择推荐的密码哈希参数；数据库只保存哈希，不保存明文密码。
PASSWORD_HASH = PasswordHash.recommended()


class InvalidAccessTokenError(ValueError):
    """访问令牌无法解析为合法用户时使用的统一业务异常。"""


def hash_password(password: str) -> str:
    """生成用于持久化的单向密码哈希。"""

    return PASSWORD_HASH.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """校验登录明文是否匹配已保存的密码哈希。"""

    return PASSWORD_HASH.verify(password, password_hash)


def create_access_token(user_id: int, settings: AuthSettings) -> str:
    """签发带 subject、签发时间和过期时间的 JWT。

    JWT 是签名令牌，不是加密容器，因此 Payload 只放用户 ID 等非敏感声明。
    """

    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(
        payload,
        settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str, settings: AuthSettings) -> int:
    """验证令牌并返回用户 ID，不向调用方暴露底层解码错误。"""

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "sub"]},
        )
        user_id = int(payload["sub"])
    except (InvalidTokenError, KeyError, TypeError, ValueError) as exc:
        raise InvalidAccessTokenError("Invalid or expired token") from exc

    # sub 虽然通过签名校验，仍确认它是有效的正整数业务 ID。
    if user_id <= 0:
        raise InvalidAccessTokenError("Invalid or expired token")

    return user_id
