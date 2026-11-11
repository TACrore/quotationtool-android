# -*- coding: utf-8 -*-
"""Android 端出 PDF：fpdf2（纯 Python，无 C 依赖）；Windows 端仍用 reportlab"""
import os


HERE = os.path.dirname(os.path.abspath(__file__))
_CANDIDATES = [os.path.join(HERE, "pdf-font.ttf"),
               os.path.join(HERE, "assets", "pdf-font.ttf"),
               os.path.join(HERE, "sy-cjk.ttf")]
FONT = next((f for f in _CANDIDATES if os.path.exists(f)), _CANDIDATES[-1])


def make_quote_pdf(path, cust_code, item, cust_name="", font_path=None):
    if os.path.exists(path) and os.path.getsize(path) > 1000:
        return path
    from fpdf import FPDF  # 延迟导入：无 fpdf 时界面仍可用
    pdf = FPDF(unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    font = font_path or FONT
    if os.path.exists(font):
        pdf.add_font("SY", "", font)
        pdf.set_font("SY", size=16)
    else:
        pdf.set_font("Helvetica", size=16)

    pdf.cell(0, 12, "报价单 / Quotation", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font_size(10)
    rows = [
        ("客户编号 / Customer", cust_code),
        ("客户名称 / Name", cust_name),
        ("图号 / Part No.", item.get("fig", "")),
        ("规格 / Spec", item.get("spec", "")),
        ("单价 / Unit Price", f"{item.get('price','')} {item.get('cur','')}"),
        ("起订量 / MOQ", item.get("moq", "")),
        ("报价日期 / Date", item.get("date", "")),
        ("报价确认人 / Confirmed by", item.get("confirm", "")),
    ]
    for k, v in rows:
        pdf.cell(45, 8, k, border=1)
        pdf.cell(0, 8, str(v), border=1, new_x="LMARGIN", new_y="NEXT")
    pdf.output(path)
    return path
