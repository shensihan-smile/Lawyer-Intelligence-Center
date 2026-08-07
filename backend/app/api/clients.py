"""客户管理 API"""
from datetime import datetime
from difflib import SequenceMatcher
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.client import Client
from app.models.case import Case
from app.models.case_client import case_clients
from app.models.communication import CommunicationRecord
from app.models.user import User

router = APIRouter()


# ---------- Pydantic schemas ----------

class ClientCreate(BaseModel):
    name: str
    client_type: str = "个人"
    id_number: str = ""
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
    client_type: Optional[str] = None
    id_number: Optional[str] = None
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    wechat: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    cooperation_history: Optional[str] = None
    legal_contacts: Optional[str] = None
    notes: Optional[str] = None


class CommunicationCreate(BaseModel):
    date: str  # ISO格式日期
    content: str = ""


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
    # 计算最后联系日期
    last_contact = None
    if client.communications and len(client.communications) > 0:
        sorted_comms = sorted(client.communications, key=lambda x: x.date or datetime.min, reverse=True)
        last_contact = sorted_comms[0].date.isoformat() if sorted_comms[0].date else None

    return {
        "id": client.id,
        "name": client.name,
        "client_type": client.client_type or "个人",
        "id_number": client.id_number or "",
        "contact_person": client.contact_person,
        "phone": client.phone,
        "wechat": client.wechat,
        "email": client.email,
        "address": client.address,
        "cooperation_history": client.cooperation_history,
        "legal_contacts": client.legal_contacts,
        "notes": client.notes,
        "case_count": len(client.cases) if client.cases else 0,
        "last_contact": last_contact,
        "created_at": client.created_at.isoformat() if client.created_at else None,
        "updated_at": client.updated_at.isoformat() if client.updated_at else None,
    }


def _similarity(a: str, b: str) -> float:
    """计算两个字符串的相似度（0~1）"""
    if not a or not b:
        return 0
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


# ---------- Routes ----------

@router.get("")
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


# —— 冲突检测（必须在 /{client_id} 之前注册） ——

@router.get("/check-conflict")
def check_conflict(
    name: str = Query(..., min_length=1, description="待检测的客户名称"),
    exclude_id: int = Query(0, description="排除的客户ID（编辑时避免和自己冲突）"),
    db: Session = Depends(get_db),
):
    """利益冲突检索：对客户名称做模糊匹配"""
    if len(name.strip()) < 2:
        return {"conflicts": []}

    results = []

    # 匹配已有客户
    clients = db.query(Client).all()
    for c in clients:
        if c.id == exclude_id:
            continue
        sim = _similarity(name, c.name)
        if sim >= 0.55 or name.strip() in c.name or c.name in name.strip():
            results.append({
                "source": "已有客户",
                "matched_name": c.name,
                "similarity": round(sim * 100),
                "case_id": None,
                "case_number": None,
            })

    # 匹配案件当事人
    cases = db.query(Case).all()
    for c in cases:
        for field, label in [(c.plaintiff, "案件原告"), (c.defendant, "案件被告")]:
            if not field:
                continue
            sim = _similarity(name, field)
            if sim >= 0.55 or name.strip() in field or field in name.strip():
                results.append({
                    "source": label,
                    "matched_name": field,
                    "similarity": round(sim * 100),
                    "case_id": c.id,
                    "case_number": c.case_number,
                })

    # 按相似度降序，去重
    seen = set()
    unique = []
    for r in sorted(results, key=lambda x: x["similarity"], reverse=True):
        key = (r["matched_name"], r["source"])
        if key not in seen:
            seen.add(key)
            unique.append(r)

    return {"conflicts": unique[:10]}


# —— 沟通记录（必须在 /{client_id} 之前注册） ——

