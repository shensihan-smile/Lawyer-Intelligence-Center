"""本地判例库模型"""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime
from datetime import datetime
from app.core.database import Base


class LocalCase(Base):
    """本地判例库"""
    __tablename__ = "local_cases"

    id = Column(Integer, primary_key=True, index=True)
    original_case_id = Column(Integer, nullable=True, comment="关联原始案件ID")
    case_category = Column(String(50), nullable=False, comment="案由分类：婚姻家庭/劳动争议/合同纠纷等")
    province = Column(String(50), default="", comment="省")
    city = Column(String(50), default="", comment="市")
    district = Column(String(50), default="", comment="区")
    court_name = Column(String(200), default="", comment="法院名称")
    judge = Column(String(100), default="", comment="承办法官")
    case_number = Column(String(100), default="", comment="案号")
    plaintiff = Column(String(200), default="", comment="原告")
    defendant = Column(String(200), default="", comment="被告")
    case_reason = Column(String(200), default="", comment="案由")
    judgment_result = Column(String(500), default="", comment="判决结果")
    key_points = Column(Text, default="", comment="处理要点（律师备注）")
    judgment_date = Column(DateTime, nullable=True, comment="判决日期")
    is_public = Column(Boolean, default=False, comment="是否公开")
    archived_date = Column(DateTime, default=datetime.utcnow, comment="归档日期")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted = Column(Boolean, default=False, comment="软删除标记")
