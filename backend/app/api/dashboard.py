"""仪表盘聚合数据 API"""
from datetime import date, datetime, timedelta
from calendar import monthrange
from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.case import Case
from app.models.client import Client
from app.models.document import Document
from app.models.schedule import Schedule
from app.models.task import Task
from app.models.billing import Bill, TimeRecord
from app.models.preservation import PreservationRecord
from app.models.retainer import RetainerClient
from app.models.user import User

router = APIRouter()


def _days_until(end_date_val) -> int:
    """计算距到期日的天数（已过期返回负数）"""
    if not end_date_val:
        return 9999
    if isinstance(end_date_val, str):
        end_date_val = date.fromisoformat(end_date_val[:10])
    elif isinstance(end_date_val, datetime):
        end_date_val = end_date_val.date()
    return (end_date_val - date.today()).days


def _case_stage_name(raw: str) -> str:
    """标准化案件阶段名称"""
    if not raw:
        return "接案"
    mapping = {
        "接案": "接案", "立案": "立案", "审理中": "审理中",
        "判决": "判决", "执行": "执行", "结案": "结案",
        "closed": "结案", "paused": "暂缓",
        "intake": "接案", "jiean": "接案", "filing": "立案",
        "trial": "审理中", "judgment": "判决",
        "enforcement": "执行", "暂缓": "暂缓",
    }
    return mapping.get(raw.strip(), raw.strip() or "接案")


