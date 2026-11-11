# -*- coding: utf-8 -*-
"""A4 报价单渲染（reportlab）：LOGO + 公章 + 全居中 + 紧凑版式"""
import datetime
import os
import sys

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle)

TAX = 1.13
FONT_NAME = "YaHei"
NAVY = colors.HexColor("#1F4E79")
LINE = colors.HexColor("#B9C6D6")
ZEBRA = colors.HexColor("#F2F6FB")
HERE = os.path.dirname(os.path.abspath(__file__))


def _asset(name):
    import sys as _sys
    cands = [HERE,
             getattr(_sys, "_MEIPASS", ""),
             os.path.dirname(_sys.executable),
             os.path.dirname(os.path.dirname(os.path.abspath(__file__)))]
    for d in cands:
        if not d:
            continue
        for sub in ("assets", ""):
            p = os.path.join(d, sub, name) if sub else os.path.join(d, name)
            if os.path.exists(p):
                return p
    return ""


def _font_dirs():
    out = [HERE]
    try:
        out.append(os.path.join(HERE, "fonts"))
    except Exception:
        pass
    for base in (getattr(sys, "_MEIPASS", None), os.path.dirname(sys.executable)):
        if base:
            out.append(os.path.join(base, "fonts"))
            out.append(base)
    out.append(r"C:\Windows\Fonts")
    return [d for d in out if d]


def _font():
    if FONT_NAME in pdfmetrics.getRegisteredFontNames():
        return FONT_NAME

    reg = bold = None
    for d in _font_dirs():
        if not os.path.isdir(d):
            continue
        for name in ("sy-cjk.ttf",):
            p = os.path.join(d, name)
            if reg is None and os.path.exists(p):
                reg = p
        for name in ("sy-cjk-bold.ttf",):
            p = os.path.join(d, name)
            if bold is None and os.path.exists(p):
                bold = p
        # 兼容系统字体（没打包时）
        if reg is None:
            for name, idx in (("msyh.ttc", 0), ("simsun.ttc", 0)):
                p = os.path.join(d, name)
                if os.path.exists(p):
                    reg = (p, idx)
                    break
        if bold is None:
            p = os.path.join(d, "msyhbd.ttc")
            if os.path.exists(p):
                bold = (p, 0)

    if isinstance(reg, tuple):
        try:
            pdfmetrics.registerFont(TTFont(FONT_NAME, reg[0], subfontIndex=reg[1]))
        except Exception:
            reg = None
    elif reg:
        try:
            pdfmetrics.registerFont(TTFont(FONT_NAME, reg))
        except Exception:
            reg = None

    if isinstance(bold, tuple):
        try:
            pdfmetrics.registerFont(TTFont(FONT_BOLD, bold[0], subfontIndex=bold[1]))
        except Exception:
            bold = None
    elif bold:
        try:
            pdfmetrics.registerFont(TTFont(FONT_BOLD, bold))
        except Exception:
            bold = None

    if reg:
        try:
            pdfmetrics.registerFontFamily(FONT_NAME, normal=FONT_NAME,
                                          bold=(FONT_BOLD if bold else FONT_NAME),
                                          italic=FONT_NAME,
                                          boldItalic=(FONT_BOLD if bold else FONT_NAME))
        except Exception:
            pass
        return FONT_NAME
    return "Helvetica"


LABELS = {
    "company": ("公司名", "Company"), "contact": ("客户负责人", "Attn."),
    "addr": ("客户地址", "Address"), "tel": ("联系方式", "Tel."),
    "date": ("日期", "Date"), "no": ("序号", "No."), "fig": ("图号", "Drawing No."),
    "spec": ("规格", "Spec"), "part": ("品号/品名", "Part No. / Name"),
    "price": ("单价", "Unit Price"), "moq": ("最小起订量", "MOQ"),
    "remark": ("备注", "Remark"), "term": ("交易条件", "Trade Term"),
    "confirm": ("报价确认人", "Confirmed by"), "mail": ("邮箱", "E-mail"),
}


