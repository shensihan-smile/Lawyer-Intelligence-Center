"""沟通记录模型"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class CommunicationRecord(Base):
    __tablename__ = "communication_records"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    date = Column(DateTime, nullable=False)
    content = Column(Text, default="")
    created_at = Column(DateTime, server_default=func.now())

    # ORM 关系
    client = relationship("Client", back_populates="communications")
