"""律所/律师设置模型 — 单例行（id=1），存储全局配置"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func
from app.core.database import Base


class FirmSettings(Base):
    __tablename__ = "firm_settings"

    id = Column(Integer, primary_key=True, default=1)
    firm_name = Column(String(200), default="")
    firm_address = Column(String(300), default="")
    firm_phone = Column(String(50), default="")
    lawyer_name = Column(String(50), default="")
    lawyer_email = Column(String(100), default="")
    bank_account = Column(String(300), default="")  # 开户行 + 账号
    retainer_in_billing = Column(Boolean, default=False)  # 常法工时纳入计费
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
