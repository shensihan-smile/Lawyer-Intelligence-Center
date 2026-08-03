"""卷宗管理 API — 上传文件 + 自动 OCR 识别"""
import os
import shutil
import uuid
import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from app.core.database import get_db
from app.core.config import settings
from app.models.docket import DocketRecord
from app.services.ocr_service import recognize_file

router = APIRouter()

# 卷宗文件存储子目录
DOCKET_UPLOAD_DIR = os.path.join(settings.UPLOAD_DIR, "dockets")
os.makedirs(DOCKET_UPLOAD_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.tif', '.gif', '.webp', '.pdf', '.docx'}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB


# ---------- Pydantic schemas ----------

class DocketLinkRequest(BaseModel):
    case_id: int


# ---------- 辅助函数 ----------

def _save_upload(file: UploadFile) -> tuple:
    """保存上传文件，返回 (存储路径, 文件名, 文件扩展名)"""
    ext = os.path.splitext(file.filename or "unknown")[1].lower()

    if ext not in ALLOWED_EXTENSIONS:
        allowed = ', '.join(ALLOWED_EXTENSIONS)
        raise HTTPException(status_code=400, detail=f"不支持的文件类型「{ext}」。支持: {allowed}")

    # 生成唯一文件名（保留原扩展名）
    unique_name = f"{uuid.uuid4().hex}{ext}"
    save_path = os.path.join(DOCKET_UPLOAD_DIR, unique_name)

    # 写入文件
    try:
        with open(save_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件保存失败: {str(e)}")

    return save_path, file.filename or "unknown", ext


# ---------- API 端点 ----------

@router.post("/upload")
async def upload_docket(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """上传卷宗文件并自动 OCR 识别

    支持拖拽上传图片（PNG/JPG等）或 PDF 文件。
    上传后自动触发 OCR 识别，识别结果存入数据库并返回。
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="未选择文件")

    # 检查文件大小
    file.file.seek(0, 2)  # 移动到文件末尾
    file_size = file.file.tell()
    file.file.seek(0)  # 重置到开头

    if file_size > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail=f"文件过大（{file_size / 1024 / 1024:.1f}MB），最大支持 50MB")

    # 保存文件
    save_path, original_name, ext = _save_upload(file)

    # 判断文件类型并执行 OCR
    file_type = "docx" if ext == ".docx" else ("pdf" if ext == ".pdf" else "image")
    ocr_result = recognize_file(save_path, file_type)

    # 生成标题
    title = os.path.splitext(original_name)[0][:200]

    # 存入数据库
    record = DocketRecord(
        title=title,
        file_name=original_name,
        file_type=file_type,
        file_path=save_path,
        file_size=file_size,
        recognized_text=ocr_result.get("text", ""),
        summary=ocr_result.get("summary", ""),
        ocr_method=ocr_result.get("method", ""),
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    return {
        "id": record.id,
        "title": record.title,
        "file_name": record.file_name,
        "file_type": record.file_type,
        "file_size": record.file_size,
        "recognized_text": record.recognized_text[:500] if record.recognized_text else "",  # 截断返回
        "summary": record.summary,
        "ocr_method": record.ocr_method,
        "case_id": record.case_id,
        "created_at": record.created_at.isoformat() if record.created_at else "",
        "success": ocr_result.get("success", False),
        "full_text_length": len(record.recognized_text or ""),
    }


@router.get("")
def list_dockets(
    search: str = Query("", description="搜索关键词"),
    case_id: Optional[int] = Query(None, description="按案件ID筛选"),
    skip: int = Query(0),
    limit: int = Query(50),
    db: Session = Depends(get_db),
):
    """获取卷宗列表"""
    query = db.query(DocketRecord)

    if search:
        like = f"%{search}%"
        query = query.filter(
            DocketRecord.title.ilike(like) |
            DocketRecord.file_name.ilike(like) |
            DocketRecord.summary.ilike(like)
        )

    if case_id is not None:
        query = query.filter(DocketRecord.case_id == case_id)

    total = query.count()
    records = query.order_by(DocketRecord.created_at.desc()).offset(skip).limit(limit).all()

    return {
        "total": total,
        "items": [
            {
                "id": r.id,
                "title": r.title,
                "file_name": r.file_name,
                "file_type": r.file_type,
                "file_size": r.file_size,
                "summary": r.summary,
                "ocr_method": r.ocr_method,
                "case_id": r.case_id,
                "created_at": r.created_at.isoformat() if r.created_at else "",
            }
            for r in records
        ]
    }


@router.get("/{docket_id}")
def get_docket(docket_id: int, db: Session = Depends(get_db)):
    """获取卷宗详情（含 OCR 识别全文）"""
    record = db.query(DocketRecord).filter(DocketRecord.id == docket_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="卷宗记录不存在")

    return {
        "id": record.id,
        "title": record.title,
        "file_name": record.file_name,
        "file_type": record.file_type,
        "file_size": record.file_size,
        "recognized_text": record.recognized_text,
        "summary": record.summary,
        "ocr_method": record.ocr_method,
        "case_id": record.case_id,
        "created_at": record.created_at.isoformat() if record.created_at else "",
    }


@router.delete("/{docket_id}")
def delete_docket(docket_id: int, db: Session = Depends(get_db)):
    """删除卷宗记录及对应文件"""
    record = db.query(DocketRecord).filter(DocketRecord.id == docket_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="卷宗记录不存在")

    # 删除服务器上的文件
    if record.file_path and os.path.exists(record.file_path):
        try:
            os.remove(record.file_path)
        except OSError:
            pass

    db.delete(record)
    db.commit()
    return {"ok": True, "message": "卷宗已删除"}


@router.put("/{docket_id}/link")
def link_docket_to_case(
    docket_id: int,
    data: DocketLinkRequest,
    db: Session = Depends(get_db),
):
    """将卷宗关联到案件"""
    record = db.query(DocketRecord).filter(DocketRecord.id == docket_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="卷宗记录不存在")

    # 验证案件存在
    from app.models.case import Case
    case = db.query(Case).filter(Case.id == data.case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="案件不存在")

    record.case_id = data.case_id
    db.commit()
    return {"ok": True, "message": f"已关联到案件「{case.case_number}」"}


@router.get("/stats/summary")
def docket_stats(db: Session = Depends(get_db)):
    """卷宗统计数据"""
    total = db.query(DocketRecord).count()
    images = db.query(DocketRecord).filter(DocketRecord.file_type == "image").count()
    pdfs = db.query(DocketRecord).filter(DocketRecord.file_type == "pdf").count()
    linked = db.query(DocketRecord).filter(DocketRecord.case_id.isnot(None)).count()

    return {
        "total": total,
        "images": images,
        "pdfs": pdfs,
        "linked": linked,
        "unlinked": total - linked,
    }
