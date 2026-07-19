"""轻量数据模型：消息记录 / 工时记录 / 账单 / 计费配置
不依赖现有复杂模型，与前端 localStorage 数据结构完全对应。
"""
from sqlalchemy import Column, Integer, String, Float, Text, DateTime
from sqlalchemy.sql import func
from app.core.database import Base


class StoredMessage(Base):
    """消息记录"""
    __tablename__ = "stored_messages"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    source = Column(String(50), default="微信")
    content = Column(Text, default="")
    result = Column(String(200), default="")          # 识别结果摘要
    created_at = Column(DateTime, server_default=func.now())


class StoredTask(Base):
    """待办任务（从消息识别生成）"""
    __tablename__ = "stored_tasks"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(String(200), nullable=False)
    priority = Column(String(10), default="中")       # 高/中/低
    related = Column(String(200), default="")         # 关联客户/案件描述
    deadline = Column(String(20), default="")         # 截止日期 YYYY-MM-DD
    status = Column(String(20), default="待处理")     # 待处理/已完成
    created_at = Column(DateTime, server_default=func.now())


class StoredTimeRecord(Base):
    """工时记录（计时器 + 手动补录）"""
    __tablename__ = "stored_time_records"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    case_name = Column(String(200), default="")
    category = Column(String(30), default="其他")    # 法律研究/文书起草/庭审出庭/客户咨询/其他
    minutes = Column(Integer, default=0)
    date = Column(String(20), default="")            # YYYY-MM-DD
    created_at = Column(DateTime, server_default=func.now())


class StoredBillingConfig(Base):
    """计费配置（键值对）"""
    __tablename__ = "stored_billing_config"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    config_key = Column(String(50), unique=True, nullable=False)
    config_value = Column(String(100), default="")


class StoredBill(Base):
    """账单"""
    __tablename__ = "stored_bills"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    period = Column(String(10), default="")           # YYYY-MM
    total_min = Column(Integer, default=0)
    total_amt = Column(Float, default=0)
    rate = Column(Float, default=500)
    created_at = Column(DateTime, server_default=func.now())
