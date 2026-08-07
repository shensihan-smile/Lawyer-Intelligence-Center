"""保全记录 + 续期记录模型"""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from datetime import datetime
from app.core.database import Base


class PreservationRecord(Base):
    """保全记录"""
    __tablename__ = "preservation_records"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, nullable=False, comment="关联案件ID")
    preservation_type = Column(String(50), nullable=False, comment="保全类型：财产保全/证据保全/行为保全/诉前保全/诉讼保全/执行保全/其他")
    target = Column(String(500), nullable=False, comment="被保全标的")
    ruling_number = Column(String(200), default="", comment="保全裁定书案号")
    measure_type = Column(String(50), default="", comment="保全措施类型：冻结银行账户/查封不动产/查封动产/冻结股权/冻结债权/扣押/其他")
    court = Column(String(200), default="", comment="保全法院")
    start_date = Column(DateTime, nullable=False, comment="保全起始日期")
    end_date = Column(DateTime, nullable=False, comment="保全到期日期")
    renewal_count = Column(Integer, default=0, comment="续期次数")
    status = Column(String(20), default="active", comment="状态：active/已解封/已到期未续/已续期")
    notes = Column(Text, default="", comment="备注")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PreservationRenewal(Base):
    """保全续期记录"""
    __tablename__ = "preservation_renewals"

    id = Column(Integer, primary_key=True, index=True)
    preservation_id = Column(Integer, ForeignKey("preservation_records.id"), nullable=False, comment="关联保全记录ID")
    previous_end_date = Column(DateTime, nullable=False, comment="续期前到期日期")
    new_end_date = Column(DateTime, nullable=False, comment="续期后到期日期")
    ruling_number = Column(String(200), default="", comment="续期裁定书案号")
    renewal_date = Column(DateTime, default=datetime.utcnow, comment="续期日期")
    notes = Column(Text, default="", comment="备注")
    created_at = Column(DateTime, default=datetime.utcnow)
