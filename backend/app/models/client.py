"""客户模型"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
from app.models.case_client import case_clients
from app.models.case_third_party import case_third_parties


class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), nullable=False, index=True)
    contact_person = Column(String(50), default="")
    phone = Column(String(20), default="")
    wechat = Column(String(50), default="")
    email = Column(String(100), default="")
    address = Column(String(200), default="")
    cooperation_history = Column(Text, default="")
    legal_contacts = Column(Text, default="")
    notes = Column(Text, default="")
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)  # 创建者
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # ORM 关系
    cases = relationship("Case", secondary=case_clients, back_populates="clients")
    third_party_cases = relationship("Case", secondary=case_third_parties, back_populates="third_party_clients")
    documents = relationship("Document", back_populates="client")
    bills = relationship("Bill", back_populates="client")
