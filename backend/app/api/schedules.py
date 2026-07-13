"""日程管理 API"""
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, Body, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from app.core.database import get_db
from app.core.auth import get_current_user, get_current_user_optional
from app.models.schedule import Schedule
from app.models.case import Case
from app.models.user import User
from app.services.sms_parser import parse_sms

router = APIRouter()


# ---------- Pydantic schemas ----------

class ScheduleCreate(BaseModel):
    title: str
    schedule_type: str = "other"  # hearing/meeting/consultation/deadline/other
    case_id: Optional[int] = None
    start_time: str               # ISO 格式
    end_time: str                 # ISO 格式
    location: str = ""
    judge: str = ""
    notes: str = ""
    is_parsed_from_sms: bool = False


class ScheduleUpdate(BaseModel):
    title: Optional[str] = None
    schedule_type: Optional[str] = None
    case_id: Optional[int] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    location: Optional[str] = None
    judge: Optional[str] = None
    notes: Optional[str] = None


# ---------- Helpers ----------

def _schedule_to_dict(s: Schedule) -> dict:
    """将 Schedule ORM 对象转为字典"""
    return {
        "id": s.id,
        "title": s.title,
        "schedule_type": s.schedule_type,
        "case_id": s.case_id,
        "case_number": s.case.case_number if s.case else None,
        "case_reason": s.case.case_reason if s.case else None,
        "start_time": s.start_time.isoformat() if s.start_time else None,
        "end_time": s.end_time.isoformat() if s.end_time else None,
        "location": s.location,
        "judge": s.judge,
        "notes": s.notes,
        "is_parsed_from_sms": s.is_parsed_from_sms,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


def _parse_dt(value: str) -> datetime:
    """将 ISO 字符串转为 datetime"""
    if not value:
        raise HTTPException(status_code=400, detail="时间不能为空")
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail=f"无效的时间格式: {value}")


def _check_conflict(db: Session, start: datetime, end: datetime, exclude_id: int = None) -> list:
    """检测时间冲突：同一时段存在两个以上日程"""
    q = db.query(Schedule).filter(
        Schedule.start_time < end,
        Schedule.end_time > start,
    )
    if exclude_id:
        q = q.filter(Schedule.id != exclude_id)
    conflicts = q.all()
    return [_schedule_to_dict(c) for c in conflicts]


# ---------- Routes ----------

