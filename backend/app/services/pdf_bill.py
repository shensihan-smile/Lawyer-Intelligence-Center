"""PDF 账单生成服务（使用 ReportLab）"""
import os
import uuid
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor, black, grey
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus.flowables import Flowable

# ==================== 中文字体注册 ====================

_CJK_FONT_REGISTERED = False


def _register_cjk_font():
    """注册中文字体（只执行一次）"""
    global _CJK_FONT_REGISTERED
    if _CJK_FONT_REGISTERED:
        return

    # 尝试 Windows 常见中文字体路径
    font_candidates = [
        ("SimSun", "C:/Windows/Fonts/simsun.ttc"),     # 宋体
        ("SimHei", "C:/Windows/Fonts/simhei.ttf"),     # 黑体
        ("MSYH", "C:/Windows/Fonts/msyh.ttc"),          # 微软雅黑
        ("SimKai", "C:/Windows/Fonts/simkai.ttf"),     # 楷体
    ]

    for name, path in font_candidates:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont(name, path))
                _CJK_FONT_REGISTERED = True
                return name
            except Exception:
                continue

    # 都找不到，使用默认字体（可能不显示中文）
    return "Helvetica"


# ==================== 样式 ====================

def _build_styles(font_name: str):
    """构建段落样式"""
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        "CJN-Title",
        fontName=font_name,
        fontSize=18,
        leading=24,
        alignment=TA_CENTER,
        spaceAfter=8 * mm,
    ))
    styles.add(ParagraphStyle(
        "CJN-Heading",
        fontName=font_name,
        fontSize=12,
        leading=16,
        spaceBefore=6 * mm,
        spaceAfter=3 * mm,
    ))
    styles.add(ParagraphStyle(
        "CJN-Normal",
        fontName=font_name,
        fontSize=10,
        leading=14,
        spaceBefore=1 * mm,
        spaceAfter=1 * mm,
    ))
    styles.add(ParagraphStyle(
        "CJN-Right",
        fontName=font_name,
        fontSize=10,
        leading=14,
        alignment=TA_RIGHT,
    ))
    styles.add(ParagraphStyle(
        "CJN-Small",
        fontName=font_name,
        fontSize=8,
        leading=10,
        textColor=grey,
    ))

    return styles


# ==================== 生成 PDF ====================

