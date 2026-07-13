"""文档图片化服务：将文档导出为长图或分页图"""
import os
import uuid
import tempfile
import fitz  # PyMuPDF
from PIL import Image, ImageDraw, ImageFont


def _add_watermark(image: Image.Image, text: str, font_size: int = 36) -> Image.Image:
    """在图片上添加半透明水印文字"""
    if not text:
        return image

    # 创建透明水印层
    overlay = Image.new("RGBA", image.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)

    # 尝试加载中文字体，失败用默认
    try:
        # Windows 常见中文字体路径
        font_paths = [
            "C:/Windows/Fonts/simhei.ttf",      # 黑体
            "C:/Windows/Fonts/msyh.ttc",         # 微软雅黑
            "C:/Windows/Fonts/simsun.ttc",       # 宋体
            "C:/Windows/Fonts/simkai.ttf",       # 楷体
        ]
        font = None
        for fp in font_paths:
            if os.path.exists(fp):
                font = ImageFont.truetype(fp, font_size)
                break
        if font is None:
            font = ImageFont.load_default()
    except Exception:
        font = ImageFont.load_default()

    # 计算水印位置（对角线平铺）
    text_color = (180, 180, 180, 80)  # 半透明灰色
    spacing_x = image.width // 3
    spacing_y = image.height // 3

    for x in range(-image.width // 2, image.width * 2, spacing_x):
        for y in range(-image.height // 2, image.height * 2, spacing_y):
            # 旋转绘制水印
            try:
                # 创建单个水印文字图片并旋转
                bbox = font.getbbox(text) if hasattr(font, 'getbbox') else (0, 0, 200, font_size)
                tw = bbox[2] - bbox[0]
                th = bbox[3] - bbox[1]
                txt_img = Image.new("RGBA", (tw + 40, th + 40), (255, 255, 255, 0))
                txt_draw = ImageDraw.Draw(txt_img)
                txt_draw.text((20, 20), text, font=font, fill=text_color)
                txt_img = txt_img.rotate(30, expand=True)
                overlay.paste(txt_img, (x, y), txt_img)
            except Exception:
                pass

    # 合并水印层
    result = Image.alpha_composite(image.convert("RGBA"), overlay)
    return result


def _pdf_to_images(
    pdf_path: str,
    output_dir: str,
    mode: str = "pages",      # "long" 或 "pages"
    dpi: int = 150,
    watermark_text: str = "",
) -> list:
    """将 PDF 渲染为图片列表

    Args:
        pdf_path: PDF 文件路径
        output_dir: 输出目录
        mode: "long" 生成一张长图 / "pages" 每页一张图
        dpi: 图片分辨率
        watermark_text: 水印文字（空字符串表示无水印）

    Returns:
        生成的图片文件路径列表
    """
    zoom = dpi / 72.0  # PDF 默认 72 DPI
    mat = fitz.Matrix(zoom, zoom)

    pdf = fitz.open(pdf_path)
    page_images: list[Image.Image] = []

    for page_num in range(len(pdf)):
        page = pdf[page_num]
        pix = page.get_pixmap(matrix=mat)
        # 转为 PIL Image
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        # 添加水印
        if watermark_text:
            img = _add_watermark(img, watermark_text)
        page_images.append(img)

    pdf.close()

    result_paths = []

    if mode == "long":
        # 拼接为长图
        if not page_images:
            return []

        total_height = sum(img.height for img in page_images)
        max_width = max(img.width for img in page_images)
        # 页间分隔线高度
        separator_height = 6 if len(page_images) > 1 else 0

        long_img = Image.new("RGB", (max_width, total_height + separator_height), "white")
        y_offset = 0
        for i, img in enumerate(page_images):
            # 居中粘贴（不同页可能宽度略有差异）
            x_offset = (max_width - img.width) // 2
            long_img.paste(img, (x_offset, y_offset))

            y_offset += img.height

            # 画分隔线（最后一页不加）
            if i < len(page_images) - 1:
                draw = ImageDraw.Draw(long_img)
                draw.line(
                    [(0, y_offset + 3), (max_width, y_offset + 3)],
                    fill=(200, 200, 200),
                    width=1,
                )
                y_offset += separator_height

        output_name = f"long_{uuid.uuid4().hex[:8]}.png"
        output_path = os.path.join(output_dir, output_name)
        long_img.save(output_path, "PNG", optimize=True)
        result_paths.append(output_path)

    else:
        # 每页一张图
        for i, img in enumerate(page_images):
            output_name = f"page_{i+1:03d}_{uuid.uuid4().hex[:6]}.png"
            output_path = os.path.join(output_dir, output_name)
            img.save(output_path, "PNG", optimize=True)
            result_paths.append(output_path)

    return result_paths


def document_to_images(
    file_path: str,
    file_type: str,
    output_dir: str,
    mode: str = "pages",
    dpi: int = 150,
    watermark_text: str = "",
) -> list:
    """将文档（PDF 或 Word）导出为图片

    Word 文件会先转为 PDF 再渲染。

    Args:
        file_path: 源文件路径
        file_type: 文件类型（pdf / doc / docx）
        output_dir: 图片输出目录
        mode: "long" 长图 / "pages" 分页图
        dpi: 分辨率（DPI），默认 150
        watermark_text: 水印文字

    Returns:
        生成的图片文件路径列表，失败返回空列表
    """
    pdf_path = file_path
    temp_pdf = None

    # Word → PDF 预处理
    if file_type.lower() in ("doc", "docx", "docm"):
        from app.services.document_converter import word_to_pdf
        pdf_path = word_to_pdf(file_path, output_dir)
        if not pdf_path:
            print("[document_to_images] Word → PDF 转换失败")
            return []
        temp_pdf = pdf_path  # 标记为临时文件，用完清理

    try:
        return _pdf_to_images(pdf_path, output_dir, mode=mode, dpi=dpi, watermark_text=watermark_text)
    finally:
        # 清理临时 PDF
        if temp_pdf and os.path.exists(temp_pdf):
            try:
                os.remove(temp_pdf)
            except OSError:
                pass