@router.get("/")
def list_schedules(
    start_date: str = Query("", description="开始日期 YYYY-MM-DD"),
    end_date: str = Query("", description="结束日期 YYYY-MM-DD"),
    schedule_type: str = Query("", description="按类型筛选"),
    case_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取日程列表，支持日期范围筛选"""
    q = db.query(Schedule)

    if start_date:
        try:
            sd = datetime.fromisoformat(start_date)
            q = q.filter(Schedule.start_time >= sd)
        except ValueError:
            pass
    if end_date:
        try:
            ed = datetime.fromisoformat(end_date) + timedelta(days=1)
            q = q.filter(Schedule.end_time < ed)
        except ValueError:
            pass
    if schedule_type:
        q = q.filter(Schedule.schedule_type == schedule_type)
    if case_id:
        q = q.filter(Schedule.case_id == case_id)

    schedules = q.order_by(Schedule.start_time.asc()).all()
    return [_schedule_to_dict(s) for s in schedules]


@router.get("/types")
def get_schedule_types():
    """获取日程类型列表"""
    return [
        {"value": "hearing", "label": "开庭"},
        {"value": "meeting", "label": "会议"},
        {"value": "consultation", "label": "咨询"},
        {"value": "deadline", "label": "截止日期"},
        {"value": "other", "label": "其他"},
    ]


@router.get("/conflicts")
def check_conflicts(
    start: str = Query(...),
    end: str = Query(...),
    exclude_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """检测指定时间段是否存在冲突"""
    start_dt = _parse_dt(start)
    end_dt = _parse_dt(end)
    conflicts = _check_conflict(db, start_dt, end_dt, exclude_id)
    return {"has_conflict": len(conflicts) > 0, "conflicts": conflicts}


@router.get("/reminders")
def get_reminders(
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    """获取当前需要提醒的日程

    规则：
    - 开庭前 3 天、1 天、2 小时需要提醒
    - 其他类型日程：开始前 1 天、1 小时提醒
    """
    now = datetime.now()
    # 查询从现在到未来 4 天内的所有日程
    future = now + timedelta(days=4)
    schedules = db.query(Schedule).filter(
        Schedule.start_time >= now,
        Schedule.start_time <= future,
    ).order_by(Schedule.start_time.asc()).all()

    reminders = []
    for s in schedules:
        time_until = s.start_time - now
        hours_until = time_until.total_seconds() / 3600

        due_reminders = []

        if s.schedule_type == "hearing":
            # 开庭：3 天、1 天、2 小时
            for label, threshold, key in [
                ("距开庭还有 3 天", 72, "hearing_3d"),
                ("距开庭还有 1 天", 24, "hearing_1d"),
                ("距开庭还有 2 小时", 2, "hearing_2h"),
            ]:
                if 0 < hours_until <= threshold and hours_until > threshold * 0.8:
                    due_reminders.append({"key": key, "label": label, "hours_remaining": round(hours_until, 1)})
        else:
            # 其他：1 天、1 小时
            for label, threshold, key in [
                ("日程即将开始（1 天内）", 24, "general_1d"),
                ("日程即将开始（1 小时内）", 1, "general_1h"),
            ]:
                if 0 < hours_until <= threshold and hours_until > threshold * 0.8:
                    due_reminders.append({"key": key, "label": label, "hours_remaining": round(hours_until, 1)})

        if due_reminders:
            reminders.append({
                "schedule": _schedule_to_dict(s),
                "reminders": due_reminders,
            })

    return reminders


@router.get("/export-ical")
def export_ical(
    start_date: str = Query(""),
    end_date: str = Query(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """导出日程为 iCal 格式（可导入手机日历、Outlook 等）"""
    q = db.query(Schedule)
    if start_date:
        try:
            q = q.filter(Schedule.start_time >= datetime.fromisoformat(start_date))
        except ValueError:
            pass
    if end_date:
        try:
            q = q.filter(Schedule.end_time < datetime.fromisoformat(end_date) + timedelta(days=1))
        except ValueError:
            pass
    schedules = q.order_by(Schedule.start_time.asc()).all()

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//律师智能中心//日程导出//CN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:律师智能中心 - 日程",
    ]

    for s in schedules:
        # 格式化时间为 iCal UTC 格式
        def to_ical_dt(dt: datetime) -> str:
            return dt.strftime("%Y%m%dT%H%M%S")

        lines.append("BEGIN:VEVENT")
        lines.append(f"UID:schedule-{s.id}@lawyer-center")
        lines.append(f"DTSTART:{to_ical_dt(s.start_time)}")
        lines.append(f"DTEND:{to_ical_dt(s.end_time)}")
        lines.append(f"SUMMARY:{s.title}")
        if s.location:
            lines.append(f"LOCATION:{s.location}")
        if s.notes:
            lines.append(f"DESCRIPTION:{s.notes}")
        if s.case:
            lines.append(f"CATEGORIES:案件-{s.case.case_number}")
        lines.append("END:VEVENT")

    lines.append("END:VCALENDAR")

    return PlainTextResponse(
        content="\r\n".join(lines),
        media_type="text/calendar",
        headers={"Content-Disposition": "attachment; filename=lawyer_schedule.ics"},
    )


@router.get("/{schedule_id}")
def get_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取单个日程详情"""
    s = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="日程不存在")
    return _schedule_to_dict(s)


