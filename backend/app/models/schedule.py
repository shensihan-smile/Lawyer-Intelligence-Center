"""日程模型"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class Schedule(Base):
    __tablename__ = "schedules"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(String(200), nullable=False)
    schedule_type = Column(String(20), default="other")  # hearing/meeting/consultation/deadline/other
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=True)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    location = Column(String(200), default="")
    judge = Column(String(50), default="")
    notes = Column(String(500), default="")
    is_parsed_from_sms = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())

    # ORM 关系
    case = relationship("Case", back_populates="schedules", lazy="joined")
