"""用户管理 API（仅管理员可操作）"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from app.core.database import get_db
from app.core.auth import hash_password, get_current_user, require_admin
from app.models.user import User

router = APIRouter()


# ---------- Schemas ----------

class UserCreate(BaseModel):
    username: str
    password: str
    real_name: str
    role: str = "lawyer"  # admin / lawyer / assistant
    phone: str = ""
    email: str = ""


class UserUpdate(BaseModel):
    real_name: Optional[str] = None
    role: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None


# ---------- Helpers ----------

def _user_to_dict(u: User) -> dict:
    return {
        "id": u.id,
        "username": u.username,
        "real_name": u.real_name,
        "role": u.role,
        "phone": u.phone,
        "email": u.email,
        "is_active": u.is_active,
        "created_at": u.created_at.isoformat() if u.created_at else None,
    }


ROLE_LABELS = {"admin": "管理员", "lawyer": "律师", "assistant": "助理"}

VALID_ROLES = list(ROLE_LABELS.keys())


# ---------- Routes ----------

@router.get("/")
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取用户列表（所有登录用户可查看）"""
    users = db.query(User).order_by(User.role.asc(), User.created_at.desc()).all()
    return [_user_to_dict(u) for u in users]


@router.get("/roles")
def get_roles():
    """获取可选角色列表"""
    return [{"value": k, "label": v} for k, v in ROLE_LABELS.items()]


@router.get("/me")
def get_me(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取当前登录用户信息"""
    return _user_to_dict(current_user)


@router.post("/")
def create_user(
    data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """创建新用户（仅管理员）"""
    if data.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"无效角色，可选：{', '.join(VALID_ROLES)}")

    existing = db.query(User).filter(User.username == data.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="用户名已存在")

    user = User(
        username=data.username,
        hashed_password=hash_password(data.password),
        real_name=data.real_name,
        role=data.role,
        phone=data.phone,
        email=data.email,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"id": user.id, "message": f"用户 {user.real_name} 创建成功"}


@router.put("/{user_id}")
def update_user(
    user_id: int,
    data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """更新用户信息（仅管理员）"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    update_data = data.model_dump(exclude_unset=True)

    # 角色校验
    if "role" in update_data and update_data["role"] not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"无效角色")

    # 密码单独处理
    if "password" in update_data and update_data["password"]:
        update_data["hashed_password"] = hash_password(update_data.pop("password"))
    elif "password" in update_data:
        del update_data["password"]

    for key, value in update_data.items():
        setattr(user, key, value)

    db.commit()
    return {"message": "用户信息已更新"}


@router.put("/{user_id}/toggle-active")
def toggle_user_active(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """一键启用/停用用户账号（仅管理员）"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="不能停用自己的账号")

    user.is_active = not user.is_active
    db.commit()
    status_text = "启用" if user.is_active else "停用"
    return {"message": f"用户 {user.real_name} 已{status_text}", "is_active": user.is_active}


@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """删除用户（仅管理员）"""
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="不能删除自己的账号")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    db.delete(user)
    db.commit()
    return {"message": f"用户 {user.real_name} 已删除"}
