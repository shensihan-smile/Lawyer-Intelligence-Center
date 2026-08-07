"""常法客户（常年法律顾问）API — CRUD + 工作记录 + 付款 + 统计 + 报告 + 预警"""
import os
import json
import uuid
from datetime import datetime, date, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, Body, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import func as sql_func
from pydantic import BaseModel
from typing import Optional, List
from app.core.database import get_db
from app.core.auth import get_current_user
from app.core.config import settings
from app.models.user import User
from app.models.retainer import RetainerClient, WorkRecord, PaymentRecord, RetainerReport
from app.models.client import Client

router = APIRouter()

# ==================== 常量 ====================

SERVICE_SCOPE_OPTIONS = [
    {"value": "contract_review", "label": "合同审查"},
    {"value": "legal_opinion", "label": "法律意见书"},
    {"value": "legal_consultation", "label": "法律咨询"},
    {"value": "policy_analysis", "label": "政策法规分析"},
    {"value": "labor_relations", "label": "劳动人事合规"},
    {"value": "ip_advice", "label": "知识产权建议"},
    {"value": "dispute_mediation", "label": "纠纷调解/协商"},
    {"value": "legal_training", "label": "法律培训/讲座"},
    {"value": "onsite_service", "label": "驻场服务"},
]

WORK_TYPE_OPTIONS = [
    {"value": "contract_review", "label": "合同审查"},
    {"value": "legal_opinion", "label": "法律意见书"},
    {"value": "legal_consultation", "label": "法律咨询"},
    {"value": "policy_analysis", "label": "政策法规分析"},
    {"value": "labor_relations", "label": "劳动人事合规"},
    {"value": "ip_advice", "label": "知识产权建议"},
    {"value": "dispute_mediation", "label": "纠纷调解/协商"},
    {"value": "legal_training", "label": "法律培训/讲座"},
    {"value": "onsite_service", "label": "驻场服务"},
    {"value": "litigation", "label": "诉讼代理"},
    {"value": "meeting", "label": "会议/汇报"},
    {"value": "other", "label": "其他"},
]

PAYMENT_METHODS = [
    {"value": "once", "label": "一次性付清"},
    {"value": "quarterly", "label": "按季度支付"},
    {"value": "half_yearly", "label": "按半年支付"},
    {"value": "annual", "label": "按年支付"},
]


# ==================== Pydantic Schemas ====================

class RetainerCreate(BaseModel):
    client_id: Optional[int] = None
    client_name: str
    service_start_date: str
    service_end_date: str
    contract_amount: float = 0
    payment_method: str = ""
    service_scope: str = "[]"
    has_onsite: bool = False
    contact_name: str = ""
    contact_phone: str = ""
    contract_number: str = ""
    notes: str = ""


class RetainerUpdate(BaseModel):
    client_id: Optional[int] = None
    client_name: Optional[str] = None
    service_start_date: Optional[str] = None
    service_end_date: Optional[str] = None
    contract_amount: Optional[float] = None
    payment_method: Optional[str] = None
    service_scope: Optional[str] = None
    has_onsite: Optional[bool] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contract_number: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class WorkRecordCreate(BaseModel):
    date: str
    work_type: str = "other"
    description: str = ""
    hours: float = 0
    participants: str = ""
    reference_number: str = ""


class WorkRecordUpdate(BaseModel):
    date: Optional[str] = None
    work_type: Optional[str] = None
    description: Optional[str] = None
    hours: Optional[float] = None
    participants: Optional[str] = None
    reference_number: Optional[str] = None


class PaymentCreate(BaseModel):
    payment_date: str
    amount: float = 0
    notes: str = ""


class ReportCreate(BaseModel):
    period_start: str
    period_end: str
    content: str = "{}"


class ReportUpdate(BaseModel):
    content: Optional[str] = None
    status: Optional[str] = None


class RenewRequest(BaseModel):
    new_end_date: str
    contract_amount: float = 0
    notes: str = ""


# ==================== Helpers ====================

def _parse_date(val: Optional[str]) -> Optional[datetime]:
    if not val:
        return None
    try:
        return datetime.fromisoformat(val)
    except (ValueError, TypeError):
        return None