@router.post("/")
def create_schedule(
    data: ScheduleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建新日程，自动检测冲突"""
    start_dt = _parse_dt(data.start_time)
    end_dt = _parse_dt(data.end_time)

    if start_dt >= end_dt:
        raise HTTPException(status_code=400, detail="结束时间必须晚于开始时间")

    # 冲突检测
    conflicts = _check_conflict(db, start_dt, end_dt)

    schedule = Schedule(
        title=data.title,
        schedule_type=data.schedule_type,
        case_id=data.case_id if data.case_id and data.case_id > 0 else None,
        start_time=start_dt,
        end_time=end_dt,
        location=data.location,
        judge=data.judge,
        notes=data.notes,
        is_parsed_from_sms=data.is_parsed_from_sms,
    )
    db.add(schedule)
    db.commit()
    db.refresh(schedule)

    result = _schedule_to_dict(schedule)
    result["conflicts"] = conflicts  # 如果有冲突，提醒前端
    return result


@router.put("/{schedule_id}")
def update_schedule(
    schedule_id: int,
    data: ScheduleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新日程"""
    s = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="日程不存在")

    update_data = data.model_dump(exclude_unset=True)

    # 时间校验 + 冲突检测
    new_start = update_data.get("start_time")
    new_end = update_data.get("end_time")
    if new_start:
        update_data["start_time"] = _parse_dt(new_start)
    if new_end:
        update_data["end_time"] = _parse_dt(new_end)

    check_start = update_data.get("start_time", s.start_time)
    check_end = update_data.get("end_time", s.end_time)

    if isinstance(check_start, str):
        check_start = _parse_dt(check_start)
    if isinstance(check_end, str):
        check_end = _parse_dt(check_end)

    if check_start >= check_end:
        raise HTTPException(status_code=400, detail="结束时间必须晚于开始时间")

    conflicts = _check_conflict(db, check_start, check_end, exclude_id=schedule_id)

    for key, value in update_data.items():
        setattr(s, key, value)

    db.commit()
    db.refresh(s)

    result = _schedule_to_dict(s)
    result["conflicts"] = conflicts
    return result


@router.delete("/{schedule_id}")
def delete_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除日程"""
    s = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="日程不存在")
    db.delete(s)
    db.commit()
    return {"message": "日程删除成功"}


# ==================== 短信解析 ====================

class SmsParseRequest(BaseModel):
    text: str


@router.post("/parse-sms")
def parse_sms_endpoint(
    data: SmsParseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """解析 12368 法院短信，提取庭审信息"""
    result = parse_sms(data.text)

    # 尝试自动匹配案件
    if result.get("case_number") and not result.get("matched_case_id"):
        case = db.query(Case).filter(
            Case.case_number.contains(result["case_number"][:8])
        ).first()
        if case:
            result["matched_case_id"] = case.id
            result["matched_case_name"] = case.case_reason or case.case_number

    return result


@router.post("/create-from-sms")
def create_from_sms(
    sms_text: str = Body(..., embed=True),
    title: str = Body(""),
    schedule_type: str = Body("hearing"),
    notes: str = Body(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """从短信解析结果一键创建日程"""
    parsed = parse_sms(sms_text)

    # 构建时间
    start_dt = None
    hearing_dt_str = parsed.get("hearing_datetime", "")
    if hearing_dt_str:
        try:
            start_dt = datetime.fromisoformat(hearing_dt_str)
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="无法从短信中提取开庭时间，请手动创建")

    if not start_dt:
        raise HTTPException(status_code=400, detail="无法从短信中提取开庭时间，请手动创建")

    end_dt = start_dt + timedelta(hours=3)  # 默认 3 小时

    # 构建标题
    schedule_title = title or f"开庭 - {parsed.get('case_number', '未知案号')}"

    # 构建地点
    location = parsed.get("location", "")

    schedule = Schedule(
        title=schedule_title,
        schedule_type=schedule_type,
        case_id=parsed.get("matched_case_id"),
        start_time=start_dt,
        end_time=end_dt,
        location=location,
        judge=parsed.get("judge", ""),
        notes=notes or f"来源：12368 短信\n案号：{parsed.get('case_number', '')}\n电话：{parsed.get('phone', '')}",
        is_parsed_from_sms=True,
    )
    db.add(schedule)
    db.commit()
    db.refresh(schedule)

    conflicts = _check_conflict(db, start_dt, end_dt)

    result = _schedule_to_dict(schedule)
    result["conflicts"] = conflicts
    result["parsed"] = parsed
    return result
