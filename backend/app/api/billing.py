"""财务管理 API"""
import json
import os
import uuid
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from app.core.database import get_db
from app.core.auth import get_current_user
from app.core.config import settings
from app.models.user import User
from app.models.billing import BillingConfig, Bill, BillItem, TimeRecord
from app.models.case import Case
from app.models.client import Client
from app.models.retainer import WorkRecord
from app.services.billing_engine import (
    get_case_billing_rate, calculate_record_amount,
    generate_bill_items,
)
from app.services.pdf_bill import amount_to_chinese
from app.services.pdf_bill import generate_bill_pdf

router = APIRouter()

# ==================== Pydantic Schemas ====================

class TimeRecordCreate(BaseModel):
    case_id: Optional[int] = None
    work_category: str = "other"
    description: str = ""
    start_time: str   # ISO
    end_time: str     # ISO


class TimeRecordUpdate(BaseModel):
    case_id: Optional[int] = None
    work_category: Optional[str] = None
    description: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None


class BillingConfigCreate(BaseModel):
    name: str
    billing_method: str = "hourly"
    unit_price: float = 0
    is_default: bool = False
    notes: str = ""


class BillGenerateRequest(BaseModel):
    client_id: int
    period_start: str  # YYYY-MM-DD
    period_end: str
    case_id: Optional[int] = None
    firm_name: str = ""
    firm_address: str = ""
    firm_phone: str = ""
    lawyer_name: str = ""
    notes: str = ""
    bank_info: str = ""


# ==================== Helpers ====================

def _parse_dt(value: str) -> datetime:
    if not value:
        raise HTTPException(status_code=400, detail="时间不能为空")
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail=f"无效时间: {value}")


