"""用户模型"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func
from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    real_name = Column(String(50), nullable=False)
    role = Column(String(20), nullable=False, default="lawyer")  # admin/partner/lawyer/assistant/intern
    department = Column(String(50), default="")
    phone = Column(String(20), default="")
    email = Column(String(100), default="")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
