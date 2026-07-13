"""案件-第三人关联表（多对多，从客户库中选取）"""
from sqlalchemy import Column, Integer, ForeignKey, Table
from app.core.database import Base

case_third_parties = Table(
    "case_third_parties",
    Base.metadata,
    Column("case_id", Integer, ForeignKey("cases.id", ondelete="CASCADE"), primary_key=True),
    Column("client_id", Integer, ForeignKey("clients.id", ondelete="CASCADE"), primary_key=True),
)
