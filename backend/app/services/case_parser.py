"""法律文书 AI 解析服务

采用 AI 优先 + 正则回退策略：
1. 先调用 LLM 解析文书内容 → 返回结构化 JSON（含置信度）
2. AI 不可用时回退到正则表达式提取
"""
import re
import json
from datetime import datetime
from typing import Optional
from app.services import ai_client


# ==================== AI 提示词模板 ====================

SYSTEM_PROMPT_LEGAL = """你是一位资深法律文书分析专家。你的任务是从法律文书中提取关键案件信息。

核心规则：
1. 只提取文中明确出现的信息，绝对不要编造任何内容
2. 每个字段必须包含 value（提取到的值）和 confidence（置信度，0到1之间的小数）
3. 如果文中没有某字段的信息，value设为空字符串""，confidence设为0
4. 当事人名称必须提取完整全称（公司名包含"有限公司""股份有限公司"等后缀）
5. 金额统一转换为"万元"数字单位（原文为"元"时除以10000）
6. 日期格式统一为 YYYY-MM-DD
7. 案号保留原文中的括号格式，如"(2025)京0105民初12345号"
8. 案件阶段用中文：接案/立案/审理中/判决/执行/结案
9. 只输出JSON，不要输出任何解释、说明或思考过程

输出格式（严格按此JSON结构）：
{
  "document_type": "complaint",
  "fields": {
    "case_number":       {"value": "(2025)京0105民初12345号", "confidence": 0.95},
    "case_reason":       {"value": "买卖合同纠纷",            "confidence": 0.90},
    "court":             {"value": "北京市朝阳区人民法院",    "confidence": 0.95},
    "judge":             {"value": "李四",                    "confidence": 0.70},
    "clerk":             {"value": "",                        "confidence": 0},
    "plaintiff":         {"value": "张三",                    "confidence": 0.95},
    "defendant":         {"value": "北京XX科技有限公司",      "confidence": 0.90},
    "amount_in_dispute": {"value": 50.5,                      "confidence": 0.85},
    "trial_date":        {"value": "2026-06-15",              "confidence": 0.60},
    "case_stage":        {"value": "立案",                    "confidence": 0.80},
    "notes":             {"value": "诉讼请求：判令被告支付货款50.5万元及逾期利息", "confidence": 0.90}
  }
}

document_type 取值说明：
- "complaint" = 起诉状（含原告、被告、诉讼请求等）
- "judgment"  = 判决书（含案号、法院、判决结果等）
- "other"     = 其他法律文书

notes 字段应包含文书中提取到的补充信息摘要（诉讼请求、判决结果、事实摘要等），不超过200字。"""


# ==================== 正则回退模板 ====================

# 案号正则（支持多种格式）
RE_CASE_NUMBER = re.compile(
    r'[\(\uff08]\s*(\d{4})\s*[\uff09\)]\s*[\u4e00-\u9fff]{0,3}[\u4e00-\u9fff]{1,4}\S{0,4}\d+\s*\u53f7'
    r'|'
    r'(?:\u6848\u53f7|\u6848\u4ef6\u7f16\u53f7)[\uff1a:\s]*(\d{4}[\uff09\)]?\s*\S{3,30}\u53f7)'
)
RE_CASE_REASON = re.compile(r'案由[：:]\s*(.+?)(?:\n|。|，|$)')
RE_COURT = re.compile(r'(?:受理法院|本院|法院)[：:]\s*(.+?)(?:\n|。|，|$)')
RE_JUDGE = re.compile(r'(?:承办法官|审判长|法官|审判员)[：:]\s*(.+?)(?:，|。|\n|$)')
RE_CLERK = re.compile(r'(?:书记员)[：:]\s*(.+?)(?:，|。|\n|$)')
RE_PLAINTIFF = re.compile(r'(?:原告|申请执行人|申请人)[：:]\s*(.+?)(?:，|。|\n|$)')
RE_DEFENDANT = re.compile(r'(?:被告|被执行人|被申请人)[：:]\s*(.+?)(?:，|。|\n|$)')
RE_AMOUNT = re.compile(
    r'(?:标的额|诉讼标的|标的金额|争议金额|涉案金额)[：:]\s*'
    r'(\d+\.?\d*)\s*(?:万|元)'
    r'|'
    r'(?:人民币|¥|￥)\s*(\d+\.?\d*)\s*(?:万|元)'
)
RE_TRIAL_DATE = re.compile(
    r'(?:开庭日期|开庭时间|庭审时间)[：:]\s*(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?)'
)
RE_STAGE = re.compile(
    r'(?:案件阶段|审理阶段|诉讼阶段|当前阶段)[：:]\s*((?:接案|立案|审理中|判决|执行|结案))'
)
RE_NOTES = re.compile(
    r'(?:诉讼请求|请求事项|判决如下|判决结果|裁判结果)[：:]?\s*'
    r'(.+?)(?:\n\n|\n(?=[一-鿿]{3,}[：:])|$)',
    re.DOTALL
)


