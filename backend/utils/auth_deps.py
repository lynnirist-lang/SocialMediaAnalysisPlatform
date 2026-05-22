"""认证依赖与路由保护装饰器"""
from functools import wraps
from typing import Callable, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.user import AccountUser
from backend.utils.security import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)


def _user_from_token(token: str, db: Session) -> Optional[AccountUser]:
    payload = decode_access_token(token)
    if not payload:
        return None
    username = payload.get("sub")
    if not username:
        return None
    user = db.query(AccountUser).filter(AccountUser.username == username).first()
    if not user or not user.is_active:
        return None
    return user


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Optional[AccountUser]:
    if not credentials:
        return None
    return _user_from_token(credentials.credentials, db)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> AccountUser:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = _user_from_token(credentials.credentials, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效或已过期的令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_auth(func: Callable) -> Callable:
    """路由保护装饰器：要求已登录用户"""

    @wraps(func)
    async def wrapper(*args, current_user: AccountUser = Depends(get_current_user), **kwargs):
        return await func(*args, current_user=current_user, **kwargs)

    return wrapper
