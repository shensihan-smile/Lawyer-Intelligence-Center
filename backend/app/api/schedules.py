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
    is_all_day: int = 0  # 0=否 1=是
    reminder_setting: str = "3d"  # none/day0/1d/3d/7d
    color: str = ""
    source_deadline: str = ""


class ScheduleUpdate(BaseModel):
    title: Optional[str] = None
    schedule_type: Optional[str] = None
    case_id: Optional[int] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    location: Optional[str] = None
    judge: Optional[str] = None
    notes: Optional[str] = None
    is_all_day: Optional[int] = None
    reminder_setting: Optional[str] = None
    color: Optional[str] = None
    source_deadline: Optional[str] = None


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
        "is_all_day": s.is_all_day if s.is_all_day else 0,
        "reminder_setting": s.reminder_setting or "3d",
        "color": s.color or "",
        "source_deadline": s.source_deadline or "",
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

@router.get("")
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
        {"value": "meeting", "label": "会见"},
        {"value": "consultation", "label": "咨询"},
        {"value": "deadline", "label": "截止日期"},
        {"value": "evidence_deadline", "label": "举证截止"},
        {"value": "appeal_deadline", "label": "上诉截止"},
        {"value": "enforcement_deadline", "label": "申请执行截止"},
        {"value": "preservation_expiry", "label": "保全到期"},
        {"value": "other", "label": "其他"},
    ]


@router.get("/auto-deadlines")
def get_auto_deadlines(
    case_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """根据案件日期自动计算待生成的期限条目（不自动写入，返回建议列表）

    规则：
    - 立案日期 filing_date → 举证期限（立案+30天，提前7天预警）
    - 判决日期 judgment_date → 上诉截止（判决+15天，提前5天预警）
    - 开庭日期 trial_date → 开庭提醒（提前3天）
    """
    from datetime import date

    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="案件不存在")

    suggestions = []

    # 1. 举证期限：立案日期 + 30 天
    if case.filing_date:
        evidence_due = case.filing_date + timedelta(days=30)
        # 检查是否已存在同类期限
        existing = db.query(Schedule).filter(
            Schedule.case_id == case_id,
            Schedule.source_deadline == "举证期限",
        ).first()
        if not existing and evidence_due.date() >= date.today():
            suggestions.append({
                "title": f"举证期限截止 - {case.case_number}",
                "schedule_type": "evidence_deadline",
                "start_time": evidence_due.isoformat(),
                "end_time": evidence_due.isoformat(),
                "reminder_setting": "7d",
                "source_deadline": "举证期限",
                "notes": f"立案日期 {case.filing_date.strftime('%Y-%m-%d')} + 30天，举证期限届满",
                "is_all_day": 1,
            })

    # 2. 上诉截止：判决日期 + 15 天
    if case.judgment_date:
        appeal_due = case.judgment_date + timedelta(days=15)
        existing = db.query(Schedule).filter(
            Schedule.case_id == case_id,
            Schedule.source_deadline == "上诉截止",
        ).first()
        if not existing and appeal_due.date() >= date.today():
            suggestions.append({
                "title": f"上诉截止 - {case.case_number}",
                "schedule_type": "appeal_deadline",
                "start_time": appeal_due.isoformat(),
                "end_time": appeal_due.isoformat(),
                "reminder_setting": "5d",
                "source_deadline": "上诉截止",
                "notes": f"判决日期 {case.judgment_date.strftime('%Y-%m-%d')} + 15天，上诉期限届满",
                "is_all_day": 1,
            })

    # 3. 开庭提醒（设置开庭前3天提醒的日程）
    if case.trial_date:
        existing = db.query(Schedule).filter(
            Schedule.case_id == case_id,
            Schedule.source_deadline == "开庭提醒",
        ).first()
        if not existing and case.trial_date.date() >= date.today():
            suggestions.append({
                "title": f"开庭提醒 - {case.case_number}",
                "schedule_type": "hearing",
                "start_time": case.trial_date.isoformat(),
                "end_time": (case.trial_date + timedelta(hours=3)).isoformat(),
                "reminder_setting": "3d",
                "source_deadline": "开庭提醒",
                "notes": f"开庭日期 {case.trial_date.strftime('%Y-%m-%d')}，提前3天提醒",
                "is_all_day": 0,
            })

    return {"case_id": case_id, "suggestions": suggestions}


