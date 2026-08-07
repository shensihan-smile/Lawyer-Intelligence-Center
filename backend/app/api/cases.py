"""案件管理 API"""
import os
import json
import uuid
import shutil
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from app.core.database import get_db
from app.core.auth import get_current_user
from app.core.config import settings
from app.models.case import Case
from app.models.client import Client
from app.models.user import User
from app.models.case_client import case_clients
from app.models.case_third_party import case_third_parties
from app.models.document import Document
from app.services.ocr_service import recognize_file
from app.services.case_parser import parse_legal_document

router = APIRouter()

# 案件解析文件暂存目录
PARSE_UPLOAD_DIR = os.path.join(settings.UPLOAD_DIR, "case_parse")
os.makedirs(PARSE_UPLOAD_DIR, exist_ok=True)

ALLOWED_CASE_FILE_EXTENSIONS = {'.pdf', '.docx', '.txt', '.png', '.jpg', '.jpeg'}
MAX_CASE_FILE_SIZE = 20 * 1024 * 1024  # 20MB


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


def _case_to_dict(case: Case, db: Session | None = None) -> dict:
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

    # 查询 case_clients 表获取角色信息
    client_roles = {}
    if db:
        try:
            rows = db.execute(
                case_clients.select().where(case_clients.c.case_id == case.id)
            ).fetchall()
            client_roles = {row.client_id: row.role or "" for row in rows}
        except Exception:
            pass

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
            {
                "id": c.id, "name": c.name, "contact_person": c.contact_person,
                "role": client_roles.get(c.id, ""),
            }
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


def _find_or_create_client(name: str, db: Session) -> int:
    """按名称精确查找客户，找不到则自动创建并返回 client_id"""
    if not name or not name.strip():
        return None
    name = name.strip()
    client = db.query(Client).filter(Client.name == name).first()
    if client:
        return client.id
    # 自动创建新客户
    client = Client(name=name, client_type="个人")
    db.add(client)
    db.flush()
    return client.id


def _sync_clients(case: Case, db: Session, client_ids: List[int] = None,
                  plaintiff: str = None, defendant: str = None):
    """同步案件-客户关联（带角色区分）

    将删除 case 所有旧关联，然后重新建立：
    - plaintiff 文本 → 查找/创建客户，关联为「原告」
    - defendant 文本 → 查找/创建客户，关联为「被告」
    - client_ids → 关联为「委托人」
    """
    db.execute(
        case_clients.delete().where(case_clients.c.case_id == case.id)
    )

    inserts = []

    # 原告
    if plaintiff and plaintiff.strip():
        cid = _find_or_create_client(plaintiff, db)
        if cid:
            inserts.append({"case_id": case.id, "client_id": cid, "role": "原告"})

    # 被告
    if defendant and defendant.strip():
        cid = _find_or_create_client(defendant, db)
        if cid:
            # 如果被告和原告是同一个人，跳过（同一客户在同一案件中不重复关联）
            existing_ids = {ins["client_id"] for ins in inserts}
            if cid not in existing_ids:
                inserts.append({"case_id": case.id, "client_id": cid, "role": "被告"})

    # 委托人（显式 client_ids）
    if client_ids:
        existing_ids = {
            row[0] for row in
            db.query(Client.id).filter(Client.id.in_(client_ids)).all()
        }
        already = {ins["client_id"] for ins in inserts}
        for cid in client_ids:
            if cid in existing_ids and cid not in already:
                inserts.append({"case_id": case.id, "client_id": cid, "role": "委托人"})

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

@router.get("")
def list_cases(
    search: str = Query("", description="搜索案号、案由、当事人名称"),
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
            Case.case_reason.contains(search) |
            Case.plaintiff.contains(search) |
            Case.defendant.contains(search)
        )
    if stage:
        q = q.filter(Case.case_stage == stage)
    if client_id:
        q = q.join(Case.clients).filter(Client.id == client_id)

    # 非管理员只看自己创建的
    q = _filter_by_role(q, current_user, Case)

    total = q.count()
    cases = q.order_by(Case.created_at.desc()).all()
    return {"total": total, "items": [_case_to_dict(c, db) for c in cases]}


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


# ==================== AI 文档解析（必须在 /{case_id} 之前，避免路由冲突） ====================

