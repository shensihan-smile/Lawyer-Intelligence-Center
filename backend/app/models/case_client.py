"""案件-客户关联表（多对多）"""
from sqlalchemy import Column, Integer, ForeignKey, Table
from app.core.database import Base

case_clients = Table(
    "case_clients",
    Base.metadata,
    Column("case_id", Integer, ForeignKey("cases.id", ondelete="CASCADE"), primary_key=True),
    Column("client_id", Integer, ForeignKey("clients.id", ondelete="CASCADE"), primary_key=True),
)