def _try_regex(text: str) -> dict:
    """正则表达式提取（AI 回退方案）"""
    fields = {}

    m = RE_CASE_NUMBER.search(text)
    if m:
        cn = m.group(1) or m.group(2) or m.group(0)
        fields['case_number'] = {'value': cn.strip(), 'confidence': 0.7}

    m = RE_CASE_REASON.search(text)
    if m:
        fields['case_reason'] = {'value': m.group(1).strip(), 'confidence': 0.6}

    m = RE_COURT.search(text)
    if m:
        fields['court'] = {'value': m.group(1).strip(), 'confidence': 0.6}

    m = RE_JUDGE.search(text)
    if m:
        fields['judge'] = {'value': m.group(1).strip(), 'confidence': 0.5}

    m = RE_CLERK.search(text)
    if m:
        fields['clerk'] = {'value': m.group(1).strip(), 'confidence': 0.5}

    m = RE_PLAINTIFF.search(text)
    if m:
        fields['plaintiff'] = {'value': m.group(1).strip(), 'confidence': 0.6}

    m = RE_DEFENDANT.search(text)
    if m:
        fields['defendant'] = {'value': m.group(1).strip(), 'confidence': 0.6}

    m = RE_AMOUNT.search(text)
    if m:
        raw = m.group(1) or m.group(2) or '0'
        try:
            amount = float(raw.replace(',', ''))
            # 如果原始金额是"元"（不含"万"），转换为万元
            matched_text = m.group(0)
            if '万' not in matched_text and amount > 1000:
                amount = amount / 10000
            fields['amount_in_dispute'] = {'value': round(amount, 2), 'confidence': 0.5}
        except ValueError:
            pass

    m = RE_TRIAL_DATE.search(text)
    if m:
        date_str = m.group(1).strip().replace('年', '-').replace('月', '-').replace('日', '')
        fields['trial_date'] = {'value': date_str, 'confidence': 0.4}

    m = RE_STAGE.search(text)
    if m:
        fields['case_stage'] = {'value': m.group(1).strip(), 'confidence': 0.5}

    m = RE_NOTES.search(text)
    if m:
        notes = m.group(1).strip()[:300]
        fields['notes'] = {'value': notes, 'confidence': 0.5}

    return fields


def _clean_fields(raw_fields: dict) -> dict:
    """清洗和标准化 AI/正则 返回的字段"""
    # 默认字段模板
    default_fields = {
        'case_number':       {'value': '', 'confidence': 0},
        'case_reason':       {'value': '', 'confidence': 0},
        'court':             {'value': '', 'confidence': 0},
        'judge':             {'value': '', 'confidence': 0},
        'clerk':             {'value': '', 'confidence': 0},
        'plaintiff':         {'value': '', 'confidence': 0},
        'defendant':         {'value': '', 'confidence': 0},
        'amount_in_dispute': {'value': 0, 'confidence': 0},
        'trial_date':        {'value': '', 'confidence': 0},
        'case_stage':        {'value': '接案', 'confidence': 0},
        'notes':             {'value': '', 'confidence': 0},
    }

    for key in default_fields:
        if key in raw_fields:
            f = raw_fields[key]
            if isinstance(f, dict):
                val = f.get('value', '')
                conf = f.get('confidence', 0)
                # 确保 confidence 是数字
                try:
                    conf = float(conf)
                except (ValueError, TypeError):
                    conf = 0

                if key == 'amount_in_dispute':
                    try:
                        val = float(val) if val else 0
                    except (ValueError, TypeError):
                        val = 0

                if key == 'notes' and isinstance(val, str):
                    val = val[:300]  # 截断过长文本

                default_fields[key] = {'value': val, 'confidence': min(max(conf, 0), 1)}
            elif isinstance(f, str):
                # 简单字符串值，给默认置信度0.8
                default_fields[key] = {'value': f.strip(), 'confidence': 0.8}

    return default_fields