def _days_until(end_date_val) -> int:
    """计算距到期日的天数（已过期返回负数）"""
    if not end_date_val:
        return 999
    if isinstance(end_date_val, str):
        end_date_val = date.fromisoformat(end_date_val[:10])
    elif isinstance(end_date_val, datetime):
        end_date_val = end_date_val.date()
    return (end_date_val - date.today()).days


def _compute_status(end_date_val) -> str:
    """根据到期日计算状态"""
    days = _days_until(end_date_val)
    if days < 0:
        return "expired"
    elif days <= 30:
        return "expiring"
    return "active"


def _retainer_to_dict(r: RetainerClient) -> dict:
    return {
        "id": r.id,
        "client_id": r.client_id,
        "client_name": r.client_name,
        "service_start_date": r.service_start_date.isoformat() if r.service_start_date else None,
        "service_end_date": r.service_end_date.isoformat() if r.service_end_date else None,
        "contract_amount": r.contract_amount,
        "payment_method": r.payment_method,
        "service_scope": r.service_scope,
        "has_onsite": r.has_onsite,
        "contact_name": r.contact_name,
        "contact_phone": r.contact_phone,
        "contract_file_path": r.contract_file_path,
        "contract_number": r.contract_number,
        "status": _compute_status(r.service_end_date),
        "notes": r.notes,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        "deleted": r.deleted,
        "days_until": _days_until(r.service_end_date),
    }


def _work_to_dict(w: WorkRecord) -> dict:
    return {
        "id": w.id,
        "retainer_id": w.retainer_id,
        "date": w.date.isoformat() if w.date else None,
        "work_type": w.work_type,
        "description": w.description,
        "hours": w.hours,
        "participants": w.participants,
        "reference_number": w.reference_number,
        "created_at": w.created_at.isoformat() if w.created_at else None,
        "updated_at": w.updated_at.isoformat() if w.updated_at else None,
    }