@router.get("/{client_id}/communications")
def list_communications(
    client_id: int,
    db: Session = Depends(get_db),
):
    """获取某客户的沟通记录"""
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="客户不存在")

    records = db.query(CommunicationRecord).filter(
        CommunicationRecord.client_id == client_id
    ).order_by(CommunicationRecord.date.desc()).all()

    return [
        {
            "id": r.id,
            "client_id": r.client_id,
            "date": r.date.isoformat() if r.date else None,
            "content": r.content,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in records
    ]


@router.post("/{client_id}/communications")
def create_communication(
    client_id: int,
    data: CommunicationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """添加沟通记录"""
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="客户不存在")

    try:
        comm_date = datetime.fromisoformat(data.date)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="无效的日期格式，请使用 ISO 格式（YYYY-MM-DD）")

    r = CommunicationRecord(
        client_id=client_id,
        date=comm_date,
        content=data.content,
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return {
        "id": r.id,
        "client_id": r.client_id,
        "date": r.date.isoformat() if r.date else None,
        "content": r.content,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


@router.delete("/{client_id}/communications/{comm_id}")
def delete_communication(
    client_id: int,
    comm_id: int,
    db: Session = Depends(get_db),
):
    """删除沟通记录"""
    r = db.query(CommunicationRecord).filter(
        CommunicationRecord.id == comm_id,
        CommunicationRecord.client_id == client_id,
    ).first()
    if not r:
        raise HTTPException(status_code=404, detail="沟通记录不存在")
    db.delete(r)
    db.commit()
    return {"ok": True, "message": "沟通记录已删除"}


# —— 简化列表（用于下拉框） ——

@router.get("/simple")
def list_clients_simple(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取客户简要列表（id + name + contact_person，供下拉框使用）"""
    q = _filter_by_role(db.query(Client), current_user, Client)
    clients = q.order_by(Client.name).all()
    return [{"id": c.id, "name": c.name, "contact_person": c.contact_person} for c in clients]


# —— 单个客户（必须放在所有字面路由之后） ——

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


@router.post("")
def create_client(
    data: ClientCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建新客户"""
    client = Client(
        name=data.name,
        client_type=data.client_type or "个人",
        id_number=data.id_number or "",
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
    """更新客户信息（名称变更时自动同步所有关联案件的原告/被告字段）"""
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="客户不存在")
    if not _can_access(current_user, client):
        raise HTTPException(status_code=403, detail="无权修改此客户")

    old_name = client.name
    update_data = data.model_dump(exclude_unset=True)
    new_name = update_data.get("name", old_name)

    for key, value in update_data.items():
        setattr(client, key, value)

    # 名称变更时，同步所有关联案件的原告/被告字段
    if new_name != old_name:
        # 查找所有关联此客户的案件
        rows = db.execute(
            case_clients.select().where(case_clients.c.client_id == client.id)
        ).fetchall()

        synced_cases = 0
        for row in rows:
            c = db.query(Case).filter(Case.id == row.case_id).first()
            if not c:
                continue
            role = row.role or ""
            changed = False
            if role == "原告" and c.plaintiff == old_name:
                c.plaintiff = new_name
                changed = True
            elif role == "被告" and c.defendant == old_name:
                c.defendant = new_name
                changed = True
            if changed:
                synced_cases += 1

        if synced_cases > 0:
            print(f"[SYNC] 客户「{old_name}」→「{new_name}」已同步 {synced_cases} 个案件")

    db.commit()
    db.refresh(client)
    return _client_to_dict(client)


@router.delete("/{client_id}")
def delete_client(
    client_id: int,
    mode: str = Query("delete", description="delete=删除客户及关联 | detach=仅解除案件关联"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除客户

    - mode=delete（默认）：完全删除客户，cascade 清除沟通记录 + 案件关联
    - mode=detach：仅从所有关联案件中移除该客户（保留客户记录和沟通记录）
    """
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="客户不存在")
    if not _can_access(current_user, client):
        raise HTTPException(status_code=403, detail="无权删除此客户")

    if mode == "detach":
        # 仅解除所有案件关联
        result = db.execute(
            case_clients.delete().where(case_clients.c.client_id == client.id)
        )
        db.commit()
        return {"message": f"已解除 {result.rowcount} 个案件关联"}

    # mode=delete: 完全删除
    db.delete(client)
    db.commit()
    return {"message": "客户删除成功"}
