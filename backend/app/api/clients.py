"""客户管理 API"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.client import Client
from app.models.user import User

router = APIRouter()


# ---------- Pydantic schemas ----------

class ClientCreate(BaseModel):
    name: str
    contact_person: str = ""
    phone: str = ""
    wechat: str = ""
    email: str = ""
    address: str = ""
    cooperation_history: str = ""
    legal_contacts: str = ""
    notes: str = ""


class ClientUpdate(BaseModel):
    name: Optional[str] = None
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    wechat: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    cooperation_history: Optional[str] = None
    legal_contacts: Optional[str] = None
    notes: Optional[str] = None


# ---------- Helpers ----------

def _can_access(user: User, client: Client | None) -> bool:
    if user.role == "admin":
        return True
    if client is None:
        return True
    return client.created_by == user.id


def _filter_by_role(query, user: User, model):
    if user.role != "admin" and hasattr(model, "created_by"):
        return query.filter(model.created_by == user.id)
    return query


def _client_to_dict(client: Client) -> dict:
    """将 Client ORM 对象转为字典"""
    return {
        "id": client.id,
        "name": client.name,
        "contact_person": client.contact_person,
        "phone": client.phone,
        "wechat": client.wechat,
        "email": client.email,
        "address": client.address,
        "cooperation_history": client.cooperation_history,
        "legal_contacts": client.legal_contacts,
        "notes": client.notes,
        "case_count": len(client.cases) if client.cases else 0,
        "created_at": client.created_at.isoformat() if client.created_at else None,
        "updated_at": client.updated_at.isoformat() if client.updated_at else None,
    }


# ---------- Routes ----------

@router.get("/")
def list_clients(
    search: str = Query("", description="搜索客户名称、联系人、电话"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取客户列表，支持搜索"""
    q = db.query(Client)

    if search:
        q = q.filter(
            Client.name.contains(search) |
            Client.contact_person.contains(search) |
            Client.phone.contains(search)
        )

    q = _filter_by_role(q, current_user, Client)
    clients = q.order_by(Client.created_at.desc()).all()
    return [_client_to_dict(c) for c in clients]


@router.get("/simple")
def list_clients_simple(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取客户简要列表（id + name + contact_person，供下拉框使用）"""
    q = _filter_by_role(db.query(Client), current_user, Client)
    clients = q.order_by(Client.name).all()
    return [{"id": c.id, "name": c.name, "contact_person": c.contact_person} for c in clients]


@router.get("/{client_id}")
def get_client(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取单个客户详情"""
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="客户不存在")
    return _client_to_dict(client)


@router.post("/")
def create_client(
    data: ClientCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建新客户"""
    client = Client(
        name=data.name,
        contact_person=data.contact_person,
        phone=data.phone,
        wechat=data.wechat,
        created_by=current_user.id,
        email=data.email,
        address=data.address,
        cooperation_history=data.cooperation_history,
        legal_contacts=data.legal_contacts,
        notes=data.notes,
    )
    db.add(client)
    db.commit()
    db.refresh(client)
    return _client_to_dict(client)


@router.put("/{client_id}")
def update_client(
    client_id: int,
    data: ClientUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新客户信息"""
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="客户不存在")
    if not _can_access(current_user, client):
        raise HTTPException(status_code=403, detail="无权修改此客户")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(client, key, value)

    db.commit()
    db.refresh(client)
    return _client_to_dict(client)


@router.delete("/{client_id}")
def delete_client(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除客户"""
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="客户不存在")
    if not _can_access(current_user, client):
        raise HTTPException(status_code=403, detail="无权删除此客户")

    db.delete(client)
    db.commit()
    return {"message": "客户删除成功"}