def _classify_document(text: str) -> str:
    """快速判断文档类型（关键词匹配，供AI不可用时使用）"""
    text_200 = text[:500]
    if any(kw in text_200 for kw in ['起诉状', '民事起诉', '行政起诉', '原告', '被告', '诉讼请求']):
        if any(kw in text_200 for kw in ['判决书', '本院认为', '判决如下', '裁定如下']):
            return 'judgment'
        return 'complaint'
    if any(kw in text_200 for kw in ['判决书', '裁定书', '本院认为', '判决如下', '维持原判']):
        return 'judgment'
    return 'other'


def parse_legal_document(text: str) -> dict:
    """解析法律文书内容，提取案件关键信息

    Args:
        text: 文书全文（OCR提取或直接读取的文字）

    Returns:
        {
            "success": True/False,
            "method": "ai" | "regex" | "none",
            "document_type": "complaint" | "judgment" | "other",
            "fields": { ... },       # 各字段的 {value, confidence}
            "warnings": ["..."]      # 警告信息
        }
    """
    if not text or not text.strip():
        return {
            'success': False,
            'method': 'none',
            'document_type': 'other',
            'fields': _clean_fields({}),
            'warnings': ['文书内容为空'],
        }

    text = text.strip()

    # 截断过长文本（AI token 限制，最多12000字符给 AI）
    ai_text = text[:12000] if len(text) > 12000 else text

    fields = {}
    method = 'none'
    doc_type = 'other'
    warnings = []

    # ==================== Step 1: 尝试 AI 解析 ====================
    if ai_client.is_available():
        try:
            ai_result = ai_client.chat_json(ai_text, system_message=SYSTEM_PROMPT_LEGAL)

            if ai_result and 'fields' in ai_result:
                method = 'ai'
                doc_type = ai_result.get('document_type', 'other')
                fields = _clean_fields(ai_result.get('fields', {}))
            else:
                warnings.append('AI返回结果异常，回退到正则提取')
        except Exception as e:
            warnings.append(f'AI解析失败：{str(e)[:100]}，回退到正则提取')

    # ==================== Step 2: 正则回退 ====================
    if method != 'ai':
        doc_type = _classify_document(text)
        regex_fields = _try_regex(text)
        if regex_fields:
            method = 'regex'
            fields = _clean_fields(regex_fields)
        else:
            method = 'none'
            fields = _clean_fields({})
            warnings.append('未能从文书中提取到任何信息')

    # ==================== Step 3: 质量检查 ====================
    if not fields.get('case_number', {}).get('value'):
        warnings.append('未识别到案号')
    if not fields.get('case_reason', {}).get('value'):
        warnings.append('未识别到案由')
    if not fields.get('court', {}).get('value'):
        warnings.append('未识别到受理法院')

    # 检查低置信度字段
    low_conf_fields = []
    for key, f in fields.items():
        if isinstance(f, dict) and f.get('value') and f.get('confidence', 0) < 0.5:
            field_names = {
                'case_number': '案号', 'case_reason': '案由', 'court': '法院',
                'judge': '法官', 'clerk': '书记员', 'plaintiff': '原告',
                'defendant': '被告', 'amount_in_dispute': '标的额',
                'trial_date': '开庭日期', 'case_stage': '案件阶段', 'notes': '备注'
            }
            low_conf_fields.append(field_names.get(key, key))

    if low_conf_fields:
        warnings.append(f'以下字段识别置信度较低，请仔细核对：{", ".join(low_conf_fields)}')

    return {
        'success': method != 'none',
        'method': method,
        'document_type': doc_type,
        'fields': fields,
        'warnings': warnings,
    }
