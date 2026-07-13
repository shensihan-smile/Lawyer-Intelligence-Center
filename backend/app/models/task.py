"""任务模型"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.core.database import Base


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, default="")
    priority = Column(String(10), default="medium")  # high/medium/low
    status = Column(String(20), default="pending")    # pending/in_progress/completed
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True)
    due_date = Column(DateTime, nullable=True)
    source_message = Column(Text, default="")
    created_at = Column(DateTime, server_default=func.now())
    completed_at = Column(DateTime, nullable=True)
