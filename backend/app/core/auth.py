"""认证相关功能"""
from datetime import datetime, timedelta
from typing import Optional
import hashlib
import os
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.database import get_db
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def hash_password(password: str) -> str:
    """对密码进行哈希加密（使用 SHA-256 + 随机盐，无需第三方库）"""
    salt = os.urandom(32).hex()                      # 生成 32 字节随机盐
    pwd_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100000,                                       # 10 万次迭代
    ).hex()
    return f"{salt}${pwd_hash}"                      # 格式：盐$哈希值


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码是否正确"""
    try:
        salt, pwd_hash = hashed_password.split("$", 1)
    except (ValueError, AttributeError):
        return False
    computed = hashlib.pbkdf2_hmac(
        "sha256",
        plain_password.encode("utf-8"),
        salt.encode("utf-8"),
        100000,
    ).hex()
    return computed == pwd_hash


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """创建 JWT 访问令牌"""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def _get_or_create_guest(db: Session) -> User:
    """获取或创建默认访客用户"""
    guest = db.query(User).filter(User.username == "guest").first()
    if not guest:
        guest = User(
            username="guest",
            real_name="访客",
            role="admin",
            is_active=True,
            hashed_password=hash_password("guest123"),
        )
        db.add(guest)
        db.commit()
        db.refresh(guest)
    return guest


def get_current_user(
    token: str = Depends(oauth2_scheme_optional),
    db: Session = Depends(get_db),
) -> User:
    """从 JWT 令牌中获取当前登录用户（可选认证，无 token 时返回访客用户）"""
    if not token:
        return _get_or_create_guest(db)

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(status_code=400, detail="用户已被停用")
    return user


def get_current_user_optional(
    token: str | None = Depends(oauth2_scheme_optional),
    db: Session = Depends(get_db),
) -> User | None:
    """可选认证：有 token 就解析用户，没有就返回 None（用于内部调用）"""
    if not token:
        return None
    try:
        return get_current_user(token=token, db=db)
    except HTTPException:
        return None


def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """要求管理员权限，非管理员返回 403"""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅管理员可执行此操作",
        )
    return current_user