@router.post("/batch")
def batch_create_schedules(
    data: List[ScheduleCreate],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """批量创建日程"""
    created = []
    for item in data:
        start_dt = _parse_dt(item.start_time)
        end_dt = _parse_dt(item.end_time)
        if start_dt >= end_dt:
            end_dt = start_dt + timedelta(hours=1)  # 全天事件默认1小时

        schedule = Schedule(
            title=item.title,
            schedule_type=item.schedule_type,
            case_id=item.case_id if item.case_id and item.case_id > 0 else None,
            start_time=start_dt,
            end_time=end_dt,
            location=item.location,
            judge=item.judge,
            notes=item.notes,
            is_parsed_from_sms=item.is_parsed_from_sms,
            is_all_day=item.is_all_day,
            reminder_setting=item.reminder_setting,
            color=item.color,
            source_deadline=item.source_deadline,
        )
        db.add(schedule)
        db.flush()
        created.append(_schedule_to_dict(schedule))

    db.commit()
    return {"message": f"成功创建 {len(created)} 条日程", "items": created}


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

    使用日程自身的 reminder_setting 字段判断：
    - none: 不提醒
    - day0: 当天提醒
    - 1d: 提前1天
    - 3d: 提前3天
    - 7d: 提前7天
    临近提醒（2小时/1小时）自动附加
    """
    now = datetime.now()
    # 查询从现在到未来 8 天内的所有日程
    future = now + timedelta(days=8)
    schedules = db.query(Schedule).filter(
        Schedule.start_time >= now,
        Schedule.start_time <= future,
    ).order_by(Schedule.start_time.asc()).all()

    REMINDER_THRESHOLDS = {
        "day0": 0,
        "1d": 24,
        "3d": 72,
        "7d": 168,
    }

    reminders = []
    for s in schedules:
        setting = s.reminder_setting or "3d"
        if setting == "none":
            continue

        time_until = s.start_time - now
        hours_until = time_until.total_seconds() / 3600

        due_reminders = []

        # 主提醒：根据 reminder_setting
        if setting in REMINDER_THRESHOLDS:
            threshold = REMINDER_THRESHOLDS[setting]
            if threshold == 0:
                # 当天：24小时内且未过期
                if 0 < hours_until <= 24:
                    due_reminders.append({
                        "key": "day0",
                        "label": "今日日程",
                        "hours_remaining": round(hours_until, 1),
                    })
            elif 0 < hours_until <= threshold and hours_until > threshold * 0.75:
                label_map = {"1d": "1 天", "3d": "3 天", "7d": "7 天"}
                due_reminders.append({
                    "key": setting,
                    "label": f"距日程还有 {label_map.get(setting, setting)}",
                    "hours_remaining": round(hours_until, 1),
                })

        # 临近提醒：开庭前2小时，其他1小时
        if s.schedule_type in ("hearing", "evidence_deadline", "appeal_deadline"):
            if 0 < hours_until <= 2:
                due_reminders.append({
                    "key": "urgent_2h",
                    "label": "距日程还有 2 小时",
                    "hours_remaining": round(hours_until, 1),
                })
        else:
            if 0 < hours_until <= 1:
                due_reminders.append({
                    "key": "urgent_1h",
                    "label": "日程即将开始（1 小时内）",
                    "hours_remaining": round(hours_until, 1),
                })

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


@router.post("")
def create_schedule(
    data: ScheduleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建新日程，自动检测冲突"""
    start_dt = _parse_dt(data.start_time)
    end_dt = _parse_dt(data.end_time)

    # 全天事件允许 start == end；非全天事件必须 end > start
    if not data.is_all_day and start_dt >= end_dt:
        raise HTTPException(status_code=400, detail="结束时间必须晚于开始时间")
    if data.is_all_day and start_dt >= end_dt:
        end_dt = start_dt + timedelta(hours=1)  # 全天事件默认持续1小时

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
        is_all_day=data.is_all_day,
        reminder_setting=data.reminder_setting,
        color=data.color,
        source_deadline=data.source_deadline,
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
    is_all_day = update_data.get("is_all_day", s.is_all_day if s.is_all_day else 0)

    if isinstance(check_start, str):
        check_start = _parse_dt(check_start)
    if isinstance(check_end, str):
        check_end = _parse_dt(check_end)

    # 全天事件允许 start == end
    if not is_all_day and check_start >= check_end:
        raise HTTPException(status_code=400, detail="结束时间必须晚于开始时间")
    if is_all_day and check_start >= check_end:
        check_end = check_start + timedelta(hours=1)
        update_data["end_time"] = check_end

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