def _tr_to_dict(r: TimeRecord) -> dict:
    return {
        "id": r.id,
        "case_id": r.case_id,
        "case_number": r.case.case_number if r.case else None,
        "work_category": r.work_category,
        "description": r.description,
        "start_time": r.start_time.isoformat() if r.start_time else None,
        "end_time": r.end_time.isoformat() if r.end_time else None,
        "duration_minutes": r.duration_minutes,
        "is_billed": r.is_billed,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


def _bill_to_dict(b: Bill) -> dict:
    return {
        "id": b.id,
        "bill_number": b.bill_number,
        "client_id": b.client_id,
        "client_name": b.client.name if b.client else "",
        "billing_period_start": b.billing_period_start.isoformat() if b.billing_period_start else None,
        "billing_period_end": b.billing_period_end.isoformat() if b.billing_period_end else None,
        "total_amount": b.total_amount,
        "amount_paid": b.amount_paid or 0,
        "paid_date": b.paid_date.isoformat() if b.paid_date else None,
        "status": b.status,
        "notes": b.notes,
        "firm_name": b.firm_name or "",
        "firm_address": b.firm_address or "",
        "firm_phone": b.firm_phone or "",
        "lawyer_name": b.lawyer_name or "",
        "bank_info": b.bank_info or "",
        "generated_at": b.generated_at.isoformat() if b.generated_at else None,
        "exported_at": b.exported_at.isoformat() if b.exported_at else None,
        "items": [
            {
                "id": i.id,
                "case_id": i.case_id,
                "case_number": i.case.case_number if i.case else None,
                "description": i.description,
                "billing_method": i.billing_method,
                "unit_price": i.unit_price,
                "quantity": i.quantity,
                "amount": i.amount,
                "item_type": i.item_type or "legal_fee",
            }
            for i in (b.items or [])
        ],
    }


# ==================== 工时记录 ====================

@router.get("/time-records")
def list_time_records(
    case_id: Optional[int] = Query(None),
    is_billed: Optional[bool] = Query(None),
    start_date: str = Query(""),
    end_date: str = Query(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(TimeRecord)
    if case_id:
        q = q.filter(TimeRecord.case_id == case_id)
    if is_billed is not None:
        q = q.filter(TimeRecord.is_billed == is_billed)
    if start_date:
        try:
            q = q.filter(TimeRecord.start_time >= datetime.fromisoformat(start_date))
        except ValueError:
            pass
    if end_date:
        try:
            q = q.filter(TimeRecord.end_time <= datetime.fromisoformat(end_date) + timedelta(days=1))
        except ValueError:
            pass

    records = q.order_by(TimeRecord.start_time.desc()).all()
    return [_tr_to_dict(r) for r in records]


@router.get("/time-records/active")
def get_active_timer(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取当前进行中的计时器（开始但未结束的）"""
    # 查找 end_time == start_time 的记录（表示计时中）
    record = db.query(TimeRecord).filter(
        TimeRecord.end_time == TimeRecord.start_time
    ).order_by(TimeRecord.start_time.desc()).first()

    if not record:
        return {"active": False}

    return {
        "active": True,
        "record": _tr_to_dict(record),
        "elapsed_minutes": int((datetime.now() - record.start_time).total_seconds() / 60),
    }


@router.post("/time-records/start")
def start_timer(
    case_id: Optional[int] = Body(None),
    work_category: str = Body("other"),
    description: str = Body(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """开始计时（创建一个 end_time == start_time 的记录表示计时中）"""
    # 检查是否有已在进行中的计时
    active = db.query(TimeRecord).filter(
        TimeRecord.end_time == TimeRecord.start_time
    ).first()
    if active:
        raise HTTPException(status_code=400, detail="已有进行中的计时，请先停止当前计时")

    now = datetime.now()
    record = TimeRecord(
        case_id=case_id if case_id and case_id > 0 else None,
        work_category=work_category,
        description=description,
        start_time=now,
        end_time=now,  # 标记为进行中
        duration_minutes=0,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return _tr_to_dict(record)


@router.post("/time-records/{record_id}/stop")
def stop_timer(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """停止计时"""
    record = db.query(TimeRecord).filter(TimeRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")
    if record.end_time != record.start_time:
        raise HTTPException(status_code=400, detail="计时已经停止")

    now = datetime.now()
    record.end_time = now
    record.duration_minutes = max(1, int((now - record.start_time).total_seconds() / 60))
    db.commit()
    db.refresh(record)
    return _tr_to_dict(record)


@router.post("/time-records")
def create_time_record(
    data: TimeRecordCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """手动创建工时记录"""
    start = _parse_dt(data.start_time)
    end = _parse_dt(data.end_time)

    if start >= end:
        raise HTTPException(status_code=400, detail="结束时间必须晚于开始时间")

    duration = int((end - start).total_seconds() / 60)

    record = TimeRecord(
        case_id=data.case_id if data.case_id and data.case_id > 0 else None,
        work_category=data.work_category,
        description=data.description,
        start_time=start,
        end_time=end,
        duration_minutes=duration,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return _tr_to_dict(record)


@router.put("/time-records/{record_id}")
def update_time_record(
    record_id: int,
    data: TimeRecordUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """修改工时记录"""
    r = db.query(TimeRecord).filter(TimeRecord.id == record_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="记录不存在")
    if r.is_billed:
        raise HTTPException(status_code=400, detail="已计费记录不可修改")

    update = data.model_dump(exclude_unset=True)
    if "start_time" in update:
        update["start_time"] = _parse_dt(update["start_time"])
    if "end_time" in update:
        update["end_time"] = _parse_dt(update["end_time"])

    for k, v in update.items():
        setattr(r, k, v)

    # 重新计算时长
    if r.start_time and r.end_time and r.end_time != r.start_time:
        r.duration_minutes = int((r.end_time - r.start_time).total_seconds() / 60)

    db.commit()
    db.refresh(r)
    return _tr_to_dict(r)


@router.delete("/time-records/{record_id}")
def delete_time_record(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    r = db.query(TimeRecord).filter(TimeRecord.id == record_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="记录不存在")
    if r.is_billed:
        raise HTTPException(status_code=400, detail="已计费记录不可删除")
    db.delete(r)
    db.commit()
    return {"message": "已删除"}


# ==================== 计费配置 ====================

@router.get("/config")
def list_billing_config(db: Session = Depends(get_db)):
    configs = db.query(BillingConfig).order_by(BillingConfig.is_default.desc()).all()
    return [
        {
            "id": c.id, "name": c.name, "billing_method": c.billing_method,
            "unit_price": c.unit_price, "is_default": c.is_default,
            "notes": c.notes,
        }
        for c in configs
    ]


@router.post("/config")
def create_billing_config(
    data: BillingConfigCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # 如果设为默认，取消其他默认
    if data.is_default:
        db.query(BillingConfig).filter(BillingConfig.is_default == True).update(
            {"is_default": False}
        )

    config = BillingConfig(
        name=data.name,
        billing_method=data.billing_method,
        unit_price=data.unit_price,
        is_default=data.is_default,
        notes=data.notes,
    )
    db.add(config)
    db.commit()
    db.refresh(config)
    return {"id": config.id, "name": config.name, "message": "配置已创建"}


@router.put("/config/{config_id}")
def update_billing_config(
    config_id: int,
    data: BillingConfigCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    config = db.query(BillingConfig).filter(BillingConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")

    if data.is_default:
        db.query(BillingConfig).filter(BillingConfig.is_default == True, BillingConfig.id != config_id).update(
            {"is_default": False}
        )

    config.name = data.name
    config.billing_method = data.billing_method
    config.unit_price = data.unit_price
    config.is_default = data.is_default
    config.notes = data.notes
    db.commit()
    return {"message": "配置已更新"}


@router.delete("/config/{config_id}")
def delete_billing_config(
    config_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    config = db.query(BillingConfig).filter(BillingConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")
    db.delete(config)
    db.commit()
    return {"message": "已删除"}


# ==================== 工作分类 ====================

@router.get("/work-categories")
def get_work_categories():
    return [
        {"value": "legal_research", "label": "法律研究"},
        {"value": "drafting", "label": "文书起草"},
        {"value": "hearing", "label": "庭审出庭"},
        {"value": "consultation", "label": "客户咨询"},
        {"value": "other", "label": "其他"},
    ]


# ==================== 账单管理 ====================

@router.get("/bills")
def list_bills(
    client_id: Optional[int] = Query(None),
    status: str = Query(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(Bill)
    if client_id:
        q = q.filter(Bill.client_id == client_id)
    if status:
        q = q.filter(Bill.status == status)

    bills = q.order_by(Bill.generated_at.desc()).all()
    return [_bill_to_dict(b) for b in bills]


@router.get("/bills/{bill_id}")
def get_bill(
    bill_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    bill = db.query(Bill).filter(Bill.id == bill_id).first()
    if not bill:
        raise HTTPException(status_code=404, detail="账单不存在")
    return _bill_to_dict(bill)


@router.post("/bills/generate")
def generate_bill(
    data: BillGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """生成账单：从工时记录自动计算费用"""
    # 校验客户
    client = db.query(Client).filter(Client.id == data.client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="客户不存在")

    start = _parse_dt(data.period_start)
    end = _parse_dt(data.period_end)

    # 生成明细
    items_data = generate_bill_items(db, data.client_id, start, end, data.case_id)
    if not items_data:
        raise HTTPException(status_code=400, detail="该计费期间内没有未计费的工时记录")

    # 生成账单号
    now = datetime.now()
    bill_number = f"BILL-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}"

    # 创建账单
    total = sum(it["amount"] for it in items_data)
    bill = Bill(
        bill_number=bill_number,
        client_id=data.client_id,
        billing_period_start=start,
        billing_period_end=end,
        total_amount=total,
        status="generated",
        notes=data.notes or f"{data.firm_name or ''} - 账单",
        firm_name=data.firm_name or "",
        firm_address=data.firm_address or "",
        firm_phone=data.firm_phone or "",
        lawyer_name=data.lawyer_name or "",
        bank_info=data.bank_info or "",
    )
    db.add(bill)
    db.flush()

    # 创建账单明细 & 标记工时已计费
    for item_data in items_data:
        item = BillItem(
            bill_id=bill.id,
            case_id=item_data.get("case_id"),
            description=item_data["description"],
            billing_method=item_data["billing_method"],
            unit_price=item_data["unit_price"],
            quantity=item_data["quantity"],
            amount=item_data["amount"],
            work_record_ids=item_data.get("work_record_ids", ""),
        )
        db.add(item)

        # 标记关联的工时记录
        for rid in item_data.get("time_record_ids", []):
            tr = db.query(TimeRecord).filter(TimeRecord.id == rid).first()
            if tr:
                tr.is_billed = True
                tr.bill_item_id = item.id

        # 标记关联的常法工作记录
        wr_ids_str = item_data.get("work_record_ids", "")
        if wr_ids_str:
            try:
                wr_ids = json.loads(wr_ids_str)
                for wr_id in wr_ids:
                    wr = db.query(WorkRecord).filter(WorkRecord.id == wr_id).first()
                    if wr:
                        wr.is_billed = 1
                        wr.bill_item_id = item.id
            except (json.JSONDecodeError, TypeError):
                pass

    db.commit()
    db.refresh(bill)

    return {
        **_bill_to_dict(bill),
        "firm_info": {
            "firm_name": data.firm_name,
            "firm_address": data.firm_address,
            "firm_phone": data.firm_phone,
            "lawyer_name": data.lawyer_name,
            "notes": data.notes,
            "bank_info": data.bank_info,
        },
    }


@router.post("/bills/batch-generate")
def batch_generate_bills(
    data: BillGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """周期批量出账：为所有有未计费工时的客户一键生成账单

    适用场景：月底/年底统一出账
    """
    start = _parse_dt(data.period_start)
    end = _parse_dt(data.period_end)

    # 查找计费期间内有未计费工时的所有客户
    from app.models.client import Client as ClientModel

    # 先找到所有未计费的工时记录
    unbilled = db.query(TimeRecord).filter(
        TimeRecord.is_billed == False,
        TimeRecord.start_time >= start,
        TimeRecord.end_time <= end,
    ).all()

    if not unbilled:
        raise HTTPException(status_code=400, detail="该期间内没有未计费的工时记录")

    # 按客户分组（通过案件关联找到客户）
    # 收集所有涉及的 case_id
    case_ids = list(set(r.case_id for r in unbilled if r.case_id))
    if not case_ids:
        raise HTTPException(status_code=400, detail="未计费工时没有关联案件，无法确定客户")

    # 找到这些案件关联的客户
    from app.models.case_client import case_clients
    client_case_map: dict[int, list[int]] = {}  # client_id -> [case_ids]
    for row in db.query(case_clients).filter(case_clients.c.case_id.in_(case_ids)).all():
        cid = row.client_id
        case_id = row.case_id
        if cid not in client_case_map:
            client_case_map[cid] = []
        client_case_map[cid].append(case_id)

    if not client_case_map:
        raise HTTPException(status_code=400, detail="未计费工时的案件没有关联客户")

    now = datetime.now()
    generated_bills = []
    errors = []

    for client_id, cids in client_case_map.items():
        # 获取该客户在这些案件中的未计费工时
        client_records = [r for r in unbilled if r.case_id in cids]
        if not client_records:
            continue

        # 检查是否有足够的记录（至少有有效时长的）
        valid_records = [r for r in client_records if r.duration_minutes > 0]
        if not valid_records:
            continue

        try:
            # 为该客户生成明细
            items_data = generate_bill_items(db, client_id, start, end)
            if not items_data:
                continue

            total = sum(it["amount"] for it in items_data)
            bill_number = f"BILL-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}"

            bill = Bill(
                bill_number=bill_number,
                client_id=client_id,
                billing_period_start=start,
                billing_period_end=end,
                total_amount=total,
                status="generated",
                notes=data.notes or f"周期出账 {data.period_start} ~ {data.period_end}",
                firm_name=data.firm_name or "",
                firm_address=data.firm_address or "",
                firm_phone=data.firm_phone or "",
                lawyer_name=data.lawyer_name or "",
                bank_info=data.bank_info or "",
            )
            db.add(bill)
            db.flush()

            for item_data in items_data:
                item = BillItem(
                    bill_id=bill.id,
                    case_id=item_data.get("case_id"),
                    description=item_data["description"],
                    billing_method=item_data["billing_method"],
                    unit_price=item_data["unit_price"],
                    quantity=item_data["quantity"],
                    amount=item_data["amount"],
                    work_record_ids=item_data.get("work_record_ids", ""),
                )
                db.add(item)

                for rid in item_data.get("time_record_ids", []):
                    tr = db.query(TimeRecord).filter(TimeRecord.id == rid).first()
                    if tr:
                        tr.is_billed = True
                        tr.bill_item_id = item.id

                # 标记关联的常法工作记录
                wr_ids_str = item_data.get("work_record_ids", "")
                if wr_ids_str:
                    try:
                        wr_ids = json.loads(wr_ids_str)
                        for wr_id in wr_ids:
                            wr = db.query(WorkRecord).filter(WorkRecord.id == wr_id).first()
                            if wr:
                                wr.is_billed = 1
                                wr.bill_item_id = item.id
                    except (json.JSONDecodeError, TypeError):
                        pass

            db.flush()
            generated_bills.append(bill)

        except Exception as e:
            errors.append(f"客户 #{client_id} 出账失败: {str(e)}")
            continue

    if not generated_bills:
        db.rollback()
        raise HTTPException(status_code=400, detail="没有可生成的账单" + (f"（错误: {'; '.join(errors)}）" if errors else ""))

    db.commit()

    result_bills = []
    for b in generated_bills:
        db.refresh(b)
        result_bills.append(_bill_to_dict(b))

    return {
        "message": f"成功生成 {len(generated_bills)} 份账单",
        "period": f"{data.period_start} ~ {data.period_end}",
        "bills": result_bills,
        "total_clients": len(client_case_map),
        "total_amount": sum(b.total_amount for b in generated_bills),
        "errors": errors if errors else None,
        "firm_info": {
            "firm_name": data.firm_name,
            "firm_address": data.firm_address,
            "firm_phone": data.firm_phone,
            "lawyer_name": data.lawyer_name,
            "notes": data.notes,
            "bank_info": data.bank_info,
        },
    }


@router.get("/bills/{bill_id}/pdf")
def export_bill_pdf(
    bill_id: int,
    firm_name: str = Query(""),
    firm_address: str = Query(""),
    firm_phone: str = Query(""),
    lawyer_name: str = Query(""),
    notes: str = Query(""),
    bank_info: str = Query(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """导出账单为 PDF"""
    bill = db.query(Bill).filter(Bill.id == bill_id).first()
    if not bill:
        raise HTTPException(status_code=404, detail="账单不存在")

    client = db.query(Client).filter(Client.id == bill.client_id).first()

    # 构建 PDF 数据：优先用 Bill 存储的，其次用查询参数
    pdf_data = {
        "bill_number": bill.bill_number,
        "client_name": client.name if client else "",
        "client_contact": client.contact_person if client else "",
        "period_start": bill.billing_period_start.strftime("%Y-%m-%d") if bill.billing_period_start else "",
        "period_end": bill.billing_period_end.strftime("%Y-%m-%d") if bill.billing_period_end else "",
        "items": [],
        "total_amount": f"{bill.total_amount:,.2f}",
        "total_cn": amount_to_chinese(bill.total_amount),
        "firm_name": bill.firm_name or firm_name or "律师事务所",
        "firm_address": bill.firm_address or firm_address or "",
        "firm_phone": bill.firm_phone or firm_phone or "",
        "lawyer_name": bill.lawyer_name or lawyer_name or "",
        "notes": notes or bill.notes or "",
        "bank_info": bill.bank_info or bank_info or "",
    }

    method_labels = {"hourly": "按小时", "fixed": "按件", "percentage": "按比例"}
    for item in bill.items:
        pdf_data["items"].append({
            "description": item.description,
            "method": method_labels.get(item.billing_method, item.billing_method),
            "qty": f"{item.quantity:.1f}小时" if item.billing_method == "hourly" else f"{item.quantity:.0f}件",
            "unit_price": f"{item.unit_price:,.2f}元",
            "amount": f"{item.amount:,.2f}",
        })

    tmp_dir = os.path.join(settings.UPLOAD_DIR, "temp")
    os.makedirs(tmp_dir, exist_ok=True)
    pdf_path = generate_bill_pdf(tmp_dir, pdf_data)

    if not pdf_path:
        raise HTTPException(status_code=500, detail="PDF 生成失败")

    # 更新导出时间
    bill.exported_at = datetime.now()
    bill.status = "exported"
    db.commit()

    return FileResponse(
        path=pdf_path,
        filename=f"{bill.bill_number}.pdf",
        media_type="application/pdf",
    )


@router.put("/bills/{bill_id}/status")
def update_bill_status(
    bill_id: int,
    status: str = Body(..., embed=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新账单状态（draft/generated/exported/paid）"""
    bill = db.query(Bill).filter(Bill.id == bill_id).first()
    if not bill:
        raise HTTPException(status_code=404, detail="账单不存在")
    if status not in ("draft", "generated", "exported", "paid"):
        raise HTTPException(status_code=400, detail="无效状态")
    bill.status = status
    if status == "paid":
        bill.exported_at = datetime.now()
    db.commit()
    return {"message": "状态已更新"}


@router.delete("/bills/{bill_id}")
def delete_bill(
    bill_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    bill = db.query(Bill).filter(Bill.id == bill_id).first()
    if not bill:
        raise HTTPException(status_code=404, detail="账单不存在")
    # 取消关联工时的计费标记
    for item in bill.items:
        db.query(TimeRecord).filter(TimeRecord.bill_item_id == item.id).update(
            {"is_billed": False, "bill_item_id": None}
        )
        # 取消关联的常法工作记录计费标记
        if item.work_record_ids:
            try:
                wr_ids = json.loads(item.work_record_ids)
                for wr_id in wr_ids:
                    wr = db.query(WorkRecord).filter(WorkRecord.id == wr_id).first()
                    if wr:
                        wr.is_billed = 0
                        wr.bill_item_id = None
            except (json.JSONDecodeError, TypeError):
                pass
    db.delete(bill)
    db.commit()
    return {"message": "已删除"}


# ==================== 收入统计 ====================

@router.get("/revenue-stats")
def get_revenue_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """收入统计：本月创收、本月回款、未回款总额"""
    from datetime import date, timedelta
    from calendar import monthrange

    today = date.today()
    month_start = date(today.year, today.month, 1)
    month_end = date(today.year, today.month, monthrange(today.year, today.month)[1])

    # 本月生成的账单总金额（创收）
    # 使用 < month_end+1 避免漏掉最后一天有时间的记录
    month_revenue = db.query(Bill).filter(
        Bill.generated_at >= month_start,
        Bill.generated_at < month_end + timedelta(days=1),
    ).all()
    month_total = sum(b.total_amount for b in month_revenue)

    # 本月回款
    month_paid = sum(b.amount_paid or 0 for b in month_revenue)

    # 所有账单未回款总额
    all_bills = db.query(Bill).all()
    all_total = sum(b.total_amount for b in all_bills)
    all_paid = sum(b.amount_paid or 0 for b in all_bills)
    unpaid_total = all_total - all_paid

    return {
        "month_revenue": round(month_total, 2),
        "month_paid": round(month_paid, 2),
        "unpaid_total": round(unpaid_total, 2),
        "total_revenue": round(all_total, 2),
        "total_paid": round(all_paid, 2),
    }


@router.get("/revenue-trend")
def get_revenue_trend(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """近6个月收入趋势（每月创收 + 回款）"""
    from datetime import date, timedelta
    from calendar import monthrange

    today = date.today()
    trend = []

    for i in range(5, -1, -1):
        # 计算 i 个月前的月份
        year = today.year
        month = today.month - i
        while month <= 0:
            month += 12
            year -= 1

        month_start = date(year, month, 1)
        month_end = date(year, month, monthrange(year, month)[1])

        bills = db.query(Bill).filter(
            Bill.generated_at >= month_start,
            Bill.generated_at < month_end + timedelta(days=1),
        ).all()

        trend.append({
            "month": f"{year}-{month:02d}",
            "label": f"{month}月",
            "revenue": round(sum(b.total_amount for b in bills), 2),
            "paid": round(sum(b.amount_paid or 0 for b in bills), 2),
        })

    return {"trend": trend}


@router.get("/case-revenue")
def get_case_revenue(
    limit: int = Query(10),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """案件收入排行（按账单明细汇总）"""
    from sqlalchemy import func as sql_func
    from app.models.case import Case as CaseModel

    # 按 case_id 汇总 bill_items.amount
    rows = db.query(
        BillItem.case_id,
        sql_func.sum(BillItem.amount).label("total")
    ).filter(
        BillItem.case_id.isnot(None)
    ).group_by(BillItem.case_id).order_by(
        sql_func.sum(BillItem.amount).desc()
    ).limit(limit).all()

    result = []
    for case_id, total in rows:
        case = db.query(CaseModel).filter(CaseModel.id == case_id).first()
        result.append({
            "case_id": case_id,
            "case_number": case.case_number if case else "",
            "case_reason": case.case_reason if case else "",
            "total": round(total, 2),
        })

    return {"items": result}


# ==================== 回款标记 ====================

@router.put("/bills/{bill_id}/pay")
def mark_bill_paid(
    bill_id: int,
    amount_paid: float = Body(..., embed=True),
    paid_date: str = Body(None, embed=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """标记账单回款"""
    bill = db.query(Bill).filter(Bill.id == bill_id).first()
    if not bill:
        raise HTTPException(status_code=404, detail="账单不存在")

    bill.amount_paid = amount_paid
    if paid_date:
        try:
            bill.paid_date = datetime.fromisoformat(paid_date)
        except (ValueError, TypeError):
            bill.paid_date = datetime.now()
    else:
        bill.paid_date = datetime.now()

    # 如果全额回款，自动更新状态
    if bill.amount_paid >= bill.total_amount and bill.status != "paid":
        bill.status = "paid"

    db.commit()
    db.refresh(bill)
    return _bill_to_dict(bill)
