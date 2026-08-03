"""案件管理 API"""
import json
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.case import Case
from app.models.client import Client
from app.models.user import User
from app.models.case_client import case_clients
from app.models.case_third_party import case_third_parties

router = APIRouter()


# ---------- Pydantic schemas ----------

class CaseCreate(BaseModel):
    case_number: str
    case_reason: str = ""
    court: str = ""
    judge: str = ""
    clerk: str = ""
    plaintiff: str = ""
    defendant: str = ""
    third_party: List[str] = []    # 手动输入的第三人（纯文本数组）
    third_party_client_ids: List[int] = []  # 从客户库中选的第三人
    amount_in_dispute: float = 0
    case_stage: str = "intake"
    client_ids: List[int] = []
    acceptance_date: Optional[str] = None
    filing_date: Optional[str] = None
    trial_date: Optional[str] = None
    judgment_date: Optional[str] = None
    closing_date: Optional[str] = None
    notes: str = ""


class CaseUpdate(BaseModel):
    case_number: Optional[str] = None
    case_reason: Optional[str] = None
    court: Optional[str] = None
    judge: Optional[str] = None
    clerk: Optional[str] = None
    plaintiff: Optional[str] = None
    defendant: Optional[str] = None
    third_party: Optional[List[str]] = None
    third_party_client_ids: Optional[List[int]] = None
    amount_in_dispute: Optional[float] = None
    case_stage: Optional[str] = None
    client_ids: Optional[List[int]] = None
    acceptance_date: Optional[str] = None
    filing_date: Optional[str] = None
    trial_date: Optional[str] = None
    judgment_date: Optional[str] = None
    closing_date: Optional[str] = None
    notes: Optional[str] = None


# ---------- Helpers ----------

def _can_access(user: User, case: Case | None) -> bool:
    """检查用户是否有权访问该案件"""
    if user.role == "admin":
        return True
    if case is None:
        return True  # 列表查询，由调用方过滤
    return case.created_by == user.id


def _filter_by_role(query, user: User, model):
    """非管理员只看到自己创建的数据"""
    if user.role != "admin" and hasattr(model, "created_by"):
        return query.filter(model.created_by == user.id)
    return query


def _parse_date(value: Optional[str]) -> Optional[datetime]:
    """将 ISO 日期字符串转为 datetime，失败返回 None"""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def _case_to_dict(case: Case) -> dict:
    """将 Case ORM 对象转为字典"""
    # 解析 third_party：新格式为 JSON 数组，兼容旧格式（单个字符串）
    third_party_list: List[str] = []
    if case.third_party:
        try:
            parsed = json.loads(case.third_party)
            if isinstance(parsed, list):
                third_party_list = [str(x) for x in parsed if x]
            elif isinstance(parsed, str) and parsed.strip():
                third_party_list = [parsed.strip()]
        except (json.JSONDecodeError, TypeError):
            # 旧格式：单个字符串
            if case.third_party.strip():
                third_party_list = [case.third_party.strip()]

    return {
        "id": case.id,
        "case_number": case.case_number,
        "case_reason": case.case_reason,
        "court": case.court,
        "judge": case.judge,
        "clerk": case.clerk,
        "plaintiff": case.plaintiff,
        "defendant": case.defendant,
        "third_party": third_party_list,
        "third_party_clients": [
            {"id": c.id, "name": c.name, "contact_person": c.contact_person}
            for c in (case.third_party_clients or [])
        ],
        "amount_in_dispute": case.amount_in_dispute,
        "case_stage": case.case_stage,
        "clients": [
            {"id": c.id, "name": c.name, "contact_person": c.contact_person}
            for c in (case.clients or [])
        ],
        "acceptance_date": case.acceptance_date.isoformat() if case.acceptance_date else None,
        "filing_date": case.filing_date.isoformat() if case.filing_date else None,
        "trial_date": case.trial_date.isoformat() if case.trial_date else None,
        "judgment_date": case.judgment_date.isoformat() if case.judgment_date else None,
        "closing_date": case.closing_date.isoformat() if case.closing_date else None,
        "notes": case.notes,
        "created_at": case.created_at.isoformat() if case.created_at else None,
        "updated_at": case.updated_at.isoformat() if case.updated_at else None,
    }


def _sync_clients(case: Case, client_ids: List[int], db: Session):
    """同步案件关联的客户列表"""
    db.execute(
        case_clients.delete().where(case_clients.c.case_id == case.id)
    )
    if client_ids:
        existing_ids = {
            row[0] for row in
            db.query(Client.id).filter(Client.id.in_(client_ids)).all()
        }
        inserts = [
            {"case_id": case.id, "client_id": cid}
            for cid in client_ids if cid in existing_ids
        ]
        if inserts:
            db.execute(case_clients.insert(), inserts)


