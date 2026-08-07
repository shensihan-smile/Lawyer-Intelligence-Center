"""文档模板 API"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.template import Template
from app.models.case import Case
from app.models.user import User

router = APIRouter()

# ---------- 系统内置分类 ----------

SYSTEM_CATEGORIES = [
    "起诉状", "答辩状", "代理词", "上诉状",
    "律师函", "法律意见书", "财产保全申请书", "证据目录"
]

# ---------- Pydantic schemas ----------

class TemplateCreate(BaseModel):
    category: str
    name: str
    description: str = ""
    content: str = ""
    is_system: bool = False  # 仅供种子数据标记


class TemplateUpdate(BaseModel):
    category: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    content: Optional[str] = None


class CategoryRename(BaseModel):
    new_name: str


# ---------- Helpers ----------

def _template_to_dict(t: Template) -> dict:
    return {
        "id": t.id,
        "category": t.category,
        "name": t.name,
        "description": t.description,
        "content": t.content,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }


def opposite_party(case: Case) -> str:
    """判断对方当事人：如果关联客户是原告则返被告，否则返原告"""
    client_name = ""
    if case.clients and len(case.clients) > 0:
        client_name = case.clients[0].name
    if client_name and case.plaintiff and client_name in case.plaintiff:
        return case.defendant or ""
    return case.plaintiff or case.defendant or ""


def _get_all_categories(db: Session) -> List[dict]:
    """获取所有分类（系统内置 + 数据库中实际使用的自定义分类）"""
    # 查询模板表中所有不同的分类
    rows = db.query(Template.category).distinct().all()
    db_categories = {r[0] for r in rows if r[0]}

    result = []

    # 系统内置分类
    for cat in SYSTEM_CATEGORIES:
        count = db.query(Template).filter(Template.category == cat).count()
        result.append({"name": cat, "is_system": True, "count": count})

    # 自定义分类（数据库中存在但不在系统列表中的）
    for cat in sorted(db_categories):
        if cat not in SYSTEM_CATEGORIES and cat != "未分类":
            count = db.query(Template).filter(Template.category == cat).count()
            result.append({"name": cat, "is_system": False, "count": count})

    # 未分类（总是存在）
    uncat_count = db.query(Template).filter(Template.category == "未分类").count()
    result.append({"name": "未分类", "is_system": True, "count": uncat_count})

    return result


# ---------- Routes: 分类管理 ----------

@router.get("/categories")
def get_categories(db: Session = Depends(get_db)):
    """获取所有模板分类（系统内置 + 自定义），含每个分类的模板数量"""
    return _get_all_categories(db)


@router.post("/categories")
def create_category(
    data: CategoryRename,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建自定义分类（仅验证名称，实际在创建模板时正式创建）"""
    name = data.new_name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="分类名称不能为空")
    if name in SYSTEM_CATEGORIES:
        raise HTTPException(status_code=400, detail="分类名称与系统内置分类重复")
    # 检查是否已存在
    existing = db.query(Template).filter(Template.category == name).first()
    if existing:
        raise HTTPException(status_code=400, detail="该分类已存在")
    return {"ok": True, "name": name, "is_system": False, "count": 0}


@router.put("/categories/{old_name:path}")
def rename_category(
    old_name: str,
    data: CategoryRename,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """重命名分类（批量更新该分类下所有模板的归属），系统分类也可重命名"""
    new_name = data.new_name.strip()
    if not new_name:
        raise HTTPException(status_code=400, detail="分类名称不能为空")
    if old_name == new_name:
        return {"ok": True, "old_name": old_name, "new_name": new_name}

    # 检查新名称是否与已有分类重名（排除自身）
    all_cats = _get_all_categories(db)
    existing_names = {c["name"] for c in all_cats if c["name"] != old_name}
    if new_name in existing_names:
        raise HTTPException(status_code=400, detail="分类名称已存在，不能重复")

    # 批量更新模板
    count = db.query(Template).filter(Template.category == old_name).update(
        {Template.category: new_name}
    )
    db.commit()
    return {"ok": True, "old_name": old_name, "new_name": new_name, "affected": count}


@router.delete("/categories/{name:path}")
def delete_category(
    name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除自定义分类（该分类下的模板移至「未分类」）"""
    if name in SYSTEM_CATEGORIES or name == "未分类":
        raise HTTPException(status_code=400, detail="系统内置分类不可删除")

    # 将该分类下所有模板移至"未分类"
    count = db.query(Template).filter(Template.category == name).update(
        {Template.category: "未分类"}
    )
    db.commit()
    return {"ok": True, "message": f"分类「{name}」已删除，{count} 个模板移至「未分类」"}


# ---------- Routes: 模板管理 ----------

@router.get("")
def list_templates(
    category: str = Query(""),
    db: Session = Depends(get_db),
):
    """获取模板列表"""
    q = db.query(Template)
    if category and category != "全部":
        q = q.filter(Template.category == category)
    templates = q.order_by(Template.category, Template.created_at.desc()).all()
    return [_template_to_dict(t) for t in templates]


@router.get("/{template_id}")
def get_template(template_id: int, db: Session = Depends(get_db)):
    """获取模板详情"""
    t = db.query(Template).filter(Template.id == template_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="模板不存在")
    return _template_to_dict(t)


@router.post("")
def create_template(
    data: TemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建模板"""
    t = Template(
        category=data.category,
        name=data.name,
        description=data.description,
        content=data.content,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return _template_to_dict(t)


@router.put("/{template_id}")
def update_template(
    template_id: int,
    data: TemplateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新模板"""
    t = db.query(Template).filter(Template.id == template_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="模板不存在")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(t, key, value)

    t.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(t)
    return _template_to_dict(t)


@router.delete("/{template_id}")
def delete_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除模板"""
    t = db.query(Template).filter(Template.id == template_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="模板不存在")
    db.delete(t)
    db.commit()
    return {"ok": True, "message": "模板已删除"}


@router.post("/{template_id}/render")
def render_template(
    template_id: int,
    case_id: int = Query(...),
    db: Session = Depends(get_db),
):
    """渲染模板：用案件信息替换变量占位符"""
    t = db.query(Template).filter(Template.id == template_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="模板不存在")

    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="案件不存在")

    content = t.content

    # 获取委托人名称
    client_name = ""
    if case.clients and len(case.clients) > 0:
        client_name = case.clients[0].name

    # 获取今天日期
    today = datetime.now().strftime("%Y年%m月%d日")

    # 替换变量
    replacements = {
        "{委托人}": client_name,
        "{对方当事人}": opposite_party(case),
        "{受理法院}": case.court or "",
        "{案由}": case.case_reason or "",
        "{当前日期}": today,
    }

    for var, val in replacements.items():
        content = content.replace(var, val)

    return {
        "template_id": template_id,
        "case_id": case_id,
        "content": content,
        "variables": {
            "委托人": client_name,
            "对方当事人": opposite_party(case),
            "受理法院": case.court or "",
            "案由": case.case_reason or "",
            "当前日期": today,
        }
    }
