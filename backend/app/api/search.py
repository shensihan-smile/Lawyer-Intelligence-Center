"""全局搜索 API：跨表搜索案件/客户/常法/文档/模板/待办/工作记录/判例"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text as sql_text
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User

router = APIRouter()


@router.get("")
def global_search(
    q: str = Query("", min_length=1),
    limit: int = Query(20, ge=5, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """全局搜索：跨表模糊匹配，返回分组结果"""
    if not q or not q.strip():
        return {"groups": {}}

    pattern = f"%{q.strip()}%"
    groups = {
        "cases": [],
        "clients": [],
        "retainers": [],
        "documents": [],
        "templates": [],
        "tasks": [],
        "work_records": [],
        "local_cases": [],
    }

    # 1. 案件搜索
    try:
        rows = db.execute(sql_text(
            "SELECT id, case_number, case_reason, plaintiff, defendant, court "
            "FROM cases "
            "WHERE case_number LIKE :p OR case_reason LIKE :p OR plaintiff LIKE :p "
            "OR defendant LIKE :p OR court LIKE :p "
            "LIMIT :lim"
        ), {"p": pattern, "lim": limit}).fetchall()
        for r in rows:
            # Find best matching subtitle
            subtitle = ""
            if pattern.strip("%") in (r[2] or ""):
                subtitle = f"案由: {r[2]}"
            elif pattern.strip("%") in (r[5] or ""):
                subtitle = f"法院: {r[5]}"
            else:
                subtitle = f"案由: {r[2] or ''}" if r[2] else f"法院: {r[5] or ''}"
            groups["cases"].append({
                "id": r[0],
                "title": r[1] or "无案号",
                "subtitle": subtitle,
                "target": f"cases:{r[0]}",
            })
    except Exception:
        pass

    # 2. 客户搜索
    try:
        rows = db.execute(sql_text(
            "SELECT id, name, contact_person, phone, email "
            "FROM clients "
            "WHERE name LIKE :p OR contact_person LIKE :p OR phone LIKE :p OR email LIKE :p "
            "LIMIT :lim"
        ), {"p": pattern, "lim": limit}).fetchall()
        for r in rows:
            subtitle = ""
            if r[2]:
                subtitle = f"联系人: {r[2]}"
            if r[3]:
                subtitle += f"  {r[3]}"
            groups["clients"].append({
                "id": r[0],
                "title": r[1] or "未知客户",
                "subtitle": subtitle.strip(),
                "target": f"clients:{r[0]}",
            })
    except Exception:
        pass

    # 3. 常法客户搜索
    try:
        rows = db.execute(sql_text(
            "SELECT id, client_name, contract_number, contact_name "
            "FROM retainer_clients "
            "WHERE deleted=0 AND (client_name LIKE :p OR contract_number LIKE :p OR contact_name LIKE :p) "
            "LIMIT :lim"
        ), {"p": pattern, "lim": limit}).fetchall()
        for r in rows:
            subtitle = ""
            if r[2]:
                subtitle = f"合同号: {r[2]}"
            if r[3]:
                subtitle += f"  对接人: {r[3]}"
            groups["retainers"].append({
                "id": r[0],
                "title": r[1] or "未知",
                "subtitle": subtitle.strip(),
                "target": f"retainer:{r[0]}",
            })
    except Exception:
        pass

    # 4. 文档搜索
    try:
        rows = db.execute(sql_text(
            "SELECT id, filename, original_name, notes, case_id, client_id "
            "FROM documents "
            "WHERE filename LIKE :p OR original_name LIKE :p OR notes LIKE :p "
            "LIMIT :lim"
        ), {"p": pattern, "lim": limit}).fetchall()
        for r in rows:
            subtitle = r[2] or r[1]
            groups["documents"].append({
                "id": r[0],
                "title": r[1] or r[2],
                "subtitle": subtitle,
                "target": f"documents:{r[0]}",
                "case_id": r[4],
                "client_id": r[5],
            })
    except Exception:
        pass

    # 5. 模板搜索
    try:
        rows = db.execute(sql_text(
            "SELECT id, name, description FROM templates "
            "WHERE name LIKE :p OR description LIKE :p "
            "LIMIT :lim"
        ), {"p": pattern, "lim": limit}).fetchall()
        for r in rows:
            groups["templates"].append({
                "id": r[0],
                "title": r[1],
                "subtitle": r[2] or "",
                "target": f"templates:{r[0]}",
            })
    except Exception:
        pass

    # 6. 待办任务搜索
    try:
        rows = db.execute(sql_text(
            "SELECT id, title, related, deadline, status "
            "FROM stored_tasks "
            "WHERE title LIKE :p OR related LIKE :p "
            "LIMIT :lim"
        ), {"p": pattern, "lim": limit}).fetchall()
        for r in rows:
            subtitle = f"状态: {r[4] or '待处理'}"
            if r[2]:
                subtitle += f"  关联: {r[2]}"
            groups["tasks"].append({
                "id": r[0],
                "title": r[1],
                "subtitle": subtitle,
                "target": f"messages:task:{r[0]}",
            })
    except Exception:
        pass

    # 7. 常法工作记录搜索
    try:
        rows = db.execute(sql_text(
            "SELECT wr.id, wr.description, wr.retainer_id, rc.client_name "
            "FROM retainer_work_records wr "
            "LEFT JOIN retainer_clients rc ON wr.retainer_id = rc.id "
            "WHERE wr.description LIKE :p "
            "LIMIT :lim"
        ), {"p": pattern, "lim": limit}).fetchall()
        for r in rows:
            groups["work_records"].append({
                "id": r[0],
                "title": (r[1] or "无描述")[:60],
                "subtitle": f"常法: {r[3] or '未知'}",
                "target": f"retainer:{r[2]}",
            })
    except Exception:
        pass

    # 8. 本地判例搜索
    try:
        rows = db.execute(sql_text(
            "SELECT id, case_number, case_reason, court_name, plaintiff, defendant "
            "FROM local_cases "
            "WHERE deleted=0 AND (case_number LIKE :p OR case_reason LIKE :p "
            "OR court_name LIKE :p OR plaintiff LIKE :p OR defendant LIKE :p) "
            "LIMIT :lim"
        ), {"p": pattern, "lim": limit}).fetchall()
        for r in rows:
            subtitle = f"案由: {r[2] or ''}"
            if r[3]:
                subtitle += f"  法院: {r[3]}"
            groups["local_cases"].append({
                "id": r[0],
                "title": r[1] or "无案号",
                "subtitle": subtitle,
                "target": f"localCases:{r[0]}",
            })
    except Exception:
        pass

    # 移除空分组
    result = {k: v for k, v in groups.items() if v}
    return {"groups": result, "query": q.strip()}
