"""保全记录 API — CRUD + 预警 + 日历 + 统计"""
from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.preservation import PreservationRecord, PreservationRenewal
from app.models.user import User

router = APIRouter()


# ---------- Pydantic schemas ----------

class PreservationCreate(BaseModel):
    case_id: int
    preservation_type: str
    target: str
    ruling_number: str = ""
    measure_type: str = ""
    court: str = ""
    start_date: str
    end_date: str
    notes: str = ""


class PreservationUpdate(BaseModel):
    preservation_type: Optional[str] = None
    target: Optional[str] = None
    ruling_number: Optional[str] = None
    measure_type: Optional[str] = None
    court: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class RenewalCreate(BaseModel):
    new_end_date: str
    ruling_number: str = ""
    renewal_date: Optional[str] = None
    notes: str = ""


# ---------- Helpers ----------

def _parse_date(val: Optional[str]) -> Optional[datetime]:
    if not val:
        return None
    try:
        return datetime.fromisoformat(val)
    except (ValueError, TypeError):
        return None


def _preservation_to_dict(p: PreservationRecord) -> dict:
    return {
        "id": p.id,
        "case_id": p.case_id,
        "preservation_type": p.preservation_type,
        "target": p.target,
        "ruling_number": p.ruling_number,
        "measure_type": p.measure_type,
        "court": p.court,
        "start_date": p.start_date.isoformat() if p.start_date else None,
        "end_date": p.end_date.isoformat() if p.end_date else None,
        "renewal_count": p.renewal_count,
        "status": p.status,
        "notes": p.notes,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


def _days_until(end_date_val) -> int:
    """计算距到期日的天数（已过期返回负数）"""
    if not end_date_val:
        return 999
    if isinstance(end_date_val, str):
        end_date_val = date.fromisoformat(end_date_val[:10])
    elif isinstance(end_date_val, datetime):
        end_date_val = end_date_val.date()
    return (end_date_val - date.today()).days


# ---------- 到期日自动计算 ----------

DURATION_RULES = {
    "冻结银行账户": 365,
    "查封不动产": 1095,    # 3年
    "查封动产": 730,       # 2年
    "冻结股权": 730,       # 2年
    "冻结债权": 365,
    "扣押": 730,
    "行为保全": 180,       # 6个月
    "诉前保全": 30,
    "其他": 365,
}


@router.get("/compute-end-date")
def compute_end_date(
    start_date: str = Query(...),
    measure_type: str = Query("冻结银行账户"),
):
    """根据起始日期和措施类型自动计算参考到期日"""
    try:
        sd = datetime.fromisoformat(start_date)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="无效的起始日期格式，请使用 ISO 格式（YYYY-MM-DD）")

    days = DURATION_RULES.get(measure_type, 365)
    from datetime import timedelta
    ed = sd + timedelta(days=days)
    return {
        "start_date": start_date,
        "measure_type": measure_type,
        "computed_end_date": ed.strftime("%Y-%m-%d"),
        "days_added": days,
        "note": "根据民事诉讼法，冻结银行存款期限不超过1年，查封动产不超过2年，查封不动产不超过3年，冻结股权不超过2年。自动计算仅为辅助参考，实际到期日以裁定书载明为准，请务必核对。"
    }


# ---------- CRUD ----------

@router.get("")
def list_preservations(
    case_id: Optional[int] = Query(None),
    status: str = Query(""),
    days_range: str = Query(""),
    search: str = Query(""),
    skip: int = Query(0),
    limit: int = Query(200),
    db: Session = Depends(get_db),
):
    """获取保全记录列表"""
    q = db.query(PreservationRecord)

    if case_id is not None:
        q = q.filter(PreservationRecord.case_id == case_id)
    if status:
        q = q.filter(PreservationRecord.status == status)
    if search:
        like = f"%{search}%"
        q = q.filter(
            PreservationRecord.target.ilike(like) |
            PreservationRecord.ruling_number.ilike(like)
        )

    items = q.order_by(PreservationRecord.end_date.asc()).offset(skip).limit(limit).all()

    # 按到期日筛选（前端用）
    result = []
    for p in items:
        d = _preservation_to_dict(p)
        d["days_until"] = _days_until(p.end_date)
        result.append(d)

    if days_range == "expired":
        result = [r for r in result if r["days_until"] < 0]
    elif days_range == "7d":
        result = [r for r in result if 0 <= r["days_until"] <= 7]
    elif days_range == "30d":
        result = [r for r in result if 0 <= r["days_until"] <= 30]
    elif days_range == "90d":
        result = [r for r in result if 0 <= r["days_until"] <= 90]

    return {"total": len(result), "items": result}


@router.get("/alerts")
def get_alerts(db: Session = Depends(get_db)):
    """获取待续期保全预警（用于首页和弹窗）"""
    items = db.query(PreservationRecord).filter(
        PreservationRecord.status == "active"
    ).order_by(PreservationRecord.end_date.asc()).all()

    result = []
    for p in items:
        days = _days_until(p.end_date)
        d = _preservation_to_dict(p)
        d["days_until"] = days

        # 已过期或7天内到期
        if days <= 7:
            d["alert_level"] = "urgent" if days < 0 else "critical"
            # 获取案件信息
            from app.models.case import Case
            case = db.query(Case).filter(Case.id == p.case_id).first()
            d["case_number"] = case.case_number if case else ""
            d["case_reason"] = case.case_reason if case else ""
            result.append(d)
        elif days <= 30:
            d["alert_level"] = "warning"
            from app.models.case import Case
            case = db.query(Case).filter(Case.id == p.case_id).first()
            d["case_number"] = case.case_number if case else ""
            d["case_reason"] = case.case_reason if case else ""
            result.append(d)

    return {"total": len(result), "items": result}


