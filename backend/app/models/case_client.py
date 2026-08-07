"""案件-客户关联表（多对多，带角色区分）"""
from sqlalchemy import Column, Integer, String, ForeignKey, Table
from app.core.database import Base

case_clients = Table(
    "case_clients",
    Base.metadata,
    Column("case_id", Integer, ForeignKey("cases.id", ondelete="CASCADE"), primary_key=True),
    Column("client_id", Integer, ForeignKey("clients.id", ondelete="CASCADE"), primary_key=True),
    Column("role", String(20), default="", comment="角色：原告/被告/委托人/第三人"),
)
