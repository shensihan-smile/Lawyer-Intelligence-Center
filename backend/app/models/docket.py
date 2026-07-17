"""卷宗记录模型"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.core.database import Base


class DocketRecord(Base):
    __tablename__ = "docket_records"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(String(200), default="", comment="卷宗标题")
    file_name = Column(String(255), nullable=False, comment="原始文件名")
    file_type = Column(String(20), default="image", comment="文件类型: image / pdf")
    file_path = Column(String(500), nullable=False, comment="服务器存储路径")
    file_size = Column(Integer, default=0, comment="文件大小（字节）")
    recognized_text = Column(Text, default="", comment="OCR识别全文")
    summary = Column(String(500), default="", comment="文字摘要（前200字）")
    ocr_method = Column(String(100), default="", comment="识别方法")
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=True, comment="关联案件ID")
    created_at = Column(DateTime, server_default=func.now(), comment="上传时间")