@router.post("/parse")
async def parse_case_documents(
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """上传法律文书并 AI 解析案件信息

    接收多个文件（PDF/DOCX/TXT/图片），提取文字后调用 AI 大模型解析关键字段。
    AI 不可用时回退到正则表达式提取。

    Args:
        files: 上传的文件列表（最多 10 个）

    Returns:
        结构化 JSON，包含解析出的字段（含置信度）、重复案件检测、已有客户匹配
    """
    if not files:
        raise HTTPException(status_code=400, detail="请至少上传一个文件")

    if len(files) > 10:
        raise HTTPException(status_code=400, detail="最多同时上传 10 个文件")

    saved_files = []       # (original_name, saved_path, file_size)
    all_text_parts = []    # 拼接所有文件的文字
    parse_errors = []      # 解析过程中的错误

    # ===== Step 1: 逐个校验 + 保存 + 提取文字 =====
    for file in files:
        if not file.filename:
            continue

        # 校验扩展名
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in ALLOWED_CASE_FILE_EXTENSIONS:
            parse_errors.append(f"不支持的文件类型「{file.filename}」({ext})")
            continue

        # 校验文件大小
        file.file.seek(0, 2)
        file_size = file.file.tell()
        file.file.seek(0)

        if file_size > MAX_CASE_FILE_SIZE:
            size_mb = file_size / 1024 / 1024
            parse_errors.append(f"文件过大「{file.filename}」({size_mb:.1f}MB，上限20MB)")
            continue

        # 保存文件
        unique_name = f"{uuid.uuid4().hex}{ext}"
        saved_path = os.path.join(PARSE_UPLOAD_DIR, unique_name)

        try:
            with open(saved_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
        except Exception as e:
            parse_errors.append(f"文件保存失败「{file.filename}」: {str(e)}")
            continue

        saved_files.append((file.filename, saved_path, file_size))

        # 提取文字
        file_type_map = {
            '.docx': 'docx', '.pdf': 'pdf',
            '.txt': 'txt',
            '.png': 'image', '.jpg': 'image', '.jpeg': 'image',
        }
        file_type = file_type_map.get(ext, 'image')

        if ext == '.txt':
            # TXT 直接读取
            try:
                with open(saved_path, 'r', encoding='utf-8') as f:
                    txt_content = f.read()
                all_text_parts.append(f"=== {file.filename} ===\n{txt_content}")
            except UnicodeDecodeError:
                try:
                    with open(saved_path, 'r', encoding='gbk') as f:
                        txt_content = f.read()
                    all_text_parts.append(f"=== {file.filename} ===\n{txt_content}")
                except Exception as e:
                    parse_errors.append(f"读取文件失败「{file.filename}」: {str(e)}")
            except Exception as e:
                parse_errors.append(f"读取文件失败「{file.filename}」: {str(e)}")
        else:
            # PDF/DOCX/图片 — 使用 OCR 服务
            try:
                ocr_result = recognize_file(saved_path, file_type)
                if ocr_result.get('success') and ocr_result.get('text'):
                    all_text_parts.append(
                        f"=== {file.filename} ===\n{ocr_result['text']}"
                    )
                elif ocr_result.get('text'):
                    all_text_parts.append(
                        f"=== {file.filename} ===\n{ocr_result['text']}"
                    )
                else:
                    parse_errors.append(f"未能提取文字「{file.filename}」: {ocr_result.get('method', '未知方法')}")
            except Exception as e:
                parse_errors.append(f"OCR识别失败「{file.filename}」: {str(e)}")

    # ===== Step 2: 检查是否有可用文字 =====
    if not saved_files:
        raise HTTPException(status_code=400, detail="没有可处理的文件。" + ("; ".join(parse_errors) if parse_errors else ""))

    full_text = "\n\n".join(all_text_parts)

    if not full_text.strip():
        return {
            "success": False,
            "method": "none",
            "document_type": "other",
            "source_files": [sf[0] for sf in saved_files],
            "saved_file_paths": [sf[1] for sf in saved_files],  # 供后续创建 Document
            "source_text_preview": "",
            "fields": {},
            "duplicate_case": None,
            "matched_clients": {"plaintiff": None, "defendant": None},
            "warnings": ["所有文件均未能提取到可读文字。" + ("; ".join(parse_errors) if parse_errors else "")],
        }

    # ===== Step 3: AI/正则 解析 =====
    parse_result = parse_legal_document(full_text)
    fields = parse_result.get('fields', {})
    warnings = parse_result.get('warnings', [])

    if parse_errors:
        warnings = parse_errors + warnings

    # ===== Step 4: 检查重复案号 =====
    duplicate_case = None
    case_number = fields.get('case_number', {}).get('value', '')
    if case_number:
        dup = db.query(Case).filter(Case.case_number == case_number).first()
        if dup:
            duplicate_case = {
                "id": dup.id,
                "case_number": dup.case_number,
                "case_reason": dup.case_reason or "",
            }

    # ===== Step 5: 匹配已有客户 =====
    matched_clients = {"plaintiff": None, "defendant": None}

    plaintiff_name = fields.get('plaintiff', {}).get('value', '')
    if plaintiff_name:
        client = db.query(Client).filter(Client.name == plaintiff_name.strip()).first()
        if client:
            matched_clients['plaintiff'] = {"id": client.id, "name": client.name}

    defendant_name = fields.get('defendant', {}).get('value', '')
    if defendant_name and defendant_name.strip():
        client = db.query(Client).filter(Client.name == defendant_name.strip()).first()
        if client:
            matched_clients['defendant'] = {"id": client.id, "name": client.name}

    # ===== Step 6: 返回 =====
    source_text_preview = full_text[:800].replace('\n', '\\n').replace('\r', '')

    return {
        "success": parse_result.get('success', False),
        "method": parse_result.get('method', 'none'),
        "document_type": parse_result.get('document_type', 'other'),
        "source_files": [sf[0] for sf in saved_files],
        "saved_file_paths": [sf[1] for sf in saved_files],
        "source_text_preview": source_text_preview,
        "fields": fields,
        "duplicate_case": duplicate_case,
        "matched_clients": matched_clients,
        "warnings": warnings,
    }


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
    return _case_to_dict(case, db)

@router.post("")
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

    # 关联客户：原告/被告自动查找或创建，client_ids 作为委托人
    _sync_clients(case, db, client_ids=data.client_ids,
                  plaintiff=data.plaintiff, defendant=data.defendant)
    _sync_third_parties(case, data.third_party_client_ids, db)

    db.commit()
    db.refresh(case)
    return _case_to_dict(case, db)


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

    # 同步关联 — 当原告/被告/委托人任一项变化时，全量重建
    if client_ids is not None or "plaintiff" in update_data or "defendant" in update_data:
        _sync_clients(case, db,
                      client_ids=client_ids if client_ids is not None else None,
                      plaintiff=case.plaintiff,
                      defendant=case.defendant)
    if third_party_client_ids is not None:
        _sync_third_parties(case, third_party_client_ids, db)

    db.commit()
    db.refresh(case)
    return _case_to_dict(case, db)


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
