"""轻量 API：消息识别 / 待办任务 / 工时记录 / 计费配置 / 账单
完全不依赖现有认证系统，与前端数据结构直接对应。
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from app.core.database import get_db
from app.models.lightweight import StoredMessage, StoredTask, StoredTimeRecord, StoredBillingConfig, StoredBill

router = APIRouter()

# ==================== Messages ====================

class MessageCreate(BaseModel):
    source: str = "微信"
    content: str
    result: str = ""


@router.get("/messages")
def list_messages(limit: int = Query(100), db: Session = Depends(get_db)):
    records = db.query(StoredMessage).order_by(StoredMessage.created_at.desc()).limit(limit).all()
    return {"items": [{"id": r.id, "source": r.source, "content": r.content,
        "result": r.result, "time": r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else ""} for r in records]}


@router.post("/messages")
def create_message(data: MessageCreate, db: Session = Depends(get_db)):
    msg = StoredMessage(source=data.source, content=data.content, result=data.result)
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return {"ok": True, "id": msg.id}


# ==================== Tasks ====================

class TaskCreate(BaseModel):
    title: str
    priority: str = "中"
    related: str = ""
    deadline: str = ""
    status: str = "待处理"


@router.get("/tasks")
def list_tasks(limit: int = Query(100), db: Session = Depends(get_db)):
    records = db.query(StoredTask).order_by(StoredTask.created_at.desc()).limit(limit).all()
    return {"items": [{"id": r.id, "title": r.title, "priority": r.priority,
        "related": r.related, "deadline": r.deadline, "status": r.status} for r in records]}


@router.post("/tasks")
def create_task(data: TaskCreate, db: Session = Depends(get_db)):
    task = StoredTask(title=data.title, priority=data.priority, related=data.related,
                      deadline=data.deadline, status=data.status)
    db.add(task)
    db.commit()
    db.refresh(task)
    return {"ok": True, "id": task.id}


@router.put("/tasks/{task_id}")
def update_task(task_id: int, data: dict, db: Session = Depends(get_db)):
    task = db.query(StoredTask).filter(StoredTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    for k, v in data.items():
        if hasattr(task, k):
            setattr(task, k, v)
    db.commit()
    return {"ok": True}


@router.delete("/tasks/{task_id}")
def delete_task(task_id: int, db: Session = Depends(get_db)):
    db.query(StoredTask).filter(StoredTask.id == task_id).delete()
    db.commit()
    return {"ok": True}


# ==================== Time Records ====================

class TimeRecordCreate(BaseModel):
    case_name: str = ""
    category: str = "其他"
    minutes: int
    date: str = ""


@router.get("/time-records")
def list_time_records(limit: int = Query(200), db: Session = Depends(get_db)):
    records = db.query(StoredTimeRecord).order_by(StoredTimeRecord.created_at.desc()).limit(limit).all()
    return {"items": [{"id": r.id, "case_name": r.case_name, "category": r.category,
        "minutes": r.minutes, "date": r.date} for r in records]}


@router.post("/time-records")
def create_time_record(data: TimeRecordCreate, db: Session = Depends(get_db)):
    tr = StoredTimeRecord(case_name=data.case_name, category=data.category,
                          minutes=data.minutes, date=data.date)
    db.add(tr)
    db.commit()
    db.refresh(tr)
    return {"ok": True, "id": tr.id}


# ==================== Billing Config ====================

@router.get("/billing-config")
def get_billing_config(db: Session = Depends(get_db)):
    configs = db.query(StoredBillingConfig).all()
    result = {}
    for c in configs:
        result[c.config_key] = c.config_value
    return result


@router.post("/billing-config")
def set_billing_config(data: dict, db: Session = Depends(get_db)):
    for key, value in data.items():
        existing = db.query(StoredBillingConfig).filter(StoredBillingConfig.config_key == key).first()
        if existing:
            existing.config_value = str(value)
        else:
            db.add(StoredBillingConfig(config_key=key, config_value=str(value)))
    db.commit()
    return {"ok": True}


# ==================== Bills ====================

class BillCreate(BaseModel):
    period: str
    total_min: int
    total_amt: float
    rate: float = 500


@router.get("/bills")
def list_bills(limit: int = Query(50), db: Session = Depends(get_db)):
    records = db.query(StoredBill).order_by(StoredBill.created_at.desc()).limit(limit).all()
    return {"items": [{"id": r.id, "period": r.period, "total_min": r.total_min,
        "total_amt": r.total_amt, "rate": r.rate,
        "date": r.created_at.strftime("%Y-%m-%d") if r.created_at else ""} for r in records]}


@router.post("/bills")
def create_bill(data: BillCreate, db: Session = Depends(get_db)):
    bill = StoredBill(period=data.period, total_min=data.total_min,
                      total_amt=data.total_amt, rate=data.rate)
    db.add(bill)
    db.commit()
    db.refresh(bill)
    return {"ok": True, "id": bill.id}


@router.delete("/bills/{bill_id}")
def delete_bill(bill_id: int, db: Session = Depends(get_db)):
    db.query(StoredBill).filter(StoredBill.id == bill_id).delete()
    db.commit()
    return {"ok": True}
