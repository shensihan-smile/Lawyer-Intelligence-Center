"""计费引擎：根据计费配置和工时记录计算费用"""
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.billing import BillingConfig, TimeRecord, BillItem
from app.models.case import Case


def get_case_billing_rate(case: Case | None, db: Session) -> dict:
    """获取案件的有效计费配置

    优先级：案件覆盖 > 全局默认 > 系统硬编码默认值

    Returns:
        {"billing_method": "hourly", "unit_price": 2000.0}
    """
    # 1. 案件级覆盖
    if case and case.billing_method and case.billing_rate is not None:
        return {
            "billing_method": case.billing_method,
            "unit_price": case.billing_rate,
            "source": "case",
        }

    # 2. 全局默认
    config = db.query(BillingConfig).filter(
        BillingConfig.is_default == True
    ).first()
    if config:
        return {
            "billing_method": config.billing_method,
            "unit_price": config.unit_price,
            "source": "global",
        }

    # 3. 硬编码默认
    return {
        "billing_method": "hourly",
        "unit_price": 2000.0,
        "source": "default",
    }


def calculate_record_amount(
    record: TimeRecord,
    db: Session,
) -> float:
    """计算单条工时记录的费用

    - 按小时：时长(小时) × 小时费率
    - 按件：固定费用（忽略时长）
    - 按比例：标的额 × 百分比（需要案件信息）
    """
    case = record.case
    rate_info = get_case_billing_rate(case, db)
    method = rate_info["billing_method"]
    unit_price = rate_info["unit_price"]

    if method == "fixed":
        # 按件计费：固定价格
        return unit_price

    elif method == "percentage":
        # 按标的额比例
        if case and case.amount_in_dispute > 0:
            return case.amount_in_dispute * unit_price / 100.0
        return 0

    else:
        # hourly（默认）：按时长 × 费率
        hours = record.duration_minutes / 60.0
        return round(hours * unit_price, 2)


def generate_bill_items(
    db: Session,
    client_id: int,
    start_date: datetime,
    end_date: datetime,
    case_id: int | None = None,
) -> list[dict]:
    """为指定客户生成账单明细

    从工时记录中聚合未计费项目，计算费用

    Returns:
        [{"description": "...", "billing_method": "hourly", "unit_price": 2000, "quantity": 3.5, "amount": 7000, "time_record_ids": [1,2,3]}, ...]
    """
    # 查询该客户关联的案件的未计费工时
    from app.models.client import Client

    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        return []

    # 获取客户关联的所有案件 ID
    case_ids = [c.id for c in client.cases]
    if case_id and case_id in case_ids:
        case_ids = [case_id]

    if not case_ids:
        return []

    # 查询未计费工时记录
    q = db.query(TimeRecord).filter(
        TimeRecord.case_id.in_(case_ids),
        TimeRecord.is_billed == False,
        TimeRecord.start_time >= start_date,
        TimeRecord.end_time <= end_date,
    ).order_by(TimeRecord.case_id, TimeRecord.work_category, TimeRecord.start_time)

    records = q.all()
    if not records:
        return []

    # 按 案件 + 工作分类 分组
    groups: dict[tuple, list[TimeRecord]] = {}
    for r in records:
        key = (r.case_id, r.work_category)
        groups.setdefault(key, []).append(r)

    WORK_CATEGORY_LABELS = {
        "legal_research": "法律研究",
        "drafting": "文书起草",
        "hearing": "庭审出庭",
        "consultation": "客户咨询",
        "other": "其他",
    }

    items = []
    for (cid, cat), group_records in groups.items():
        case = db.query(Case).filter(Case.id == cid).first()
        rate_info = get_case_billing_rate(case, db)

        # 计算该组的总时长和总费用
        total_minutes = sum(r.duration_minutes for r in group_records)
        total_amount = sum(calculate_record_amount(r, db) for r in group_records)

        items.append({
            "case_id": cid,
            "case_number": case.case_number if case else "",
            "description": f"{case.case_number + ' - ' if case else ''}{WORK_CATEGORY_LABELS.get(cat, cat)}",
            "billing_method": rate_info["billing_method"],
            "unit_price": rate_info["unit_price"],
            "quantity": round(total_minutes / 60.0, 1),
            "amount": round(total_amount, 2),
            "time_record_ids": [r.id for r in group_records],
        })

    return items
