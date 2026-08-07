"""常法顾问工作报告 PDF 生成服务（使用 ReportLab）"""
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

# ==================== 中文字体注册 ====================

_CJK_FONT_REGISTERED = False


def _register_cjk_font():
    """注册中文字体（只执行一次）"""
    global _CJK_FONT_REGISTERED
    if _CJK_FONT_REGISTERED:
        return

    font_candidates = [
        ("SimSun", "C:/Windows/Fonts/simsun.ttc"),
        ("SimHei", "C:/Windows/Fonts/simhei.ttf"),
        ("MSYH", "C:/Windows/Fonts/msyh.ttc"),
        ("SimKai", "C:/Windows/Fonts/simkai.ttf"),
    ]

    for name, path in font_candidates:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont(name, path))
                _CJK_FONT_REGISTERED = True
                return name
            except Exception:
                continue

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
        "CJN-Subtitle",
        fontName=font_name,
        fontSize=14,
        leading=18,
        alignment=TA_CENTER,
        spaceAfter=4 * mm,
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
    styles.add(ParagraphStyle(
        "CJN-Cover",
        fontName=font_name,
        fontSize=22,
        leading=30,
        alignment=TA_CENTER,
        spaceAfter=12 * mm,
    ))

    return styles


# ==================== 颜色 ====================

MORANDI_SLATE = HexColor("#5b6e7a")
MORANDI_TAUPE = HexColor("#b09878")
MORANDI_SAGE = HexColor("#7a9a7e")
LIGHT_BG = HexColor("#f5f2ed")


# ==================== 生成 PDF ====================

