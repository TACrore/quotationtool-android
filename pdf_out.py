# -*- coding: utf-8 -*-
"""报价 PDF 适配层：字段齐全（含确认人/邮箱），复用 Windows reportlab 渲染。"""


def make_quote_pdf(path, cust_code, item, cust_name="", font_path=None):
    try:
        import quote_pdf
    except Exception as e:
        raise RuntimeError("手机端暂不支持生成 PDF（PDF 组件未打包），请用电脑端报价单工具：%s" % e)
    cur = str(item.get("cur") or "RMB").upper()
    confirm = item.get("confirm", "") or ""
    email = item.get("email", "") or ""
    cust = {"code": cust_code, "name": cust_name or "", "cur": cur,
            "owner": item.get("owner", ""), "term": item.get("term", ""),
            "attn": item.get("attn", ""),
            "contact": item.get("contact", "") or item.get("attn", ""),
            "email": email, "addr": item.get("addr", ""),
            "tel": item.get("tel", ""), "confirm": confirm}
    it = dict(item)
    it["remark"] = item.get("remark") or item.get("note") or ""
    it["qty"] = item.get("qty") or ""
    it["part"] = item.get("part") or item.get("no") or ""
    it["attn"] = item.get("attn") or ""
    opts = {"currency": "1" if cur in ("RMB", "") else "2",
            "usd_or_euro": "2" if cur == "EUR" else "1",
            "rate": item.get("rate") or "7.10",
            "taxmode": "both",
            "confirm": confirm,
            "mail": email}
    quote_pdf.build(cust, [it], opts, path)
    return path
