"""本地判例库 API"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.local_case import LocalCase
from app.models.user import User

router = APIRouter()


class LocalCaseCreate(BaseModel):
    original_case_id: Optional[int] = None
    case_category: str
    province: str = ""
    city: str = ""
    district: str = ""
    court_name: str = ""
    judge: str = ""
    case_number: str = ""
    plaintiff: str = ""
    defendant: str = ""
    case_reason: str = ""
    judgment_result: str = ""
    key_points: str = ""
    judgment_date: Optional[str] = None
    is_public: bool = False


class LocalCaseUpdate(BaseModel):
    case_category: Optional[str] = None
    province: Optional[str] = None
    city: Optional[str] = None
    district: Optional[str] = None
    court_name: Optional[str] = None
    judge: Optional[str] = None
    case_number: Optional[str] = None
    plaintiff: Optional[str] = None
    defendant: Optional[str] = None
    case_reason: Optional[str] = None
    judgment_result: Optional[str] = None
    key_points: Optional[str] = None
    judgment_date: Optional[str] = None
    is_public: Optional[bool] = None


def _to_dict(lc: LocalCase) -> dict:
    return {
        "id": lc.id,
        "original_case_id": lc.original_case_id,
        "case_category": lc.case_category,
        "province": lc.province,
        "city": lc.city,
        "district": lc.district,
        "court_name": lc.court_name,
        "judge": lc.judge,
        "case_number": lc.case_number,
        "plaintiff": lc.plaintiff,
        "defendant": lc.defendant,
        "case_reason": lc.case_reason,
        "judgment_result": lc.judgment_result,
        "key_points": lc.key_points,
        "judgment_date": lc.judgment_date.isoformat() if lc.judgment_date else None,
        "is_public": lc.is_public,
        "archived_date": lc.archived_date.isoformat() if lc.archived_date else None,
        "created_at": lc.created_at.isoformat() if lc.created_at else None,
        "updated_at": lc.updated_at.isoformat() if lc.updated_at else None,
    }


@router.get("")
def list_local_cases(
    search: str = Query(""),
    case_category: str = Query(""),
    province: str = Query(""),
    city: str = Query(""),
    judge: str = Query(""),
    judgment_result: str = Query(""),
    skip: int = Query(0),
    limit: int = Query(50),
    db: Session = Depends(get_db),
):
    """获取本地判例库列表"""
    q = db.query(LocalCase).filter(LocalCase.deleted == False)

    if search:
        like = f"%{search}%"
        q = q.filter(
            LocalCase.case_number.ilike(like) |
            LocalCase.plaintiff.ilike(like) |
            LocalCase.defendant.ilike(like) |
            LocalCase.key_points.ilike(like)
        )
    if case_category:
        q = q.filter(LocalCase.case_category == case_category)
    if province:
        q = q.filter(LocalCase.province == province)
    if city:
        q = q.filter(LocalCase.city == city)
    if judge:
        q = q.filter(LocalCase.judge.ilike(f"%{judge}%"))
    if judgment_result:
        q = q.filter(LocalCase.judgment_result.ilike(f"%{judgment_result}%"))

    total = q.count()
    items = q.order_by(LocalCase.judgment_date.desc().nullslast()).offset(skip).limit(limit).all()
    return {"total": total, "items": [_to_dict(i) for i in items]}


@router.get("/similar")
def find_similar_cases(
    case_reason: str = Query(""),
    court: str = Query(""),
    judge: str = Query(""),
    limit: int = Query(3),
    db: Session = Depends(get_db),
):
    """查找相似案件（用于案件详情页"本地相似案件"区块）"""
    q = db.query(LocalCase).filter(LocalCase.deleted == False)

    # 按匹配度排序：同法院+同法官 > 同法院+同案由 > 同案由
    results = []
    seen_ids = set()

    # 第一优先：同法院 + 同法官
    if court and judge:
        r1 = q.filter(
            LocalCase.court_name == court,
            LocalCase.judge == judge
        ).order_by(LocalCase.judgment_date.desc().nullslast()).limit(limit).all()
        for item in r1:
            if item.id not in seen_ids:
                results.append(item)
                seen_ids.add(item.id)

    # 第二优先：同法院 + 同案由
    if len(results) < limit and court:
        remaining = limit - len(results)
        r2 = q.filter(
            LocalCase.court_name == court,
            ~LocalCase.id.in_(seen_ids) if seen_ids else True
        ).order_by(LocalCase.judgment_date.desc().nullslast()).limit(remaining).all()
        for item in r2:
            if item.id not in seen_ids:
                results.append(item)
                seen_ids.add(item.id)

    # 第三优先：同案由
    if len(results) < limit and case_reason:
        remaining = limit - len(results)
        r3 = q.filter(
            LocalCase.case_reason == case_reason,
            ~LocalCase.id.in_(seen_ids) if seen_ids else True
        ).order_by(LocalCase.judgment_date.desc().nullslast()).limit(remaining).all()
        for item in r3:
            if item.id not in seen_ids:
                results.append(item)
                seen_ids.add(item.id)

    # 为每个结果计算法官统计
    items = []
    for r in results[:limit]:
        d = _to_dict(r)
        # 统计该法官同类案件判决倾向
        if r.judge:
            stats_q = db.query(LocalCase).filter(
                LocalCase.deleted == False,
                LocalCase.judge == r.judge,
                LocalCase.case_category == r.case_category
            )
            total = stats_q.count()
            if total > 0:
                support = stats_q.filter(LocalCase.judgment_result.ilike("%支持%")).count()
                remand = stats_q.filter(LocalCase.judgment_result.ilike("%改判%")).count()
                mediate = stats_q.filter(LocalCase.judgment_result.ilike("%调解%")).count()
                d["judge_stats"] = {
                    "total": total,
                    "support_pct": round(support / total * 100),
                    "remand_pct": round(remand / total * 100),
                    "mediate_pct": round(mediate / total * 100),
                }
        items.append(d)

    return {"items": items}


@router.get("/categories")
def get_categories():
    """获取案由分类列表"""
    return [
        "婚姻家庭", "劳动争议", "合同纠纷", "侵权纠纷",
        "建设工程", "公司纠纷", "知识产权", "行政", "刑事", "其他"
    ]


@router.get("/stats/judge/{judge_name}")
def judge_stats(judge_name: str, db: Session = Depends(get_db)):
    """获取某法官的判决统计"""
    q = db.query(LocalCase).filter(
        LocalCase.deleted == False,
        LocalCase.judge == judge_name
    )
    total = q.count()
    if total == 0:
        return {"total": 0}

    support = q.filter(LocalCase.judgment_result.ilike("%支持%")).count()
    remand = q.filter(LocalCase.judgment_result.ilike("%改判%")).count()
    mediate = q.filter(LocalCase.judgment_result.ilike("%调解%")).count()
    return {
        "total": total,
        "support_pct": round(support / total * 100),
        "remand_pct": round(remand / total * 100),
        "mediate_pct": round(mediate / total * 100),
    }


@router.get("/{lc_id}")
def get_local_case(lc_id: int, db: Session = Depends(get_db)):
    """获取判例详情"""
    lc = db.query(LocalCase).filter(LocalCase.id == lc_id, LocalCase.deleted == False).first()
    if not lc:
        raise HTTPException(status_code=404, detail="判例不存在")
    return _to_dict(lc)


@router.post("")
def create_local_case(
    data: LocalCaseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """归档案件到本地判例库"""
    lc = LocalCase(
        original_case_id=data.original_case_id,
        case_category=data.case_category,
        province=data.province,
        city=data.city,
        district=data.district,
        court_name=data.court_name,
        judge=data.judge,
        case_number=data.case_number,
        plaintiff=data.plaintiff,
        defendant=data.defendant,
        case_reason=data.case_reason,
        judgment_result=data.judgment_result,
        key_points=data.key_points,
        judgment_date=datetime.fromisoformat(data.judgment_date) if data.judgment_date else None,
        is_public=data.is_public,
        archived_date=datetime.utcnow(),
    )
    db.add(lc)
    db.commit()
    db.refresh(lc)
    return _to_dict(lc)


@router.put("/{lc_id}")
def update_local_case(
    lc_id: int,
    data: LocalCaseUpdate,
    db: Session = Depends(get_db),
):
    """更新判例"""
    lc = db.query(LocalCase).filter(LocalCase.id == lc_id, LocalCase.deleted == False).first()
    if not lc:
        raise HTTPException(status_code=404, detail="判例不存在")

    update_data = data.model_dump(exclude_unset=True)
    if "judgment_date" in update_data:
        val = update_data.pop("judgment_date")
        lc.judgment_date = datetime.fromisoformat(val) if val else None

    for key, value in update_data.items():
        setattr(lc, key, value)

    lc.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(lc)
    return _to_dict(lc)


@router.delete("/{lc_id}")
def delete_local_case(lc_id: int, db: Session = Depends(get_db)):
    """软删除判例"""
    lc = db.query(LocalCase).filter(LocalCase.id == lc_id, LocalCase.deleted == False).first()
    if not lc:
        raise HTTPException(status_code=404, detail="判例不存在")
    lc.deleted = True
    db.commit()
    return {"ok": True, "message": "判例已删除"}