def generate_retainer_report_pdf(
    output_dir: str,
    data: dict,
) -> str:
    """生成常法顾问工作报告 PDF

    Args:
        output_dir: 输出目录
        data: {
            "client_name": "XX科技有限公司",
            "contract_number": "HT-2026-001",
            "period_start": "2026年01月01日",
            "period_end": "2026年06月30日",
            "content": {
                "summary": "概述文字",
                "work_summary": {"total_count": 45, "total_hours": 120.5},
                "type_distribution": [{"label": "合同审查", "hours": 50.0, "count": 20}, ...],
                "work_records": [{"date": "...", "work_type": "...", "description": "...", "hours": 2.0}, ...],
                "monthly_trend": [{"month": "2026-01", "label": "1月", "hours": 20, "count": 8}, ...],
                "suggestions": "总结与建议文字",
            }
        }

    Returns:
        PDF 文件路径，失败返回空字符串
    """
    font_name = _register_cjk_font()
    styles = _build_styles(font_name)

    output_name = f"retainer_report_{uuid.uuid4().hex[:8]}.pdf"
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

    content = data.get("content", {})
    if isinstance(content, str):
        import json
        try:
            content = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            content = {}

    # ========== 封面 ==========
    story.append(Spacer(1, 4 * cm))
    story.append(Paragraph("常年法律顾问", styles["CJN-Cover"]))
    story.append(Paragraph("工 作 报 告", styles["CJN-Cover"]))
    story.append(Spacer(1, 2 * cm))

    client_name = data.get("client_name", "")
    period = f"{data.get('period_start', '')} — {data.get('period_end', '')}"

    cover_info = [
        [Paragraph("客户名称：", styles["CJN-Normal"]),
         Paragraph(client_name, styles["CJN-Normal"])],
        [Paragraph("服务期间：", styles["CJN-Normal"]),
         Paragraph(period, styles["CJN-Normal"])],
    ]
    contract_number = data.get("contract_number", "")
    if contract_number:
        cover_info.append([
            Paragraph("合同编号：", styles["CJN-Normal"]),
            Paragraph(contract_number, styles["CJN-Normal"]),
        ])

    cover_table = Table(cover_info, colWidths=[2.5 * cm, 8 * cm])
    cover_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("ALIGN", (0, 0), (0, -1), "RIGHT"),
    ]))
    story.append(cover_table)
    story.append(Spacer(1, 3 * cm))
    story.append(Paragraph(
        f"报告生成日期：{datetime.now().strftime('%Y年%m月%d日')}",
        styles["CJN-Right"],
    ))
    story.append(PageBreak())

    # ========== 一、服务概况 ==========
    story.append(Paragraph("一、服务概况", styles["CJN-Heading"]))
    story.append(HRFlowable(width="100%", thickness=1, color=MORANDI_SLATE))
    story.append(Spacer(1, 3 * mm))

    summary = content.get("summary", "")
    if summary:
        story.append(Paragraph(summary, styles["CJN-Normal"]))
        story.append(Spacer(1, 3 * mm))

    work_summary = content.get("work_summary", {})
    total_count = work_summary.get("total_count", 0)
    total_hours = work_summary.get("total_hours", 0)

    overview_data = [
        [Paragraph("服务期间", styles["CJN-Normal"]),
         Paragraph(period, styles["CJN-Normal"])],
        [Paragraph("工作总次数", styles["CJN-Normal"]),
         Paragraph(f"{total_count} 次", styles["CJN-Normal"])],
        [Paragraph("工作总时长", styles["CJN-Normal"]),
         Paragraph(f"{total_hours} 小时", styles["CJN-Normal"])],
    ]

    overview_table = Table(overview_data, colWidths=[3 * cm, 10 * cm])
    overview_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("BACKGROUND", (0, 0), (0, -1), LIGHT_BG),
        ("ALIGN", (0, 0), (0, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#dddddd")),
    ]))
    story.append(overview_table)
    story.append(Spacer(1, 5 * mm))

    # ========== 二、工作内容汇总 ==========
    story.append(Paragraph("二、工作内容汇总", styles["CJN-Heading"]))
    story.append(HRFlowable(width="100%", thickness=1, color=MORANDI_SLATE))
    story.append(Spacer(1, 3 * mm))

    type_dist = content.get("type_distribution", [])
    if type_dist:
        table_header = ["工作类型", "次数", "小时数", "占比"]
        header_row = [Paragraph(h, styles["CJN-Normal"]) for h in table_header]

        table_data = [header_row]
        for item in type_dist:
            pct = f"{item.get('hours', 0) / max(1, total_hours) * 100:.1f}%"
            row = [
                Paragraph(item.get("label", item.get("type", "")), styles["CJN-Normal"]),
                Paragraph(str(item.get("count", 0)), styles["CJN-Normal"]),
                Paragraph(f"{item.get('hours', 0):.1f}", styles["CJN-Normal"]),
                Paragraph(pct, styles["CJN-Normal"]),
            ]
            table_data.append(row)

        col_widths = [5 * cm, 2.5 * cm, 2.5 * cm, 2.5 * cm]
        type_table = Table(table_data, colWidths=col_widths, repeatRows=1)
        type_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), LIGHT_BG),
            ("FONTNAME", (0, 0), (-1, -1), font_name),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#dddddd")),
            ("LINEBELOW", (0, 0), (-1, 0), 1, MORANDI_SLATE),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (1, 1), (3, -1), "CENTER"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(type_table)
        story.append(Spacer(1, 5 * mm))

    # ========== 三、工作明细 ==========
    story.append(Paragraph("三、工作明细", styles["CJN-Heading"]))
    story.append(HRFlowable(width="100%", thickness=1, color=MORANDI_SLATE))
    story.append(Spacer(1, 3 * mm))

    work_records = content.get("work_records", [])
    if work_records:
        # 按月分组
        from collections import OrderedDict
        grouped = OrderedDict()
        for w in work_records:
            month_key = w.get("date", "")[:7]
            if month_key not in grouped:
                grouped[month_key] = []
            grouped[month_key].append(w)

        for month_key, records in grouped.items():
            # 月份标题
            try:
                ym = datetime.strptime(month_key, "%Y-%m")
                month_label = ym.strftime("%Y年%m月")
            except (ValueError, TypeError):
                month_label = month_key
            story.append(Paragraph(month_label, styles["CJN-Heading"]))

            detail_header = ["日期", "工作类型", "工作内容", "时长(h)"]
            detail_data = [[Paragraph(h, styles["CJN-Normal"]) for h in detail_header]]

            for w in records:
                date_str = w.get("date", "")[:10] if w.get("date") else ""
                row = [
                    Paragraph(date_str, styles["CJN-Small"]),
                    Paragraph(w.get("work_type", ""), styles["CJN-Small"]),
                    Paragraph(w.get("description", ""), styles["CJN-Small"]),
                    Paragraph(f"{w.get('hours', 0):.1f}", styles["CJN-Small"]),
                ]
                detail_data.append(row)

            detail_cols = [2.5 * cm, 3 * cm, 7 * cm, 2 * cm]
            detail_table = Table(detail_data, colWidths=detail_cols, repeatRows=1)
            detail_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), LIGHT_BG),
                ("FONTNAME", (0, 0), (-1, -1), font_name),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#eeeeee")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (3, 1), (3, -1), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ]))
            story.append(detail_table)
            story.append(Spacer(1, 3 * mm))
    else:
        story.append(Paragraph("本期间暂无工作记录。", styles["CJN-Normal"]))

    story.append(Spacer(1, 5 * mm))

    # ========== 四、总结与建议 ==========
    story.append(Paragraph("四、总结与建议", styles["CJN-Heading"]))
    story.append(HRFlowable(width="100%", thickness=1, color=MORANDI_SLATE))
    story.append(Spacer(1, 3 * mm))

    suggestions = content.get("suggestions", "")
    if suggestions:
        for line in suggestions.split("\n"):
            line = line.strip()
            if line:
                story.append(Paragraph(line, styles["CJN-Normal"]))
    else:
        story.append(Paragraph("（请在此处填写总结与建议）", styles["CJN-Normal"]))

    story.append(Spacer(1, 10 * mm))

    # ========== 页脚 ==========
    story.append(HRFlowable(width="100%", thickness=0.5, color=grey))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(
        f"本报告由律师智能中心系统自动生成 | 生成日期：{datetime.now().strftime('%Y年%m月%d日')}",
        styles["CJN-Small"],
    ))
    story.append(Paragraph(
        "本报告内容仅供客户内部参考使用，不构成法律意见。",
        styles["CJN-Small"],
    ))

    # ---- 生成 ----
    try:
        doc.build(story)
        return output_path
    except Exception as e:
        print(f"[PDF] 常法报告生成失败: {e}")
        return ""
