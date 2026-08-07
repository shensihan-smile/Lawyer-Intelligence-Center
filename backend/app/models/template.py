"""文档模板模型"""
from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.sql import func
from app.core.database import Base


class Template(Base):
    __tablename__ = "templates"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    category = Column(String(30), default="other", index=True, comment="模板分类")
    name = Column(String(200), nullable=False, comment="模板名称")
    description = Column(String(500), default="", comment="模板说明")
    content = Column(Text, default="", comment="模板正文（HTML，含变量占位符）")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