def _L(key, bilingual, sub_color="#3C4A5E"):
    zh, en = LABELS[key]
    return f"{zh}<br/><font size=7.2 color='{sub_color}'>{en}</font>" if bilingual else zh


def _fmt_term(text):
    """交易条件排版：编号项（1. 2. …）各自换行，其余保持原样"""
    import re as _re
    t = str(text or "")
    t = t.replace("\r", "")
    t = _re.sub(r"(?<![\d.])(\d{1,2})[.、．]\s*", r"<br/>\1.", t)
    t = t.replace("<br/>", "\n")
    lines = [x.strip() for x in t.split("\n") if x.strip()]
    return "<br/>".join(lines)


def _fmt_remark(text):
    """备注排版：去空格，1./2./3. 各自换行"""
    import re as _re
    t = str(text or "")
    has_cjk = any("\u4e00" <= ch <= "\u9fff" for ch in t)
    if has_cjk:
        t = t.replace("\u3000", "").replace(" ", "").replace("　", "")
    t = _re.sub(r"(?<![\d.])(\d{1,2})[.、．]", r"\n\1.", t)
    lines = [x.strip() for x in t.split("\n") if x.strip()]
    return "<br/>".join(lines)


def build(cust, items, opts, path):
    fn = _font()
    cur = "RMB"
    if str(opts.get("currency")) == "2":
        cur = "EUR" if str(opts.get("usd_or_euro")) == "2" else "USD"
    rate = float(opts.get("rate_eur") if cur == "EUR" and opts.get("rate_eur")
                 else (opts.get("rate") or 7.10))
    foreign = cur != "RMB"
    _tax = str(opts.get("taxmode") or "both")
    only_incl = _tax in ("incl", "2") or foreign     # 只显示含税单价
    only_excl = _tax in ("excl", "3") and not foreign  # 只显示未税单价
    bilingual = foreign

    st_co = ParagraphStyle("co", fontName=fn, fontSize=17, leading=21, alignment=TA_CENTER, textColor=NAVY)
    st_co_en = ParagraphStyle("coen", fontName=fn, fontSize=10.5, leading=13, alignment=TA_CENTER,
                              textColor=colors.HexColor("#3C4A5E"))
    st_title = ParagraphStyle("t", fontName=fn, fontSize=13, leading=16, alignment=TA_CENTER,
                              textColor=colors.white)
    st_label = ParagraphStyle("l", fontName=fn, fontSize=7.6, leading=9.5, alignment=TA_LEFT,
                              textColor=colors.HexColor("#3C4A5E"))
    st_val = ParagraphStyle("v", fontName=fn, fontSize=9.2, leading=12, alignment=TA_LEFT,
                            textColor=colors.HexColor("#1F2A3A"))
    st_addr = ParagraphStyle("a", fontName=fn, fontSize=8.6, leading=11, alignment=TA_LEFT,
                             textColor=colors.HexColor("#1F2A3A"))
    st_cell = ParagraphStyle("c", fontName=fn, fontSize=8.6, leading=11, alignment=TA_CENTER,
                            textColor=colors.HexColor("#1F2A3A"))
    st_head = ParagraphStyle("h", fontName=fn, fontSize=8.6, leading=11, alignment=TA_CENTER,
                            textColor=colors.white)
    st_note = ParagraphStyle("n", fontName=fn, fontSize=7.8, leading=10.5, alignment=TA_CENTER,
                             textColor=colors.HexColor("#33404F"))
    st_note_l = ParagraphStyle("nl", fontName=fn, fontSize=7.8, leading=10.5, alignment=TA_LEFT,
                               textColor=colors.HexColor("#33404F"))
    # 备注列：长文本用更小字号，避免溢出表格
    st_cell_remark = ParagraphStyle("cr", fontName=fn, fontSize=7.6, leading=9.2,
                                    alignment=TA_CENTER,
                                    textColor=colors.HexColor("#1F2A3A"))
    st_cell_remark_long = ParagraphStyle("crl", fontName=fn, fontSize=6.4, leading=7.8,
                                         alignment=TA_LEFT,
                                         textColor=colors.HexColor("#1F2A3A"))
    # 底部备注：更醒目
    st_bottom = ParagraphStyle("bt", fontName=fn, fontSize=9.6, leading=13.2,
                               alignment=TA_LEFT,
                               textColor=colors.HexColor("#1A2433"))

    story = []
    logo_p = _asset("logo.png")
    left = Image(logo_p, width=26 * mm, height=26 * mm * 1300 / 1870) if os.path.exists(logo_p) \
        else Paragraph("", st_val)
    head = Table([[left,
                   [Paragraph("温州神一轴业股份有限公司", st_co),
                    Paragraph("WENZHOU SHENYI SHAFT INDUSTRIES CO.,LTD.", st_co_en)],
                   ""]], colWidths=[30 * mm, 130 * mm, 30 * mm])
    head.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                              ("ALIGN", (0, 0), (0, 0), "LEFT"),
                              ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                              ("TOPPADDING", (0, 0), (-1, -1), 0)]))
    story.append(head)
    story.append(Spacer(1, 2.5 * mm))

    doc_type = str(opts.get("doc_type") or "normal")
    if doc_type == "sample":
        title_txt = "样品报价单&nbsp;&nbsp;/&nbsp;&nbsp;SAMPLE QUOTATION" if bilingual else "样品报价单"
    else:
        title_txt = "报 价 单&nbsp;&nbsp;/&nbsp;&nbsp;QUOTATION" if bilingual else "报 价 单"
    band = Table([[Paragraph(title_txt, st_title)]], colWidths=[190 * mm], rowHeights=[9 * mm])
    band.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), NAVY),
                              ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    story.append(band)
    story.append(Spacer(1, 3.4 * mm))

    attn = opts.get("attn") or ""
    if not attn:
        for it in items:
            if it.get("attn"):
                attn = it["attn"]
                break
    attn = attn or cust.get("contact") or ""

    info = [
        [Paragraph(_L("company", bilingual), st_label), Paragraph(str(cust["name"]), st_val),
         Paragraph(_L("contact", bilingual), st_label), Paragraph(str(attn), st_val)],
        [Paragraph(_L("addr", bilingual), st_label), Paragraph(str(cust["addr"]), st_addr), "", ""],
        [Paragraph(_L("tel", bilingual), st_label), Paragraph(str(cust["tel"]), st_val),
         Paragraph(_L("date", bilingual), st_label), Paragraph(f"{datetime.date.today():%Y-%m-%d}", st_val)],
    ]
    t_info = Table(info, colWidths=[22 * mm, 76 * mm, 22 * mm, 70 * mm])
    t_info.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("SPAN", (1, 1), (3, 1)),
        ("LINEBELOW", (1, 0), (1, 0), 0.4, LINE),
        ("LINEBELOW", (3, 0), (3, 0), 0.4, LINE),
        ("LINEBELOW", (1, 1), (3, 1), 0.4, LINE),
        ("LINEBELOW", (1, 2), (1, 2), 0.4, LINE),
        ("LINEBELOW", (3, 2), (3, 2), 0.4, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 3.6), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.6),
    ]))
    story.append(t_info)
    story.append(Spacer(1, 3.4 * mm))

    heads = [_L("no", bilingual, "#FFFFFF"), _L("fig", bilingual, "#FFFFFF"),
             _L("spec", bilingual, "#FFFFFF"), _L("part", bilingual, "#FFFFFF")]
    if foreign:
        heads.append(f"单价 Price<br/><font size=7.2 color='#FFFFFF'>({cur})</font>")
    elif only_incl:
        heads.append(f"含税单价<br/><font size=7.2 color='#FFFFFF'>({cur} 含税)</font>")
    elif only_excl:
        heads.append(f"未税单价<br/><font size=7.2 color='#FFFFFF'>({cur})</font>")
    else:
        heads.append(f"未税单价<br/><font size=7.2 color='#FFFFFF'>({cur})</font>")
        heads.append(f"含税单价<br/><font size=7.2 color='#FFFFFF'>(含 13%)</font>")
    heads += [_L("moq", bilingual, "#FFFFFF"), _L("remark", bilingual, "#FFFFFF")]

    rows = [[Paragraph(h, st_head) for h in heads]]
    for i, it in enumerate(items, 1):
        try:
            base = float(str(it["price"]).replace(",", ""))
        except Exception:
            base = None
        if base is None:
            unit = None
        elif foreign:
            unit = base          # 外币：按录入单价原样显示，不换算
        else:
            unit = base   # 录入价即该模式下的单价（含税模式不再乘 1.13）
        row = [Paragraph(str(i), st_cell), Paragraph(str(it["fig"]), st_cell),
               Paragraph(str(it["spec"]), st_cell), Paragraph(str(it["part"]), st_cell),
               Paragraph("-" if unit is None else f"{unit:,.4f}", st_cell)]
        if not foreign and not only_incl and not only_excl:
            row.append(Paragraph("-" if unit is None else f"{unit * TAX:,.4f}", st_cell))
        rmk = _fmt_remark(it["remark"])
        rmk_plain = rmk.replace("<br/>", " ")
        if len(rmk_plain) > 300:
            rmk = rmk[:300].rsplit("<br/>", 1)[0] + "…"
        rmk_style = st_cell if len(rmk_plain) <= 60 else st_cell_remark_long
        row += [Paragraph(str(it["moq"]), st_cell), Paragraph(rmk, rmk_style)]
        rows.append(row)

    widths = [14 * mm, 38 * mm, 26 * mm, 26 * mm, 24 * mm]
    if not foreign and not only_incl and not only_excl:
        widths.append(20 * mm)
    widths += [30 * mm, 34 * mm]
    widths = widths[: len(heads)]
    # 撑满内容区宽度 190mm，右侧与标题带、交易条件框对齐
    _total = sum(widths)
    widths = [w * (190 * mm) / _total for w in widths]
    t = Table(rows, colWidths=widths, repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("GRID", (0, 0), (-1, -1), 0.35, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 4.4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4.4),
        ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
    ]
    for r in range(1, len(rows)):
        if r % 2 == 0:
            style.append(("BACKGROUND", (0, r), (-1, r), ZEBRA))
    t.setStyle(TableStyle(style))
    story.append(t)
    story.append(Spacer(1, 7 * mm))

    term_rows = [[Paragraph(f"<b>{_L('term', bilingual)}</b>", st_note),
                  Paragraph(_fmt_term(cust["term"]), st_note_l)]]
    if foreign:
        term_rows.append([Paragraph("币种 Currency", st_note),
                          Paragraph(f"{cur}" + ("" if not bilingual else " (prices exclude VAT)"), st_note_l)])
    elif only_incl:
        term_rows.append([Paragraph("税率 Tax", st_note),
                          Paragraph("单价为含税价（已含 13% 增值税）" if not bilingual
                                    else "Unit price is inclusive of 13% VAT", st_note_l)])
    else:
        term_rows.append([Paragraph("税率 Tax", st_note),
                          Paragraph("含税价 = 未税单价 × 1.13" if not bilingual
                                    else "Price incl. tax = unit price × 1.13", st_note_l)])
    t_term = Table(term_rows, colWidths=[24 * mm, 166 * mm])
    t_term.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F7F9FC")),
        ("BOX", (0, 0), (-1, -1), 0.4, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#E3EAF3")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4.0), ("BOTTOMPADDING", (0, 0), (-1, -1), 4.0),
    ]))
    story.append(t_term)
    story.append(Spacer(1, 3.4 * mm))

    bottom = next((it["bottom"] for it in items if it.get("bottom")), "")
    if bottom:
        txt = str(bottom).strip()
        story.append(Paragraph("备注 Note: " + txt, st_bottom))
        story.append(Spacer(1, 3.4 * mm))

    conf = opts.get("confirm") or ""
    mail = opts.get("mail") or ""
    # 确认人按记录里保存的名字原样打印（RMB=中文，USD/EUR=中英文）

    from reportlab.lib.utils import ImageReader

    def foot(canvas, doc):
        canvas.saveState()
        last = (canvas.getPageNumber() == getattr(doc, "_total_pages", 1))
        if not last:
            canvas.setStrokeColor(LINE)
            canvas.setLineWidth(0.6)
            canvas.line(10 * mm, 12 * mm, A4[0] - 10 * mm, 12 * mm)
            canvas.setFont(fn, 7)
            canvas.setFillColor(colors.HexColor("#5B6B80"))
            canvas.drawString(10 * mm, 8 * mm,
                              "温州神一官方网站 Shenyi official Web-Site: http://www.wzshenyi.com/")
            canvas.drawRightString(A4[0] - 10 * mm, 8 * mm, "联系电话 Tel: +0086 0577 61383976")
            canvas.restoreState()
            return
        # 签章区：固定在下部，左中右三块等距、与页边对称
        W = A4[0]
        left_x, mid_x, right_x = 38 * mm, W / 2, W - 38 * mm
        base_y = 56 * mm
        canvas.setFillColor(colors.HexColor("#5B6B80"))
        canvas.setFont(fn, 8.4)
        canvas.drawCentredString(left_x, base_y + 6.6 * mm, "确认人 Confirmed by")
        canvas.drawCentredString(mid_x, base_y + 6.6 * mm, "邮箱 E-mail")
        canvas.drawCentredString(right_x, base_y + 6.6 * mm, "日期 Date")
        canvas.setFillColor(colors.HexColor("#1F2A3A"))
        canvas.setFont(fn, 10.6)
        canvas.drawCentredString(left_x, base_y, conf or "-")
        canvas.drawCentredString(mid_x, base_y, mail or "-")
        canvas.drawCentredString(right_x, base_y, f"{datetime.date.today():%Y-%m-%d}")
        # 公章
        seal_p2 = _asset("seal.png")
        if seal_p2:
            try:
                sw = 46 * mm
                canvas.drawImage(ImageReader(seal_p2), W - 26 * mm - sw, 12 * mm,
                                 width=sw, height=sw, mask="auto")
            except Exception:
                pass
        # 页脚
        canvas.setStrokeColor(LINE)
        canvas.setLineWidth(0.6)
        canvas.line(10 * mm, 12 * mm, W - 10 * mm, 12 * mm)
        canvas.setFont(fn, 7)
        canvas.setFillColor(colors.HexColor("#5B6B80"))
        canvas.drawString(10 * mm, 8 * mm,
                          "温州神一官方网站 Shenyi official Web-Site: http://www.wzshenyi.com/")
        canvas.drawRightString(W - 10 * mm, 8 * mm, "联系电话 Tel: +0086 0577 61383976")
        canvas.restoreState()

    _outdir = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(_outdir, exist_ok=True)
    tmp_path = os.path.join(_outdir, "_probe_" + str(os.getpid()) + ".pdf")
    probe = SimpleDocTemplate(tmp_path, pagesize=A4,
                              leftMargin=10 * mm, rightMargin=10 * mm,
                              topMargin=9 * mm, bottomMargin=62 * mm)
    probe.build(list(story), onFirstPage=foot, onLaterPages=foot)
    total = probe.page

    doc = SimpleDocTemplate(path, pagesize=A4,
                            leftMargin=10 * mm, rightMargin=10 * mm,
                            topMargin=9 * mm, bottomMargin=62 * mm,
                            title="报价单 Quotation", author="温州神一轴业股份有限公司")
    doc._total_pages = total
    doc.build(story, onFirstPage=foot, onLaterPages=foot)
    try:
        os.remove(tmp_path)
    except Exception:
        pass
    return os.path.exists(path)
