"""常法客户（常年法律顾问）模型"""
import json
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class RetainerClient(Base):
    """常法客户"""
    __tablename__ = "retainer_clients"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True, index=True, comment="关联客户ID")
    client_name = Column(String(100), nullable=False, index=True, comment="客户名称（冗余展示）")
    service_start_date = Column(DateTime, nullable=False, comment="服务开始日期")
    service_end_date = Column(DateTime, nullable=False, comment="服务截止日期")
    contract_amount = Column(Float, default=0, comment="合同金额（元）")
    payment_method = Column(String(20), default="", comment="付款方式：once/quarterly/half_yearly/annual")
    service_scope = Column(Text, default="[]", comment="服务范围（JSON数组）")
    has_onsite = Column(Boolean, default=False, comment="是否有驻场要求")
    contact_name = Column(String(50), default="", comment="主要对接人")
    contact_phone = Column(String(20), default="", comment="对接人联系方式")
    contract_file_path = Column(String(500), default="", comment="合同文件路径")
    contract_number = Column(String(100), default="", comment="合同编号")
    status = Column(String(20), default="active", comment="状态：active/expiring/expired")
    notes = Column(Text, default="")
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True, comment="创建者")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    deleted = Column(Boolean, default=False, comment="软删除/归档")

    # ORM 关系
    client = relationship("Client", back_populates="retainers")
    work_records = relationship("WorkRecord", back_populates="retainer", cascade="all, delete-orphan")
    payments = relationship("PaymentRecord", back_populates="retainer", cascade="all, delete-orphan")
    reports = relationship("RetainerReport", back_populates="retainer", cascade="all, delete-orphan")


class WorkRecord(Base):
    """常法工作记录"""
    __tablename__ = "retainer_work_records"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    retainer_id = Column(Integer, ForeignKey("retainer_clients.id"), nullable=False, index=True)
    date = Column(DateTime, nullable=False, comment="工作日期")
    work_type = Column(String(30), default="other", comment="工作类型")
    description = Column(Text, default="", comment="工作内容描述")
    hours = Column(Float, default=0, comment="服务时长（小时）")
    participants = Column(String(200), default="", comment="参与人员")
    reference_number = Column(String(100), default="", comment="关联事项编号")
    is_billed = Column(Integer, default=0, comment="是否已纳入计费")
    bill_item_id = Column(Integer, nullable=True, comment="关联账单明细项ID")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    retainer = relationship("RetainerClient", back_populates="work_records")


class PaymentRecord(Base):
    """常法付款记录"""
    __tablename__ = "retainer_payment_records"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    retainer_id = Column(Integer, ForeignKey("retainer_clients.id"), nullable=False, index=True)
    payment_date = Column(DateTime, nullable=False, comment="付款日期")
    amount = Column(Float, default=0, comment="付款金额")
    receipt_path = Column(String(500), default="", comment="凭证文件路径")
    notes = Column(Text, default="")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    retainer = relationship("RetainerClient", back_populates="payments")


class RetainerReport(Base):
    """常法顾问工作报告"""
    __tablename__ = "retainer_reports"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    retainer_id = Column(Integer, ForeignKey("retainer_clients.id"), nullable=False, index=True)
    period_start = Column(DateTime, nullable=True, comment="报告期间开始")
    period_end = Column(DateTime, nullable=True, comment="报告期间结束")
    content = Column(Text, default="{}", comment="报告内容（JSON）")
    status = Column(String(20), default="draft", comment="状态：draft/sent")
    generated_date = Column(DateTime, server_default=func.now(), comment="生成日期")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    retainer = relationship("RetainerClient", back_populates="reports")
