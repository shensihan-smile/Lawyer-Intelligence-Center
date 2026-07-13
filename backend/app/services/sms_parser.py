"""12368 法院短信解析服务（正则 + AI 混合模式）"""
import re
import json
from datetime import datetime
from typing import Optional
from app.services import ai_client

# ==================== 正则匹配模式 ====================

# 常见的 12368 短信格式模式
# case_number 匹配逻辑: 4位年份 + 可选闭括号 + 非空白字符块 + 号
PATTERNS = [
    # 模式1：最标准格式（含"定于"），案号以括号开头
    re.compile(
        r"(?:关于|案号)?[\(（]\s*"
        r"(?P<case_number>\d{4}[\)）]?\s*\S{3,30}号)"
        r".*?定于\s*(?P<year>\d{4})年(?P<month>\d{1,2})月(?P<day>\d{1,2})日"
        r"\s*(?P<hour>\d{1,2})[时:：](?P<minute>\d{1,2})分?"
        r"(?:.*?(?P<location>(?:本院|法庭|法院|审判庭|第\d+法庭|第\d+审判庭)[^\s，。,.]*))?"
        r"(?:.*?(?:承办法官|审判长|法官)[：:：]?\s*(?P<judge>[^\s，。,，。\d]{2,4}))?"
        r"(?:.*?(?:联系电话|电话|联系方式)[：:：]?\s*(?P<phone>\d{7,15}))?"
    ),
    # 模式2：含法院名称 + 案号
    re.compile(
        r"(?P<court>[^\s，。,，通知]{2,10}(?:人民法院|法院|中院|高院))"
        r".*?[\(（]\s*"
        r"(?P<case_number>\d{4}[\)）]?\s*\S{3,30}号)"
        r".*?(?P<year>\d{4})年(?P<month>\d{1,2})月(?P<day>\d{1,2})日"
        r".*?(?:上午|下午|晚上)?\s*(?P<hour>\d{1,2})[时:：](?P<minute>\d{1,2})分?"
        r"(?:.*?(?P<location>(?:本院|法庭|法院|第\d+法庭|第\d+审判庭)[^\s，。,.]*))?"
        r"(?:.*?(?:法官|审判长)[：:：]?\s*(?P<judge>[^\s，。,，。\d]{2,4}))?"
        r"(?:.*?(?:电话|联系电话)[：:：]?\s*(?P<phone>\d{7,15}))?"
    ),
    # 模式3：最宽松匹配
    re.compile(
        r"[\(（]?\s*(?P<case_number>\d{4}[\)）]?\s*\S{3,30}号)?"
        r".*?(?P<year>\d{4})[年/\-\.](?P<month>\d{1,2})[月/\-\.](?P<day>\d{1,2})[日\s]*"
        r".*?(?:上午|下午|晚上)?\s*(?P<hour>\d{1,2})[时:：](?P<minute>\d{1,2})分?"
        r"(?:.*?(?P<location>(?:本院|法庭|法院|审判庭|第\d+法庭|第\d+审判庭)[^\s，。,.]{0,20}))?"
        r"(?:.*?(?:法官|审判长)[：:：]?\s*(?P<judge>[^\s，。,，。\d]{2,4}))?"
    ),
]

# 法院名称提取
COURT_PATTERN = re.compile(
    r"(?P<court>[^\s，。,，通知：:：]{2,10}(?:人民法院|法院|中院|高院|知识产权法院|互联网法院|海事法院))"
)

# 日期时间补全
TIME_PATTERN = re.compile(
    r"(?P<year>\d{4})[年/\-\.](?P<month>\d{1,2})[月/\-\.](?P<day>\d{1,2})[日]?"
    r".*?(?:上午|下午|晚上)?\s*(?P<hour>\d{1,2})[时:：](?P<minute>\d{1,2})分?"
)


def _try_regex(text: str) -> dict:
    """用正则表达式尝试提取信息"""
    best = {}
    best_score = 0

    for pattern in PATTERNS:
        m = pattern.search(text)
        if not m:
            continue

        info = m.groupdict()
        # 计算匹配得分（提取到几个关键字段）
        score = sum(1 for k in ["case_number", "year", "month", "day", "hour", "minute"]
                    if info.get(k))

        if score > best_score:
            best_score = score
            best = info

    if best_score < 2:
        return {}

    result = {}

    # 案号
    case_number = (best.get("case_number") or "").strip()
    # 清理案号中的杂音
    case_number = re.sub(r"^[,，。.\s]+|[,，。.\s]+$", "", case_number)
    result["case_number"] = case_number

    # 开庭时间
    try:
        y = int(best.get("year") or 0)
        mo = int(best.get("month") or 0)
        d = int(best.get("day") or 0)
        h = int(best.get("hour") or 0)
        mi = int(best.get("minute") or 0)
        if y >= 2020 and 1 <= mo <= 12 and 1 <= d <= 31:
            dt = datetime(y, mo, d, h, mi, 0)
            result["hearing_datetime"] = dt.isoformat()
        else:
            result["hearing_datetime"] = ""
    except (ValueError, TypeError):
        result["hearing_datetime"] = ""

    # 法庭地点
    location = (best.get("location") or "").strip()
    court = (best.get("court") or "").strip()
    if not court:
        cm = COURT_PATTERN.search(text)
        if cm:
            court = cm.group("court")
    result["court"] = court
    result["location"] = f"{court}{location}" if court and location else (court or location)

    # 法官
    result["judge"] = (best.get("judge") or "").strip()

    # 电话
    result["phone"] = (best.get("phone") or "").strip()

    return result