def _payment_to_dict(p: PaymentRecord) -> dict:
    return {
        "id": p.id,
        "retainer_id": p.retainer_id,
        "payment_date": p.payment_date.isoformat() if p.payment_date else None,
        "amount": p.amount,
        "receipt_path": p.receipt_path,
        "notes": p.notes,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


def _report_to_dict(r: RetainerReport) -> dict:
    return {
        "id": r.id,
        "retainer_id": r.retainer_id,
        "period_start": r.period_start.isoformat() if r.period_start else None,
        "period_end": r.period_end.isoformat() if r.period_end else None,
        "content": r.content,
        "status": r.status,
        "generated_date": r.generated_date.isoformat() if r.generated_date else None,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }


def _get_or_404(db: Session, retainer_id: int) -> RetainerClient:
    r = db.query(RetainerClient).filter(
        RetainerClient.id == retainer_id,
        RetainerClient.deleted == False,
    ).first()
    if not r:
        raise HTTPException(status_code=404, detail="常法客户不存在")
    return r


# ==================== 辅助端点（必须在 /{id} 之前注册） ====================

@router.get("/alerts")
def get_alerts(db: Session = Depends(get_db)):
    """获取常法客户到期预警（用于仪表盘）"""
    items = db.query(RetainerClient).filter(
        RetainerClient.deleted == False,
    ).order_by(RetainerClient.service_end_date.asc()).all()

    result = []
    for r in items:
        days = _days_until(r.service_end_date)
        d = _retainer_to_dict(r)
        if days <= 30:
            d["alert_level"] = "urgent" if days < 0 else ("critical" if days <= 7 else "warning")
            result.append(d)

    return {"total": len(result), "items": result}


@router.get("/alerts/stats")
def get_alert_stats(db: Session = Depends(get_db)):
    """常法客户预警统计"""
    all_items = db.query(RetainerClient).filter(
        RetainerClient.deleted == False,
    ).all()

    today = date.today()
    expired = 0
    within_7 = 0
    within_30 = 0
    for r in all_items:
        days = (r.service_end_date.date() - today).days if r.service_end_date else 999
        if days < 0:
            expired += 1
        elif days <= 7:
            within_7 += 1
        elif days <= 30:
            within_30 += 1

    return {
        "total": len(all_items),
        "expired": expired,
        "within_7d": within_7,
        "within_30d": within_30,
        "urgent_count": expired + within_7,
    }


@router.get("/service-scopes")
def get_service_scopes():
    """服务范围选项列表"""
    return {"items": SERVICE_SCOPE_OPTIONS}


@router.get("/work-types")
def get_work_types():
    """工作类型列表"""
    return {"items": WORK_TYPE_OPTIONS}


@router.get("/payment-methods")
def get_payment_methods():
    """付款方式列表"""
    return {"items": PAYMENT_METHODS}


# ==================== 常法客户 CRUD ====================

@router.get("/clients")
def list_retainer_clients(
    status: str = Query(""),
    search: str = Query(""),
    skip: int = Query(0),
    limit: int = Query(200),
    db: Session = Depends(get_db),
):
    """获取常法客户列表"""
    q = db.query(RetainerClient).filter(RetainerClient.deleted == False)

    if search:
        like = f"%{search}%"
        q = q.filter(
            RetainerClient.client_name.ilike(like) |
            RetainerClient.contract_number.ilike(like) |
            RetainerClient.contact_name.ilike(like)
        )

    items = q.order_by(RetainerClient.service_end_date.asc()).offset(skip).limit(limit).all()

    result = []
    for r in items:
        d = _retainer_to_dict(r)

        # 本月工时汇总
        today = date.today()
        month_start = date(today.year, today.month, 1)
        month_end_date = month_start
        if today.month == 12:
            month_end_date = date(today.year + 1, 1, 1) - timedelta(days=1)
        else:
            month_end_date = date(today.year, today.month + 1, 1) - timedelta(days=1)

        month_work = db.query(
            sql_func.sum(WorkRecord.hours),
            sql_func.count(WorkRecord.id)
        ).filter(
            WorkRecord.retainer_id == r.id,
            WorkRecord.date >= month_start,
            WorkRecord.date <= month_end_date,
        ).first()

        d["month_hours"] = round(month_work[0] or 0, 1)
        d["month_count"] = month_work[1] or 0

        result.append(d)

    # 状态筛选（在 Python 中做，因为 status 是计算字段）
    if status:
        result = [r for r in result if r["status"] == status]

    return {"total": len(result), "items": result}


@router.post("/clients")
def create_retainer_client(
    data: RetainerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建常法客户（如客户名称不在客户表中，自动创建 Client 记录）"""
    # 自动关联或创建 Client
    client_id = data.client_id
    if not client_id and data.client_name:
        existing = db.query(Client).filter(Client.name == data.client_name).first()
        if existing:
            client_id = existing.id
        else:
            new_client = Client(
                name=data.client_name,
                contact_person=data.contact_name,
                phone=data.contact_phone,
                created_by=current_user.id,
            )
            db.add(new_client)
            db.flush()
            client_id = new_client.id

    r = RetainerClient(
        client_id=client_id,
        client_name=data.client_name,
        service_start_date=_parse_date(data.service_start_date),
        service_end_date=_parse_date(data.service_end_date),
        contract_amount=data.contract_amount,
        payment_method=data.payment_method,
        service_scope=data.service_scope,
        has_onsite=data.has_onsite,
        contact_name=data.contact_name,
        contact_phone=data.contact_phone,
        contract_number=data.contract_number,
        notes=data.notes,
        created_by=current_user.id,
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return _retainer_to_dict(r)


@router.get("/clients/{retainer_id}")
def get_retainer_client(retainer_id: int, db: Session = Depends(get_db)):
    """获取常法客户详情"""
    r = _get_or_404(db, retainer_id)

    d = _retainer_to_dict(r)

    # 本月工时汇总
    today = date.today()
    month_start = date(today.year, today.month, 1)
    if today.month == 12:
        month_end_date = date(today.year + 1, 1, 1) - timedelta(days=1)
    else:
        month_end_date = date(today.year, today.month + 1, 1) - timedelta(days=1)

    month_work = db.query(
        sql_func.sum(WorkRecord.hours),
        sql_func.count(WorkRecord.id)
    ).filter(
        WorkRecord.retainer_id == r.id,
        WorkRecord.date >= month_start,
        WorkRecord.date <= month_end_date,
    ).first()

    d["month_hours"] = round(month_work[0] or 0, 1)
    d["month_count"] = month_work[1] or 0

    # 付款汇总
    payments = db.query(PaymentRecord).filter(
        PaymentRecord.retainer_id == r.id
    ).all()
    total_paid = sum(p.amount for p in payments)
    d["total_paid"] = round(total_paid, 2)
    d["unpaid_amount"] = round(max(0, r.contract_amount - total_paid), 2)

    return d


@router.put("/clients/{retainer_id}")
def update_retainer_client(
    retainer_id: int,
    data: RetainerUpdate,
    db: Session = Depends(get_db),
):
    """更新常法客户"""
    r = _get_or_404(db, retainer_id)

    update_data = data.model_dump(exclude_unset=True)

    # 处理日期字段
    for date_field in ["service_start_date", "service_end_date"]:
        if date_field in update_data:
            val = update_data.pop(date_field)
            setattr(r, date_field, _parse_date(val))

    for key, value in update_data.items():
        setattr(r, key, value)

    r.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(r)
    return _retainer_to_dict(r)


@router.delete("/clients/{retainer_id}")
def delete_retainer_client(retainer_id: int, db: Session = Depends(get_db)):
    """软删除常法客户（归档）"""
    r = _get_or_404(db, retainer_id)
    r.deleted = True
    r.updated_at = datetime.utcnow()
    db.commit()
    return {"ok": True, "message": "常法客户已归档"}


# ==================== 归档 / 续签 ====================

@router.post("/clients/{retainer_id}/archive")
def archive_retainer(retainer_id: int, db: Session = Depends(get_db)):
    """归档常法客户"""
    r = _get_or_404(db, retainer_id)
    r.deleted = True
    r.updated_at = datetime.utcnow()
    db.commit()
    return {"ok": True, "message": "常法客户已归档"}


@router.post("/clients/{retainer_id}/renew")
def renew_retainer(
    retainer_id: int,
    data: RenewRequest,
    db: Session = Depends(get_db),
):
    """续签常法合同"""
    r = db.query(RetainerClient).filter(RetainerClient.id == retainer_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="常法客户不存在")

    # 保存旧截止日期到备注
    old_end = r.service_end_date.strftime("%Y-%m-%d") if r.service_end_date else ""
    old_notes = r.notes or ""
    renew_note = f"[续签] {datetime.now().strftime('%Y-%m-%d')} 从 {old_end} 续签至 {data.new_end_date}"
    if data.notes:
        renew_note += f"；备注：{data.notes}"
    r.notes = f"{old_notes}\n{renew_note}".strip()

    r.service_end_date = _parse_date(data.new_end_date)
    if data.contract_amount > 0:
        r.contract_amount = data.contract_amount
    r.deleted = False  # 如已归档，重新激活
    r.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(r)
    return _retainer_to_dict(r)


# ==================== 合同文件上传/下载 ====================

@router.post("/clients/{retainer_id}/contract-file")
def upload_contract_file(
    retainer_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """上传常法客户合同文件"""
    r = _get_or_404(db, retainer_id)

    upload_dir = os.path.join(settings.UPLOAD_DIR, "retainer_contracts")
    os.makedirs(upload_dir, exist_ok=True)

    ext = os.path.splitext(file.filename or "contract.pdf")[1] or ".pdf"
    safe_name = f"retainer_{retainer_id}_{uuid.uuid4().hex[:8]}{ext}"
    file_path = os.path.join(upload_dir, safe_name)

    with open(file_path, "wb") as f:
        f.write(file.file.read())

    r.contract_file_path = file_path
    r.updated_at = datetime.utcnow()
    db.commit()

    return {"ok": True, "file_path": file_path, "filename": file.filename}


@router.get("/clients/{retainer_id}/contract-file")
def download_contract_file(retainer_id: int, db: Session = Depends(get_db)):
    """下载常法客户合同文件"""
    r = _get_or_404(db, retainer_id)
    if not r.contract_file_path or not os.path.exists(r.contract_file_path):
        raise HTTPException(status_code=404, detail="合同文件不存在")

    filename = os.path.basename(r.contract_file_path)
    return FileResponse(
        path=r.contract_file_path,
        filename=filename,
        media_type="application/octet-stream",
    )


# ==================== 工作记录 CRUD ====================

@router.get("/clients/{retainer_id}/work-records")
def list_work_records(
    retainer_id: int,
    work_type: str = Query(""),
    date_from: str = Query(""),
    date_to: str = Query(""),
    skip: int = Query(0),
    limit: int = Query(500),
    db: Session = Depends(get_db),
):
    """获取常法客户工作记录列表"""
    _get_or_404(db, retainer_id)

    q = db.query(WorkRecord).filter(WorkRecord.retainer_id == retainer_id)

    if work_type:
        q = q.filter(WorkRecord.work_type == work_type)
    if date_from:
        dt = _parse_date(date_from)
        if dt:
            q = q.filter(WorkRecord.date >= dt)
    if date_to:
        dt = _parse_date(date_to)
        if dt:
            q = q.filter(WorkRecord.date <= dt + timedelta(days=1))

    items = q.order_by(WorkRecord.date.desc()).offset(skip).limit(limit).all()

    result = [_work_to_dict(w) for w in items]

    # 汇总
    total_hours = sum(w.hours for w in items)
    return {
        "total": len(result),
        "total_hours": round(total_hours, 1),
        "items": result,
    }


@router.post("/clients/{retainer_id}/work-records")
def create_work_record(
    retainer_id: int,
    data: WorkRecordCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建常法工作记录"""
    _get_or_404(db, retainer_id)

    w = WorkRecord(
        retainer_id=retainer_id,
        date=_parse_date(data.date) or datetime.utcnow(),
        work_type=data.work_type,
        description=data.description,
        hours=data.hours,
        participants=data.participants,
        reference_number=data.reference_number,
    )
    db.add(w)
    db.commit()
    db.refresh(w)
    return _work_to_dict(w)


@router.put("/clients/{retainer_id}/work-records/{record_id}")
def update_work_record(
    retainer_id: int,
    record_id: int,
    data: WorkRecordUpdate,
    db: Session = Depends(get_db),
):
    """更新工作记录"""
    _get_or_404(db, retainer_id)

    w = db.query(WorkRecord).filter(
        WorkRecord.id == record_id,
        WorkRecord.retainer_id == retainer_id,
    ).first()
    if not w:
        raise HTTPException(status_code=404, detail="工作记录不存在")

    update_data = data.model_dump(exclude_unset=True)
    if "date" in update_data:
        update_data["date"] = _parse_date(update_data["date"])

    for key, value in update_data.items():
        setattr(w, key, value)

    w.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(w)
    return _work_to_dict(w)


@router.delete("/clients/{retainer_id}/work-records/{record_id}")
def delete_work_record(
    retainer_id: int,
    record_id: int,
    db: Session = Depends(get_db),
):
    """删除工作记录"""
    _get_or_404(db, retainer_id)

    w = db.query(WorkRecord).filter(
        WorkRecord.id == record_id,
        WorkRecord.retainer_id == retainer_id,
    ).first()
    if not w:
        raise HTTPException(status_code=404, detail="工作记录不存在")

    db.delete(w)
    db.commit()
    return {"ok": True, "message": "工作记录已删除"}


# ==================== 付款记录 CRUD ====================

@router.get("/clients/{retainer_id}/payments")
def list_payments(
    retainer_id: int,
    skip: int = Query(0),
    limit: int = Query(200),
    db: Session = Depends(get_db),
):
    """获取常法客户付款记录列表"""
    _get_or_404(db, retainer_id)

    items = db.query(PaymentRecord).filter(
        PaymentRecord.retainer_id == retainer_id
    ).order_by(PaymentRecord.payment_date.desc()).offset(skip).limit(limit).all()

    result = [_payment_to_dict(p) for p in items]
    total_paid = sum(p.amount for p in items)

    # 获取合同总额
    retainer = _get_or_404(db, retainer_id)

    return {
        "total": len(result),
        "total_paid": round(total_paid, 2),
        "contract_amount": retainer.contract_amount,
        "unpaid_amount": round(max(0, retainer.contract_amount - total_paid), 2),
        "items": result,
    }


@router.post("/clients/{retainer_id}/payments")
def create_payment(
    retainer_id: int,
    data: PaymentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建常法付款记录"""
    _get_or_404(db, retainer_id)

    p = PaymentRecord(
        retainer_id=retainer_id,
        payment_date=_parse_date(data.payment_date) or datetime.utcnow(),
        amount=data.amount,
        notes=data.notes,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return _payment_to_dict(p)


@router.post("/clients/{retainer_id}/payments/{payment_id}/receipt")
def upload_payment_receipt(
    retainer_id: int,
    payment_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """上传付款凭证文件"""
    _get_or_404(db, retainer_id)

    p = db.query(PaymentRecord).filter(
        PaymentRecord.id == payment_id,
        PaymentRecord.retainer_id == retainer_id,
    ).first()
    if not p:
        raise HTTPException(status_code=404, detail="付款记录不存在")

    upload_dir = os.path.join(settings.UPLOAD_DIR, "retainer_receipts")
    os.makedirs(upload_dir, exist_ok=True)

    ext = os.path.splitext(file.filename or "receipt.pdf")[1] or ".pdf"
    safe_name = f"receipt_{payment_id}_{uuid.uuid4().hex[:8]}{ext}"
    file_path = os.path.join(upload_dir, safe_name)

    with open(file_path, "wb") as f:
        f.write(file.file.read())

    p.receipt_path = file_path
    p.updated_at = datetime.utcnow()
    db.commit()

    return {"ok": True, "file_path": file_path, "filename": file.filename}


@router.get("/clients/{retainer_id}/payments/{payment_id}/receipt-file")
def download_payment_receipt(
    retainer_id: int,
    payment_id: int,
    db: Session = Depends(get_db),
):
    """下载付款凭证文件"""
    _get_or_404(db, retainer_id)

    p = db.query(PaymentRecord).filter(
        PaymentRecord.id == payment_id,
        PaymentRecord.retainer_id == retainer_id,
    ).first()
    if not p:
        raise HTTPException(status_code=404, detail="付款记录不存在")
    if not p.receipt_path or not os.path.exists(p.receipt_path):
        raise HTTPException(status_code=404, detail="凭证文件不存在")

    filename = os.path.basename(p.receipt_path)
    return FileResponse(
        path=p.receipt_path,
        filename=filename,
        media_type="application/octet-stream",
    )


@router.delete("/clients/{retainer_id}/payments/{payment_id}")
def delete_payment(
    retainer_id: int,
    payment_id: int,
    db: Session = Depends(get_db),
):
    """删除付款记录"""
    _get_or_404(db, retainer_id)

    p = db.query(PaymentRecord).filter(
        PaymentRecord.id == payment_id,
        PaymentRecord.retainer_id == retainer_id,
    ).first()
    if not p:
        raise HTTPException(status_code=404, detail="付款记录不存在")

    # 清理凭证文件
    if p.receipt_path and os.path.exists(p.receipt_path):
        try:
            os.remove(p.receipt_path)
        except OSError:
            pass

    db.delete(p)
    db.commit()
    return {"ok": True, "message": "付款记录已删除"}


# ==================== 统计 ====================

@router.get("/clients/{retainer_id}/stats")
def get_retainer_stats(retainer_id: int, db: Session = Depends(get_db)):
    """常法客户统计概览"""
    r = _get_or_404(db, retainer_id)

    # 所有工作记录
    all_work = db.query(WorkRecord).filter(
        WorkRecord.retainer_id == retainer_id,
    ).all()

    total_count = len(all_work)
    total_hours = round(sum(w.hours for w in all_work), 1)

    # 平均月工时
    if all_work:
        min_date = min(w.date for w in all_work if w.date)
        max_date = max(w.date for w in all_work if w.date)
        if min_date and max_date:
            months = max(1, (max_date.year - min_date.year) * 12 + (max_date.month - min_date.month) + 1)
            avg_monthly = round(total_hours / months, 1)
        else:
            avg_monthly = 0
    else:
        avg_monthly = 0

    # 按类型分布
    type_dist = {}
    for w in all_work:
        t = w.work_type or "other"
        type_dist[t] = type_dist.get(t, 0) + w.hours
    type_distribution = [
        {"type": k, "hours": round(v, 1),
         "label": next((wt["label"] for wt in WORK_TYPE_OPTIONS if wt["value"] == k), k)}
        for k, v in sorted(type_dist.items(), key=lambda x: -x[1])
    ]

    # 按月分布（近12个月）
    today = date.today()
    monthly = {}
    for i in range(11, -1, -1):
        year = today.year
        month = today.month - i
        while month <= 0:
            month += 12
            year -= 1
        key = f"{year}-{month:02d}"
        monthly[key] = {"month": key, "label": f"{month}月", "hours": 0, "count": 0}

    for w in all_work:
        if w.date:
            key = w.date.strftime("%Y-%m")
            if key in monthly:
                monthly[key]["hours"] += w.hours
                monthly[key]["count"] += 1

    monthly_list = [v for v in monthly.values()]
    for m in monthly_list:
        m["hours"] = round(m["hours"], 1)

    # 付款统计
    payments = db.query(PaymentRecord).filter(
        PaymentRecord.retainer_id == retainer_id,
    ).all()
    total_paid = round(sum(p.amount for p in payments), 2)
    unpaid = round(max(0, r.contract_amount - total_paid), 2)

    # 剩余天数
    days_remaining = _days_until(r.service_end_date)

    return {
        "total_count": total_count,
        "total_hours": total_hours,
        "avg_monthly_hours": avg_monthly,
        "days_remaining": days_remaining,
        "contract_amount": r.contract_amount,
        "total_paid": total_paid,
        "unpaid_amount": unpaid,
        "type_distribution": type_distribution,
        "monthly_trend": monthly_list,
    }


# ==================== 工作报告 ====================

@router.post("/clients/{retainer_id}/reports")
def create_report(
    retainer_id: int,
    data: ReportCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """生成常法顾问工作报告"""
    _get_or_404(db, retainer_id)

    report = RetainerReport(
        retainer_id=retainer_id,
        period_start=_parse_date(data.period_start),
        period_end=_parse_date(data.period_end),
        content=data.content,
        status="draft",
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return _report_to_dict(report)


@router.get("/clients/{retainer_id}/reports")
def list_reports(
    retainer_id: int,
    db: Session = Depends(get_db),
):
    """获取常法客户报告列表"""
    _get_or_404(db, retainer_id)

    reports = db.query(RetainerReport).filter(
        RetainerReport.retainer_id == retainer_id,
    ).order_by(RetainerReport.generated_date.desc()).all()

    return [_report_to_dict(r) for r in reports]


@router.get("/clients/{retainer_id}/reports/{report_id}")
def get_report(
    retainer_id: int,
    report_id: int,
    db: Session = Depends(get_db),
):
    """获取报告详情"""
    _get_or_404(db, retainer_id)

    report = db.query(RetainerReport).filter(
        RetainerReport.id == report_id,
        RetainerReport.retainer_id == retainer_id,
    ).first()
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")

    return _report_to_dict(report)


@router.put("/clients/{retainer_id}/reports/{report_id}")
def update_report(
    retainer_id: int,
    report_id: int,
    data: ReportUpdate,
    db: Session = Depends(get_db),
):
    """更新报告内容或状态"""
    _get_or_404(db, retainer_id)

    report = db.query(RetainerReport).filter(
        RetainerReport.id == report_id,
        RetainerReport.retainer_id == retainer_id,
    ).first()
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(report, key, value)

    report.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(report)
    return _report_to_dict(report)


@router.get("/clients/{retainer_id}/reports/{report_id}/pdf")
def export_report_pdf(
    retainer_id: int,
    report_id: int,
    db: Session = Depends(get_db),
):
    """导出工作报告为 PDF"""
    r = _get_or_404(db, retainer_id)

    report = db.query(RetainerReport).filter(
        RetainerReport.id == report_id,
        RetainerReport.retainer_id == retainer_id,
    ).first()
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")

    try:
        from app.services.pdf_retainer_report import generate_retainer_report_pdf

        tmp_dir = os.path.join(settings.UPLOAD_DIR, "temp")
        os.makedirs(tmp_dir, exist_ok=True)

        # 构建 PDF 数据
        pdf_data = {
            "client_name": r.client_name,
            "contract_number": r.contract_number,
            "period_start": report.period_start.strftime("%Y年%m月%d日") if report.period_start else "",
            "period_end": report.period_end.strftime("%Y年%m月%d日") if report.period_end else "",
            "content": json.loads(report.content) if isinstance(report.content, str) else report.content,
        }

        pdf_path = generate_retainer_report_pdf(tmp_dir, pdf_data)

        if not pdf_path:
            raise HTTPException(status_code=500, detail="PDF 生成失败")

        # 更新报告状态
        report.status = "sent"
        report.updated_at = datetime.utcnow()
        db.commit()

        safe_name = f"常法顾问工作报告_{r.client_name}_{report.period_start.strftime('%Y%m') if report.period_start else ''}.pdf"

        return FileResponse(
            path=pdf_path,
            filename=safe_name,
            media_type="application/pdf",
        )
    except ImportError:
        raise HTTPException(status_code=500, detail="PDF 生成服务未就绪")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF 生成失败: {str(e)}")
