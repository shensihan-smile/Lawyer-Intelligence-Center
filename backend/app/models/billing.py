"""账单/计费/工时模型"""
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class BillingConfig(Base):
    """全局计费配置（默认费率）"""
    __tablename__ = "billing_config"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), nullable=False)  # 配置名称，如"默认小时费率"
    billing_method = Column(String(20), default="hourly")  # hourly/fixed/percentage
    unit_price = Column(Float, default=0)  # 单价（小时费率 / 固定费用 / 比例%）
    is_default = Column(Boolean, default=False)  # 是否为默认配置
    notes = Column(String(200), default="")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class Bill(Base):
    """账单"""
    __tablename__ = "bills"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    bill_number = Column(String(50), nullable=False, unique=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    billing_period_start = Column(DateTime, nullable=False)
    billing_period_end = Column(DateTime, nullable=False)
    total_amount = Column(Float, default=0)
    status = Column(String(20), default="draft")  # draft/generated/exported/paid
    notes = Column(Text, default="")
    firm_name = Column(String(200), default="")
    firm_address = Column(String(200), default="")
    firm_phone = Column(String(50), default="")
    lawyer_name = Column(String(50), default="")
    bank_info = Column(String(200), default="")
    amount_paid = Column(Float, default=0)  # 已回款金额
    paid_date = Column(DateTime, nullable=True)  # 回款日期
    generated_at = Column(DateTime, server_default=func.now())
    exported_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # ORM 关系
    client = relationship("Client", back_populates="bills")
    items = relationship("BillItem", back_populates="bill", cascade="all, delete-orphan")


class BillItem(Base):
    """账单明细项"""
    __tablename__ = "bill_items"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    bill_id = Column(Integer, ForeignKey("bills.id"), nullable=False)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=True)
    description = Column(String(500), nullable=False)
    billing_method = Column(String(20), default="hourly")  # hourly/fixed/percentage
    unit_price = Column(Float, default=0)
    quantity = Column(Float, default=1)
    amount = Column(Float, default=0)
    item_type = Column(String(20), default="legal_fee")  # legal_fee/travel/court/other
    work_record_ids = Column(Text, default="")  # JSON数组，关联常法工作记录ID

    # ORM 关系
    bill = relationship("Bill", back_populates="items")
    case = relationship("Case")


class TimeRecord(Base):
    """工时记录"""
    __tablename__ = "time_records"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=True)
    bill_item_id = Column(Integer, ForeignKey("bill_items.id"), nullable=True)  # 关联到账单项
    work_category = Column(String(30), default="other")
    description = Column(Text, default="")
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    duration_minutes = Column(Integer, default=0)
    is_billed = Column(Boolean, default=False)  # 是否已计入账单
    created_at = Column(DateTime, server_default=func.now())

    # ORM 关系
    case = relationship("Case")
