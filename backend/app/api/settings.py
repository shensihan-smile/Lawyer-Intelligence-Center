"""律所设置 API — 全局配置（律所信息、费率、常法开关、数据管理）"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.models.settings import FirmSettings
from app.models.billing import BillingConfig

router = APIRouter()


# ---------- Pydantic schemas ----------

class FirmSettingsUpdate(BaseModel):
    firm_name: Optional[str] = None
    firm_address: Optional[str] = None
    firm_phone: Optional[str] = None
    lawyer_name: Optional[str] = None
    lawyer_email: Optional[str] = None
    bank_account: Optional[str] = None
    retainer_in_billing: Optional[bool] = None
    default_rate: Optional[float] = None  # 写穿至 BillingConfig


class ClearDataRequest(BaseModel):
    confirm: bool = False


# ---------- Helpers ----------

def _get_or_create_settings(db: Session) -> FirmSettings:
    """获取设置行，不存在则创建（id=1）"""
    s = db.query(FirmSettings).filter(FirmSettings.id == 1).first()
    if not s:
        s = FirmSettings(id=1)
        db.add(s)
        db.commit()
        db.refresh(s)
    return s


def _get_default_rate(db: Session) -> float:
    """从 BillingConfig 读取默认费率"""
    config = db.query(BillingConfig).filter(BillingConfig.is_default == True).first()
    return config.unit_price if config else 0


def _settings_to_dict(s: FirmSettings, db: Session) -> dict:
    return {
        "id": s.id,
        "firm_name": s.firm_name or "",
        "firm_address": s.firm_address or "",
        "firm_phone": s.firm_phone or "",
        "lawyer_name": s.lawyer_name or "",
        "lawyer_email": s.lawyer_email or "",
        "bank_account": s.bank_account or "",
        "retainer_in_billing": s.retainer_in_billing,
        "default_rate": _get_default_rate(db),
        "version": "1.0.0",
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }


# ---------- Routes ----------

@router.get("")
def get_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取全局设置"""
    s = _get_or_create_settings(db)
    return _settings_to_dict(s, db)


@router.put("")
def update_settings(
    data: FirmSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新全局设置"""
    s = _get_or_create_settings(db)
    update_data = data.model_dump(exclude_unset=True)
    default_rate = update_data.pop("default_rate", None)

    for key, value in update_data.items():
        setattr(s, key, value)

    s.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(s)

    # 写穿默认费率到 BillingConfig
    if default_rate is not None:
        _sync_default_rate(db, default_rate)

    return {"ok": True, "settings": _settings_to_dict(s, db)}


def _sync_default_rate(db: Session, rate: float):
    """将默认费率同步到 BillingConfig（确保唯一默认）"""
    # 先清除所有默认标记
    db.query(BillingConfig).filter(BillingConfig.is_default == True).update(
        {"is_default": False}
    )
    # 查找或创建默认配置
    config = db.query(BillingConfig).filter(BillingConfig.name == "默认小时费率").first()
    if config:
        config.unit_price = rate
        config.is_default = True
    else:
        config = BillingConfig(
            name="默认小时费率",
            billing_method="hourly",
            unit_price=rate,
            is_default=True,
            notes="系统自动维护的默认费率",
        )
        db.add(config)
    db.commit()


@router.post("/clear-data")
def clear_all_data(
    data: ClearDataRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """清空所有业务数据（保留用户、计费配置、律所设置）

    需要 body: {"confirm": true}
    """
    if not data.confirm:
        raise HTTPException(status_code=400, detail="请确认操作：设置 confirm 为 true")

    from sqlalchemy import text as sql_text

    # FK 安全顺序删除（子表先删）
    tables = [
        "case_third_parties",
        "case_clients",
        "bill_items",
        "bill_item_time_records",
        "time_records",
        "bills",
        "communications",
        "retainer_work_records",
        "retainer_payment_records",
        "retainer_reports",
        "retainer_clients",
        "documents",
        "schedules",
        "tasks",
        "cases",
        "clients",
        "preservation_renewals",
        "preservations",
        "local_cases",
        "stored_messages",
        "stored_tasks",
        "stored_time_records",
        "stored_bills",
        "stored_billing_config",
        "templates",
        "docket_records",
        "billing_config",
    ]

    results = {}
    for table in tables:
        try:
            count = db.execute(sql_text(f"SELECT COUNT(*) FROM {table}")).scalar()
            if count > 0:
                db.execute(sql_text(f"DELETE FROM {table}"))
                results[table] = count
        except Exception:
            pass  # 表不存在则跳过

    db.commit()

    # 重新初始化种子数据
    try:
        from app.core.seed import seed_templates as _seed
        _seed()
        results["_seeded"] = "templates"
    except Exception:
        pass

    return {"ok": True, "cleared": results}