def _sync_third_parties(case: Case, client_ids: List[int], db: Session):
    """同步案件第三人（从客户库中选的）"""
    db.execute(
        case_third_parties.delete().where(case_third_parties.c.case_id == case.id)
    )
    if client_ids:
        existing_ids = {
            row[0] for row in
            db.query(Client.id).filter(Client.id.in_(client_ids)).all()
        }
        inserts = [
            {"case_id": case.id, "client_id": cid}
            for cid in client_ids if cid in existing_ids
        ]
        if inserts:
            db.execute(case_third_parties.insert(), inserts)


# ---------- Routes ----------

@router.get("/")
def list_cases(
    search: str = Query("", description="搜索案号、案由"),
    stage: str = Query("", description="按案件阶段筛选"),
    client_id: Optional[int] = Query(None, description="按客户筛选"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取案件列表，支持搜索和筛选"""
    q = db.query(Case)

    if search:
        q = q.filter(
            Case.case_number.contains(search) |
            Case.case_reason.contains(search)
        )
    if stage:
        q = q.filter(Case.case_stage == stage)
    if client_id:
        q = q.join(Case.clients).filter(Client.id == client_id)

    # 非管理员只看自己创建的
    q = _filter_by_role(q, current_user, Case)

    total = q.count()
    cases = q.order_by(Case.created_at.desc()).all()
    return {"total": total, "items": [_case_to_dict(c) for c in cases]}


@router.get("/stages")
def get_case_stages():
    """获取案件阶段列表"""
    return [
        {"value": "intake", "label": "接案"},
        {"value": "filing", "label": "立案"},
        {"value": "trial", "label": "审理中"},
        {"value": "judgment", "label": "判决"},
        {"value": "enforcement", "label": "执行"},
        {"value": "closed", "label": "结案"},
    ]


@router.get("/{case_id}")
def get_case(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取单个案件详情"""
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="案件不存在")
    if not _can_access(current_user, case):
        raise HTTPException(status_code=403, detail="无权访问此案件")
    return _case_to_dict(case)


@router.post("/")
def create_case(
    data: CaseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建新案件"""
    existing = db.query(Case).filter(Case.case_number == data.case_number).first()
    if existing:
        raise HTTPException(status_code=400, detail="案号已存在")

    case = Case(
        case_number=data.case_number,
        case_reason=data.case_reason,
        court=data.court,
        judge=data.judge,
        clerk=data.clerk,
        plaintiff=data.plaintiff,
        defendant=data.defendant,
        third_party=json.dumps(data.third_party, ensure_ascii=False) if data.third_party else "",
        amount_in_dispute=data.amount_in_dispute,
        case_stage=data.case_stage,
        created_by=current_user.id,
        acceptance_date=_parse_date(data.acceptance_date),
        filing_date=_parse_date(data.filing_date),
        trial_date=_parse_date(data.trial_date),
        judgment_date=_parse_date(data.judgment_date),
        closing_date=_parse_date(data.closing_date),
        notes=data.notes,
    )
    db.add(case)
    db.flush()  # 获取 case.id

    # 关联客户 + 第三人
    _sync_clients(case, data.client_ids, db)
    _sync_third_parties(case, data.third_party_client_ids, db)

    db.commit()
    db.refresh(case)
    return _case_to_dict(case)


@router.put("/{case_id}")
def update_case(
    case_id: int,
    data: CaseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新案件信息"""
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="案件不存在")
    if not _can_access(current_user, case):
        raise HTTPException(status_code=403, detail="无权修改此案件")

    update_data = data.model_dump(exclude_unset=True)

    # 客户关联和第三人关联单独处理
    client_ids = update_data.pop("client_ids", None)
    third_party_client_ids = update_data.pop("third_party_client_ids", None)

    # third_party 列表序列化为 JSON 字符串
    if "third_party" in update_data:
        tp = update_data["third_party"]
        update_data["third_party"] = json.dumps(tp, ensure_ascii=False) if tp else ""

    # 日期字段特殊处理
    for date_field in ["acceptance_date", "filing_date", "trial_date", "judgment_date", "closing_date"]:
        if date_field in update_data:
            update_data[date_field] = _parse_date(update_data[date_field])

    # 检查案号唯一性
    if "case_number" in update_data and update_data["case_number"] != case.case_number:
        dup = db.query(Case).filter(Case.case_number == update_data["case_number"]).first()
        if dup:
            raise HTTPException(status_code=400, detail="案号已存在")

    for key, value in update_data.items():
        setattr(case, key, value)

    # 同步关联
    if client_ids is not None:
        _sync_clients(case, client_ids, db)
    if third_party_client_ids is not None:
        _sync_third_parties(case, third_party_client_ids, db)

    db.commit()
    db.refresh(case)
    return _case_to_dict(case)


@router.delete("/{case_id}")
def delete_case(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除案件"""
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="案件不存在")
    if not _can_access(current_user, case):
        raise HTTPException(status_code=403, detail="无权删除此案件")

    db.delete(case)
    db.commit()
    return {"message": "案件删除成功"}