def _try_ai(text: str) -> dict:
    """用 AI 提取信息（兜底方案）"""
    if not ai_client.is_available():
        return {}

    system_prompt = """你是一个专业的法律信息提取助手。请从 12368 法院服务平台发送的短信中提取以下信息。

返回格式（严格的 JSON）：
{
  "case_number": "案号，如 (2024)京0105民初12345号",
  "hearing_datetime": "开庭时间，ISO8601格式 YYYY-MM-DDTHH:MM:SS",
  "location": "法庭地点，包含法院名称和具体法庭",
  "judge": "承办法官姓名",
  "phone": "法院联系电话",
  "confidence": "high/medium/low"
}

规则：
- 如果某项信息无法从短信中提取，设为空字符串 ""
- 案号格式常见为 (年份)地区代码+案件类型+序号 号
- 日期可能用中文"年月日"或数字格式
- 不要编造信息，只提取短信中明确提到的内容"""

    response = ai_client.chat(text, system_message=system_prompt)

    try:
        # 尝试从回复中提取 JSON
        # AI 可能在 JSON 前后加了 markdown 标记
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            data = json.loads(json_match.group())
            # 转换字段名
            result = {}
            if data.get("case_number"):
                result["case_number"] = data["case_number"]
            if data.get("hearing_datetime"):
                result["hearing_datetime"] = data["hearing_datetime"]
            if data.get("location"):
                result["location"] = data["location"]
            if data.get("judge"):
                result["judge"] = data["judge"]
            if data.get("phone"):
                result["phone"] = data["phone"]
            return result
    except (json.JSONDecodeError, KeyError):
        pass

    return {}


def parse_sms(text: str) -> dict:
    """解析 12368 短信，提取庭审信息（混合模式）

    优先使用正则匹配（快速、免费），匹配不完整时调用 AI 兜底。

    Args:
        text: 短信原文

    Returns:
        {
            "case_number": str,        # 案号
            "hearing_datetime": str,   # 开庭时间 ISO 格式
            "location": str,           # 法庭地点
            "judge": str,              # 承办法官
            "phone": str,              # 联系电话
            "matched_case_id": int|null,  # 自动匹配到的已有案件 ID
            "method": str,             # "regex" / "ai" / "regex+ai"
        }
    """
    if not text or not text.strip():
        return {
            "case_number": "",
            "hearing_datetime": "",
            "location": "",
            "judge": "",
            "phone": "",
            "matched_case_id": None,
            "method": "none",
        }

    text = text.strip()

    # 第一步：正则匹配
    regex_result = _try_regex(text)

    # 判断正则结果是否完整
    key_fields = ["case_number", "hearing_datetime"]
    regex_complete = all(regex_result.get(f) for f in key_fields)

    if regex_complete:
        result = {**regex_result}
        result["method"] = "regex"
    else:
        # 第二步：AI 兜底
        ai_result = _try_ai(text)
        if ai_result:
            # 合并：正则能提取的用正则，正则漏掉的用 AI 补充
            result = {}
            for field in ["case_number", "hearing_datetime", "location", "judge", "phone"]:
                result[field] = regex_result.get(field) or ai_result.get(field) or ""
            result["method"] = "regex+ai"
        else:
            # AI 不可用，返回正则的部分结果
            result = {
                "case_number": regex_result.get("case_number", ""),
                "hearing_datetime": regex_result.get("hearing_datetime", ""),
                "location": regex_result.get("location", ""),
                "judge": regex_result.get("judge", ""),
                "phone": regex_result.get("phone", ""),
                "method": "regex",
            }

    # 自动匹配已有案件
    matched_case_id = None
    case_number = result.get("case_number", "")
    if case_number:
        try:
            from app.core.database import SessionLocal
            from app.models.case import Case
            db = SessionLocal()
            matched = db.query(Case).filter(Case.case_number.contains(case_number[:8])).first()
            if matched:
                matched_case_id = matched.id
                result["matched_case_name"] = matched.case_reason or matched.case_number
            db.close()
        except Exception:
            pass

    result["matched_case_id"] = matched_case_id
    return result
