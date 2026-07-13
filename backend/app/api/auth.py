"""认证相关 API"""
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.core.database import get_db
from app.core.auth import hash_password, verify_password, create_access_token, get_current_user
from app.models.user import User

router = APIRouter()


class UserCreate(BaseModel):
    username: str
    password: str
    real_name: str
    role: str = "lawyer"
    department: str = ""
    phone: str = ""
    email: str = ""


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    real_name: str
    role: str


@router.post("/login", response_model=TokenResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """用户登录"""
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )
    if not user.is_active:
        raise HTTPException(status_code=400, detail="用户已被停用")

    access_token = create_access_token(data={"sub": user.username, "role": user.role})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "real_name": user.real_name,
        "role": user.role,
    }


@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    """获取当前登录用户信息"""
    return {
        "id": current_user.id,
        "username": current_user.username,
        "real_name": current_user.real_name,
        "role": current_user.role,
        "department": current_user.department,
        "phone": current_user.phone,
        "email": current_user.email,
        "is_active": current_user.is_active,
    }