@router.get("")
def get_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """仪表盘聚合数据 — 首页所有卡片和预警信息"""
    today = date.today()
    month_start = date(today.year, today.month, 1)
    month_end = date(today.year, today.month, monthrange(today.year, today.month)[1])

    # ========== 1. 数字卡片 ==========
    # 在办案件数
    all_cases = db.query(Case).all()
    active_cases = [c for c in all_cases if c.case_stage not in ("结案", "closed")]
    active_count = len(active_cases)

    # 常法客户数（服务中）
    retainer_count = db.query(RetainerClient).filter(
        RetainerClient.deleted == False,
        RetainerClient.status == "active",
    ).count()

    # 本月工时（分钟 → 小时，保留1位小数）
    month_time_records = db.query(TimeRecord).filter(
        TimeRecord.start_time >= month_start,
        TimeRecord.start_time < month_end + timedelta(days=1),
    ).all()
    total_minutes = sum(r.duration_minutes or 0 for r in month_time_records)
    month_hours = round(total_minutes / 60.0, 1)

    # 本月创收
    month_bills = db.query(Bill).filter(
        Bill.generated_at >= month_start,
        Bill.generated_at < month_end + timedelta(days=1),
    ).all()
    month_revenue = round(sum(b.total_amount for b in month_bills), 2)

    # 待续期保全数（已过期 + 7天内到期）
    all_preservations = db.query(PreservationRecord).filter(
        PreservationRecord.status == "active"
    ).all()
    urgent_preservation_count = 0
    for p in all_preservations:
        days = _days_until(p.end_date)
        if days <= 7:
            urgent_preservation_count += 1

    stats = {
        "active_cases": active_count,
        "retainer_clients": retainer_count,
        "monthly_hours": month_hours,
        "monthly_revenue": month_revenue,
        "urgent_preservations": urgent_preservation_count,
    }

    # ========== 2. 顶部预警横幅 ==========
    warnings = []

    # 2.1 保全到期预警（优先级最高）
    for p in all_preservations:
        days = _days_until(p.end_date)
        if days <= 30:
            case = db.query(Case).filter(Case.id == p.case_id).first()
            warnings.append({
                "type": "preservation",
                "priority": "highest" if days <= 7 else "high",
                "days_until": days,
                "label": f"{p.preservation_type}到期" + (f"还有{days}天" if days > 0 else f"已过期{abs(days)}天"),
                "detail": f"{p.preservation_type}（{p.target[:30] if p.target else ''}）{'还有'+str(days)+'天到期' if days > 0 else '已过期'+str(abs(days))+'天，请立即申请续期'}",
                "case_id": p.case_id,
                "case_number": case.case_number if case else "",
                "case_reason": case.case_reason if case else "",
                "link": f"case:{p.case_id}" if case else "",
            })

    # 2.2 诉讼期限预警（从日程表中的 source_deadline 字段提取）
    deadline_schedules = db.query(Schedule).filter(
        Schedule.source_deadline != "",
        Schedule.start_time >= today,
    ).order_by(Schedule.start_time.asc()).all()

    for s in deadline_schedules:
        days = _days_until(s.start_time)
        if days <= 30:
            case = db.query(Case).filter(Case.id == s.case_id).first() if s.case_id else None
            deadline_label_map = {
                "举证期限": "举证期限",
                "上诉截止": "上诉截止",
                "申请执行截止": "申请执行截止",
                "保全到期": "保全到期",
            }
            dl_type = deadline_label_map.get(s.source_deadline, s.source_deadline)
            warnings.append({
                "type": "deadline",
                "priority": "high" if days <= 7 else "medium",
                "days_until": days,
                "label": f"{dl_type}截止" + (f"还有{days}天" if days > 0 else f"已逾期{abs(days)}天"),
                "detail": f"{dl_type}截止还有{days}天" + (f"（案件：{case.case_reason or case.case_number}）" if case else ""),
                "case_id": s.case_id,
                "case_number": case.case_number if case else "",
                "case_reason": case.case_reason if case else "",
                "link": f"case:{s.case_id}" if s.case_id else "",
            })

    # 2.3 开庭预警（近7天的庭审日程）
    upcoming_hearings = db.query(Schedule).filter(
        Schedule.schedule_type == "hearing",
        Schedule.start_time >= today,
        Schedule.start_time < today + timedelta(days=7),
    ).order_by(Schedule.start_time.asc()).all()

    for s in upcoming_hearings:
        days = _days_until(s.start_time)
        case = db.query(Case).filter(Case.id == s.case_id).first() if s.case_id else None
        warnings.append({
            "type": "hearing",
            "priority": "medium",
            "days_until": days,
            "label": f"开庭提醒还有{days}天" if days > 0 else "今日开庭",
            "detail": (f"{s.title or '庭审'}还有{days}天" if days > 0 else f"今日开庭：{s.title or ''}") + (
                f"（案件：{case.case_reason or case.case_number}）" if case else ""),
            "case_id": s.case_id,
            "case_number": case.case_number if case else "",
            "case_reason": case.case_reason if case else "",
            "link": f"case:{s.case_id}" if s.case_id else "",
        })

    # 按优先级和天数排序
    priority_order = {"highest": 0, "high": 1, "medium": 2}
    warnings.sort(key=lambda w: (priority_order.get(w["priority"], 9), w["days_until"]))

    # ========== 3. 今日待办 ==========
    today_todos = []

    # 3.1 今日日程
    today_schedules = db.query(Schedule).filter(
        func.date(Schedule.start_time) == today.isoformat(),
    ).order_by(Schedule.start_time.asc()).all()

    for s in today_schedules:
        case = db.query(Case).filter(Case.id == s.case_id).first() if s.case_id else None
        today_todos.append({
            "source": "schedule",
            "id": s.id,
            "title": s.title,
            "type": s.schedule_type,
            "time": s.start_time.strftime("%H:%M") if s.start_time else "",
            "case_id": s.case_id,
            "case_number": case.case_number if case else "",
            "location": s.location or "",
            "completed": False,
        })

    # 3.2 今日任务
    today_tasks = db.query(Task).filter(
        func.date(Task.due_date) == today.isoformat(),
        Task.status.in_(("pending", "in_progress")),
    ).order_by(Task.priority.desc(), Task.due_date.asc()).all()

    for t in today_tasks:
        case = db.query(Case).filter(Case.id == t.case_id).first() if t.case_id else None
        today_todos.append({
            "source": "task",
            "id": t.id,
            "title": t.title,
            "type": t.priority,
            "time": t.due_date.strftime("%H:%M") if t.due_date else "",
            "case_id": t.case_id,
            "case_number": case.case_number if case else "",
            "location": "",
            "completed": t.status == "completed",
        })

    # 按时间排列
    today_todos.sort(key=lambda x: x["time"] or "99:99")

    # ========== 4. 案件阶段分布（在办案件） ==========
    stage_counts = {}
    for c in active_cases:
        stage = _case_stage_name(c.case_stage)
        stage_counts[stage] = stage_counts.get(stage, 0) + 1

    # 按阶段流程排序
    stage_order = ["接案", "立案", "审理中", "判决", "执行", "暂缓"]
    stage_distribution = [
        {"stage": s, "count": stage_counts.get(s, 0)}
        for s in stage_order
        if stage_counts.get(s, 0) > 0
    ]

    # ========== 5. 最近更新的案件（前5） ==========
    recent_cases_q = db.query(Case).filter(
        Case.case_stage.notin_(["结案", "closed"])
    ).order_by(Case.updated_at.desc()).limit(5).all()

    recent_cases = []
    for c in recent_cases_q:
        recent_cases.append({
            "id": c.id,
            "case_number": c.case_number,
            "case_reason": c.case_reason or "",
            "case_stage": _case_stage_name(c.case_stage),
            "court": c.court or "",
            "updated_at": c.updated_at.isoformat() if c.updated_at else "",
        })

    # ========== 6. 最近文档（前3） ==========
    recent_docs_q = db.query(Document).order_by(
        Document.uploaded_at.desc()
    ).limit(3).all()

    recent_docs = []
    for d in recent_docs_q:
        case = db.query(Case).filter(Case.id == d.case_id).first() if d.case_id else None
        recent_docs.append({
            "id": d.id,
            "original_name": d.original_name or d.filename,
            "doc_category": d.doc_category or "",
            "case_id": d.case_id,
            "case_number": case.case_number if case else "",
            "uploaded_at": d.uploaded_at.isoformat() if d.uploaded_at else "",
        })

    return {
        "stats": stats,
        "warnings": warnings,
        "today_todos": today_todos,
        "stage_distribution": stage_distribution,
        "recent_cases": recent_cases,
        "recent_docs": recent_docs,
    }