def generate_bill_pdf(
    output_dir: str,
    bill_data: dict,
) -> str:
    """生成账单 PDF

    Args:
        output_dir: 输出目录
        bill_data: {
            "bill_number": "BILL-2026-00001",
            "client_name": "XX科技有限公司",
            "client_contact": "张总",
            "period_start": "2026-01-01",
            "period_end": "2026-03-31",
            "items": [
                {"description": "法律研究", "method": "按小时", "qty": "5.5小时", "unit_price": "2000元/小时", "amount": "11000.00"},
                ...
            ],
            "total_amount": "28500.00",
            "total_cn": "贰万捌仟伍佰元整",
            "firm_name": "XX律师事务所",
            "firm_address": "北京市朝阳区XX路XX号",
            "firm_phone": "010-12345678",
            "lawyer_name": "张三律师",
            "notes": "付款方式：银行转账",
            "bank_info": "开户行：XX银行 账号：XXXX",
        }

    Returns:
        PDF 文件路径，失败返回空字符串
    """
    font_name = _register_cjk_font()
    styles = _build_styles(font_name)

    output_name = f"bill_{uuid.uuid4().hex[:8]}.pdf"
    output_path = os.path.join(output_dir, output_name)

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
    )

    story = []

    # ---- 页眉：律所名称 ----
    firm = bill_data.get("firm_name", "")
    story.append(Paragraph(firm, styles["CJN-Title"]))
    story.append(HRFlowable(width="100%", thickness=1, color=black))
    story.append(Spacer(1, 5 * mm))

    # ---- 账单标题 ----
    story.append(Paragraph(f"对  账  单", styles["CJN-Title"]))
    story.append(Spacer(1, 3 * mm))

    # ---- 账单基本信息 ----
    bill_number = bill_data.get("bill_number", "")
    period = f"{bill_data.get('period_start', '')} 至 {bill_data.get('period_end', '')}"
    client_name = bill_data.get("client_name", "")
    client_contact = bill_data.get("client_contact", "")

    info_data = [
        [Paragraph("账单编号：", styles["CJN-Normal"]),
         Paragraph(bill_number, styles["CJN-Normal"]),
         Paragraph("计费期间：", styles["CJN-Normal"]),
         Paragraph(period, styles["CJN-Normal"])],
        [Paragraph("客户名称：", styles["CJN-Normal"]),
         Paragraph(client_name, styles["CJN-Normal"]),
         Paragraph("联系人：", styles["CJN-Normal"]),
         Paragraph(client_contact, styles["CJN-Normal"])],
    ]

    info_table = Table(info_data, colWidths=[2.2 * cm, 5 * cm, 2.2 * cm, 5 * cm])
    info_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 5 * mm))

    # ---- 服务明细表格 ----
    story.append(Paragraph("服务明细", styles["CJN-Heading"]))

    items = bill_data.get("items", [])
    table_header = ["序号", "服务内容", "计费方式", "数量", "单价", "金额（元）"]
    header_row = [Paragraph(h, styles["CJN-Normal"]) for h in table_header]

    table_data = [header_row]
    for i, item in enumerate(items, 1):
        row = [
            Paragraph(str(i), styles["CJN-Normal"]),
            Paragraph(item.get("description", ""), styles["CJN-Normal"]),
            Paragraph(item.get("method", ""), styles["CJN-Normal"]),
            Paragraph(item.get("qty", ""), styles["CJN-Normal"]),
            Paragraph(item.get("unit_price", ""), styles["CJN-Normal"]),
            Paragraph(item.get("amount", ""), styles["CJN-Right"]),
        ]
        table_data.append(row)

    col_widths = [1 * cm, 5.2 * cm, 2.2 * cm, 2.2 * cm, 2.2 * cm, 2.8 * cm]
    items_table = Table(table_data, colWidths=col_widths, repeatRows=1)

    items_table.setStyle(TableStyle([
        # Header
        ("BACKGROUND", (0, 0), (-1, 0), HexColor("#f0f0f0")),
        ("TEXTCOLOR", (0, 0), (-1, 0), black),
        ("FONTNAME", (0, 0), (-1, -1), font_name),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        # Grid
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#cccccc")),
        ("LINEBELOW", (0, 0), (-1, 0), 1, black),
        # Align
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (3, 1), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        # Padding
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 5 * mm))

    # ---- 费用汇总 ----
    total = bill_data.get("total_amount", "0")
    total_cn = bill_data.get("total_cn", "")

    summary_data = [
        [Paragraph("费用合计：", styles["CJN-Normal"]),
         Paragraph(f"¥ {total}", styles["CJN-Normal"])],
    ]
    if total_cn:
        summary_data.append([
            Paragraph("大写金额：", styles["CJN-Normal"]),
            Paragraph(total_cn, styles["CJN-Normal"]),
        ])

    summary_table = Table(summary_data, colWidths=[2.5 * cm, 8 * cm])
    summary_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("TEXTCOLOR", (0, 0), (0, -1), black),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 8 * mm))

    # ---- 律所信息 ----
    story.append(HRFlowable(width="100%", thickness=0.5, color=grey))
    story.append(Spacer(1, 4 * mm))

    lawyer = bill_data.get("lawyer_name", "")
    firm_addr = bill_data.get("firm_address", "")
    firm_phone = bill_data.get("firm_phone", "")
    notes = bill_data.get("notes", "")
    bank = bill_data.get("bank_info", "")

    footer_lines = []
    if lawyer:
        footer_lines.append(f"承办律师：{lawyer}")
    if firm_addr:
        footer_lines.append(f"地址：{firm_addr}")
    if firm_phone:
        footer_lines.append(f"电话：{firm_phone}")
    if bank:
        footer_lines.append(f"银行账户：{bank}")
    if notes:
        footer_lines.append(f"备注：{notes}")

    for line in footer_lines:
        story.append(Paragraph(line, styles["CJN-Small"]))

    story.append(Spacer(1, 5 * mm))
    story.append(Paragraph(
        f"制单日期：{datetime.now().strftime('%Y年%m月%d日')}",
        styles["CJN-Right"],
    ))

    # ---- 生成 ----
    try:
        doc.build(story)
        return output_path
    except Exception as e:
        print(f"[PDF] 生成失败: {e}")
        return ""


# ==================== 金额大写转换 ====================

def amount_to_chinese(amount: float) -> str:
    """将数字金额转为中文大写"""
    if amount == 0:
        return "零元整"

    digits = "零壹贰叁肆伍陆柒捌玖"
    units = ["", "拾", "佰", "仟"]
    big_units = ["", "万", "亿"]

    # 分两部分处理：整数和小数
    int_part = int(amount)
    decimal_part = round((amount - int_part) * 100)

    def _convert_int(n: int) -> str:
        if n == 0:
            return "零"
        result = ""
        n_str = str(n)
        length = len(n_str)
        for i, ch in enumerate(n_str):
            d = int(ch)
            pos = (length - i - 1) % 4
            big_pos = (length - i - 1) // 4
            if d != 0:
                result += digits[d] + units[pos]
            else:
                # 连续的零只保留一个
                if result and result[-1] != "零":
                    result += "零"
            if pos == 0 and big_pos > 0:
                result += big_units[big_pos]
        result = result.rstrip("零")
        return result

    result = _convert_int(int_part) + "元"
    if decimal_part > 0:
        jiao = decimal_part // 10
        fen = decimal_part % 10
        if jiao > 0:
            result += digits[jiao] + "角"
        if fen > 0:
            result += digits[fen] + "分"
    else:
        result += "整"

    return result