@router.get("/stats")
def preservation_stats(db: Session = Depends(get_db)):
    """保全统计"""
    all_active = db.query(PreservationRecord).filter(PreservationRecord.status == "active").all()
    today = date.today()
    expired = 0
    within_7 = 0
    within_30 = 0
    within_90 = 0
    for p in all_active:
        days = (p.end_date.date() - today).days if p.end_date else 999
        if days < 0:
            expired += 1
        elif days <= 7:
            within_7 += 1
        elif days <= 30:
            within_30 += 1
        elif days <= 90:
            within_90 += 1

    return {
        "total": len(all_active),
        "expired": expired,
        "within_7d": within_7,
        "within_30d": within_30,
        "within_90d": within_90,
        "urgent_count": expired + within_7,
    }


@router.get("/types")
def get_preservation_types():
    """保全类型列表"""
    return {
        "preservation_types": ["财产保全", "证据保全", "行为保全", "诉前保全", "诉讼保全", "执行保全", "其他"],
        "measure_types": ["冻结银行账户", "查封不动产", "查封动产", "冻结股权", "冻结债权", "扣押", "其他"],
    }


@router.get("/{preservation_id}")
def get_preservation(preservation_id: int, db: Session = Depends(get_db)):
    """获取保全详情（含续期历史）"""
    p = db.query(PreservationRecord).filter(PreservationRecord.id == preservation_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="保全记录不存在")

    d = _preservation_to_dict(p)
    d["days_until"] = _days_until(p.end_date)

    # 续期历史
    renewals = db.query(PreservationRenewal).filter(
        PreservationRenewal.preservation_id == preservation_id
    ).order_by(PreservationRenewal.renewal_date.desc()).all()

    d["renewals"] = [
        {
            "id": r.id,
            "previous_end_date": r.previous_end_date.isoformat() if r.previous_end_date else None,
            "new_end_date": r.new_end_date.isoformat() if r.new_end_date else None,
            "ruling_number": r.ruling_number,
            "renewal_date": r.renewal_date.isoformat() if r.renewal_date else None,
            "notes": r.notes,
        }
        for r in renewals
    ]
    return d


@router.post("")
def create_preservation(
    data: PreservationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建保全记录"""
    p = PreservationRecord(
        case_id=data.case_id,
        preservation_type=data.preservation_type,
        target=data.target,
        ruling_number=data.ruling_number,
        measure_type=data.measure_type,
        court=data.court,
        start_date=_parse_date(data.start_date),
        end_date=_parse_date(data.end_date),
        notes=data.notes,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return _preservation_to_dict(p)


@router.put("/{preservation_id}")
def update_preservation(
    preservation_id: int,
    data: PreservationUpdate,
    db: Session = Depends(get_db),
):
    """更新保全记录"""
    p = db.query(PreservationRecord).filter(PreservationRecord.id == preservation_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="保全记录不存在")

    update_data = data.model_dump(exclude_unset=True)
    for date_field in ["start_date", "end_date"]:
        if date_field in update_data:
            val = update_data.pop(date_field)
            setattr(p, date_field, _parse_date(val))

    for key, value in update_data.items():
        setattr(p, key, value)

    p.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(p)
    return _preservation_to_dict(p)


@router.delete("/{preservation_id}")
def delete_preservation(preservation_id: int, db: Session = Depends(get_db)):
    """删除保全记录"""
    p = db.query(PreservationRecord).filter(PreservationRecord.id == preservation_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="保全记录不存在")

    # 同时删除续期记录
    db.query(PreservationRenewal).filter(PreservationRenewal.preservation_id == preservation_id).delete()
    db.delete(p)
    db.commit()
    return {"ok": True, "message": "保全记录已删除"}


# ---------- 续期 ----------

@router.post("/{preservation_id}/renew")
def renew_preservation(
    preservation_id: int,
    data: RenewalCreate,
    db: Session = Depends(get_db),
):
    """标记续期"""
    p = db.query(PreservationRecord).filter(PreservationRecord.id == preservation_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="保全记录不存在")

    # 记录续期历史
    renewal = PreservationRenewal(
        preservation_id=preservation_id,
        previous_end_date=p.end_date,
        new_end_date=_parse_date(data.new_end_date),
        ruling_number=data.ruling_number,
        renewal_date=_parse_date(data.renewal_date) if data.renewal_date else datetime.utcnow(),
        notes=data.notes,
    )
    db.add(renewal)

    # 更新保全记录
    p.end_date = _parse_date(data.new_end_date)
    p.renewal_count = (p.renewal_count or 0) + 1
    p.status = "已续期"
    p.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(p)
    return _preservation_to_dict(p)


# ---------- 批量操作 ----------

@router.post("/batch/mark-processed")
def batch_mark_processed(ids: List[int], db: Session = Depends(get_db)):
    """批量标记已处理"""
    count = 0
    for pid in ids:
        p = db.query(PreservationRecord).filter(PreservationRecord.id == pid).first()
        if p:
            p.status = "已解封"
            count += 1
    db.commit()
    return {"ok": True, "count": count}
