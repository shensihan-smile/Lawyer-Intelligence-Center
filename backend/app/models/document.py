"""文档模型"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    filename = Column(String(255), nullable=False)
    original_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, default=0)  # 字节
    file_type = Column(String(50), default="")
    doc_category = Column(String(30), default="other")  # legal_opinion/contract_draft/complaint/etc.
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True)
    version = Column(Integer, default=1)
    author = Column(String(50), default="")
    notes = Column(String(500), default="")
    uploaded_at = Column(DateTime, server_default=func.now())

    # ORM 关系
    case = relationship("Case", back_populates="documents")
    client = relationship("Client", back_populates="documents")
