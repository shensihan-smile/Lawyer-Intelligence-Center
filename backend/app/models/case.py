"""案件模型"""
from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
from app.models.case_client import case_clients
from app.models.case_third_party import case_third_parties


class Case(Base):
    __tablename__ = "cases"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    case_number = Column(String(100), nullable=False, unique=True, index=True)
    case_reason = Column(String(200), default="")
    court = Column(String(200), default="")
    judge = Column(String(50), default="")
    clerk = Column(String(50), default="")
    plaintiff = Column(Text, default="")
    defendant = Column(Text, default="")
    third_party = Column(Text, default="")  # 手动输入的第三人（纯文本）
    amount_in_dispute = Column(Float, default=0)
    case_stage = Column(String(20), default="intake")  # intake/filing/trial/judgment/enforcement/closed
    acceptance_date = Column(DateTime, nullable=True)
    filing_date = Column(DateTime, nullable=True)
    trial_date = Column(DateTime, nullable=True)
    judgment_date = Column(DateTime, nullable=True)
    closing_date = Column(DateTime, nullable=True)
    notes = Column(Text, default="")
    # 案件级计费覆盖（为空则使用全局默认）
    billing_method = Column(String(20), nullable=True)  # hourly/fixed/percentage，null=用全局
    billing_rate = Column(Float, nullable=True)  # 费率，null=用全局
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)  # 创建者
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # ORM 关系
    clients = relationship("Client", secondary=case_clients, back_populates="cases", lazy="joined")
    third_party_clients = relationship(
        "Client", secondary=case_third_parties,
        back_populates="third_party_cases", lazy="joined",
    )
    documents = relationship("Document", back_populates="case")
    schedules = relationship("Schedule", back_populates="case")
