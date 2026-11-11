# -*- coding: utf-8 -*-
"""Android 端数据层：飞书 Base 精简客户端（不依赖 tkinter / DPAPI）"""
import json
import os
import time
import urllib.parse
import io
import urllib.request

APP_ID = "cli_aa63ec7510fadc02"
APP_SECRET = ""  # 首次运行由 config.json 覆盖
BASE_APP = "Vxd0b4Kxla8AMpsMDIpc4sv6n8d"
T_CUST = "tblZK3rYfHh1SV9h"
T_ITEM = "tbl4IDx3Zd1CxYOk"
T_NOTICE = "tblTXAPehSgHRGAM"
API = "https://open.feishu.cn"
TEMP_PREFIX = "临时-"

def _data_dir():
    cands = []
    try:
        cands.append(app_private)  # noqa: F821  (p4a 注入的私有目录)
    except NameError:
        pass
    cands.append(os.environ.get("ANDROID_PRIVATE") or "")
    cands.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"))
    cands.append(os.path.join(os.path.expanduser("~"), "quoteapp"))
    for c in cands:
        if not c:
            continue
        try:
            os.makedirs(c, exist_ok=True)
            probe = os.path.join(c, ".w")
            with open(probe, "w"):
                pass
            os.remove(probe)
            return c
        except Exception:
            continue
    return os.path.dirname(os.path.abspath(__file__))


DATA_DIR = _data_dir()
TOKEN_FILE = os.path.join(DATA_DIR, "token.json")
CONF_FILE = os.path.join(DATA_DIR, "config.json")



def _ssl_ctx(strict=True):
    """返回 SSL 上下文：优先 certifi 证书链，失败可降级为不校验"""
    import ssl
    if not strict:
        return ssl._create_unverified_context()
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _ensure_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def load_conf():
    _ensure_dir()
    conf = {"app_id": APP_ID, "app_secret": APP_SECRET}
    here = os.path.dirname(os.path.abspath(__file__))
    for path in (CONF_FILE,
                 os.path.join(here, "feishu_android.json"),
                 os.path.join(here, "assets", "feishu_android.json")):
        try:
            with open(path, encoding="utf-8") as f:
                conf.update(json.load(f))
            break
        except Exception:
            continue
    return conf


def save_conf(data):
    _ensure_dir()
    with open(CONF_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


def _load_token():
    try:
        with open(TOKEN_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_token(t):
    _ensure_dir()
    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
        json.dump(t, f)


def _http(method, path, payload=None, token=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        API + path, data=data, method=method,
        headers={"Content-Type": "application/json; charset=utf-8",
                 **({"Authorization": "Bearer " + token} if token else {})})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        body = ""
        try:
            body = e.read().decode(errors="replace")
        except Exception:
            pass
        return {"code": -1, "msg": str(e)[:120] + body[:200]}


def user_token():
    """返回可用的 user_access_token；过期用 refresh_token 续期"""
    t = _load_token()
    tok = t.get("user_access_token") or ""
    if tok and time.time() < float(t.get("expire_at", 0)) - 120:
        return tok
    rt = t.get("refresh_token") or ""
    if not rt:
        raise RuntimeError("未登录")
    conf = load_conf()
    r = _http("POST", "/open-apis/authen/v2/oauth/token", {
        "grant_type": "refresh_token", "client_id": conf["app_id"],
        "client_secret": conf["app_secret"], "refresh_token": rt})
    d = r.get("data") or r
    if not d.get("access_token"):
        raise RuntimeError("刷新失败：" + str(r.get("msg"))[:80])
    t.update({"user_access_token": d["access_token"],
              "refresh_token": d.get("refresh_token", rt),
              "expire_at": time.time() + int(d.get("expires_in", 7200))})
    _save_token(t)
    return t["user_access_token"]


def api(method, path, payload=None):
    return _http(method, path, payload, user_token())


def _txt(v):
    if v is None:
        return ""
    if isinstance(v, list):
        return "".join(_txt(x) for x in v).strip()
    if isinstance(v, dict):
        return str(v.get("text") or v.get("name") or v.get("link") or "").strip()
    return str(v).strip()


def _all(table):
    out, token = [], ""
    while True:
        p = f"/open-apis/bitable/v1/apps/{BASE_APP}/tables/{table}/records?page_size=500"
        if token:
            p += "&page_token=" + token
        d = api("GET", p).get("data") or {}
        out.extend(d.get("items") or [])
        token = d.get("page_token") or ""
        if not d.get("has_more"):
            return out


def load_customers():
    out = {}
    for rec in _all(T_CUST):
        f = rec.get("fields") or {}
        code = _txt(f.get("客户编号"))
        if code:
            out[code] = {"code": code, "name": _txt(f.get("名称")),
                         "owner": _txt(f.get("负责业务员")),
                         "term": _txt(f.get("交易条件")),
                         "confirm": _txt(f.get("报价确认人")),
                         "cur": _txt(f.get("币种")) or "RMB"}
    return out


def load_items():
    out = []
    for rec in _all(T_ITEM):
        f = rec.get("fields") or {}
        fig = _txt(f.get("图号"))
        if not fig:
            continue
        out.append({"row": rec.get("record_id"), "no": _txt(f.get("NO.")), "fig": fig,
                    "spec": _txt(f.get("规格")), "price": _txt(f.get("单价")),
                    "moq": _txt(f.get("起订量")), "cust": _txt(f.get("客户编号")),
                    "date": _txt(f.get("报价日期")), "cur": _txt(f.get("币种")) or "RMB",
                    "confirm": _txt(f.get("报价确认人")),
                    "approve": _txt(f.get("审批状态"))})
    return out


CACHE_TTL = 300


def _cache_path(name):
    return os.path.join(DATA_DIR, "cache_%s.json" % name)


def _cache_get(name, ttl=CACHE_TTL):
    try:
        d = json.load(open(_cache_path(name), encoding="utf-8"))
        if time.time() - float(d.get("ts") or 0) <= ttl:
            return d.get("data")
    except Exception:
        pass
    return None


def _cache_put(name, data):
    try:
        json.dump({"ts": time.time(), "data": data},
                  open(_cache_path(name), "w", encoding="utf-8"), ensure_ascii=False)
    except Exception:
        pass


def _rec_to_item(rec):
    f = rec.get("fields") or {}
    fig = _txt(f.get("图号"))
    if not fig:
        return None
    return {"row": rec.get("record_id"), "no": _txt(f.get("NO.")), "fig": fig,
            "spec": _txt(f.get("规格")), "price": _txt(f.get("单价")),
            "moq": _txt(f.get("起订量")), "cust": _txt(f.get("客户编号")),
            "date": _txt(f.get("报价日期")), "cur": _txt(f.get("币种")) or "RMB",
            "confirm": _txt(f.get("报价确认人")), "approve": _txt(f.get("审批状态"))}


def load_customers(refresh=False):
    if not refresh:
        cached = _cache_get("customers")
        if cached:
            return cached
    out = {}
    for rec in _all(T_CUST):
        f = rec.get("fields") or {}
        code = _txt(f.get("客户编号"))
        if not code:
            continue
        out[code] = {"code": code, "name": _txt(f.get("名称")),
                     "owner": _txt(f.get("负责业务员")), "term": _txt(f.get("交易条件")),
                     "confirm": _txt(f.get("报价确认人")), "cur": _txt(f.get("币种")) or "RMB"}
    _cache_put("customers", out)
    return out


def items_for_customer(code, refresh=False, limit=2000):
    key = "items_" + str(code).replace("/", "_")
    if not refresh:
        cached = _cache_get(key)
        if cached is not None:
            return cached
    out = []
    token = ""
    while True:
        pth = ("/open-apis/bitable/v1/apps/%s/tables/%s/records/search?page_size=500"
               "&automatic_fields=false" % (BASE_APP, T_ITEM))
        if token:
            pth += "&page_token=" + token
        body = {"filter": {"conjunction": "and", "conditions": [
            {"field_name": "客户编号", "operator": "is", "value": [str(code)]}]}}
        r = api("POST", pth, body)
        d = r.get("data") or {}
        for rec in d.get("items") or []:
            it = _rec_to_item(rec)
            if it:
                out.append(it)
        token = d.get("page_token") or ""
        if not d.get("has_more") or not token or len(out) >= limit:
            break
    _cache_put(key, out)
    return out


def load_items(refresh=False):
    if not refresh:
        cached = _cache_get("items_all")
        if cached:
            return cached
    out = []
    for rec in _all(T_ITEM):
        it = _rec_to_item(rec)
        if it:
            out.append(it)
    _cache_put("items_all", out)
    return out


def save_quote(fields, rec_id=""):
    """有 rec_id 就更新，没有就新建。返回 record_id。"""
    body = {"fields": fields}
    if rec_id:
        r = api("PUT", "/open-apis/bitable/v1/apps/%s/tables/%s/records/%s"
                % (BASE_APP, T_ITEM, rec_id), body)
    else:
        r = api("POST", "/open-apis/bitable/v1/apps/%s/tables/%s/records"
                % (BASE_APP, T_ITEM), body)
    if r.get("code") not in (0, None):
        raise RuntimeError(str(r.get("msg") or r.get("code"))[:120])
    rid = rec_id or ((r.get("data") or {}).get("record") or {}).get("record_id", "")
    _clear_cache()
    return rid


def save_customer(code, fields, rec_id=""):
    fields = dict(fields)
    fields["客户编号"] = code
    body = {"fields": fields}
    if rec_id:
        r = api("PUT", "/open-apis/bitable/v1/apps/%s/tables/%s/records/%s"
                % (BASE_APP, T_CUST, rec_id), body)
    else:
        r = api("POST", "/open-apis/bitable/v1/apps/%s/tables/%s/records"
                % (BASE_APP, T_CUST), body)
    if r.get("code") not in (0, None):
        raise RuntimeError(str(r.get("msg") or r.get("code"))[:120])
    _clear_cache()
    return rec_id or ((r.get("data") or {}).get("record") or {}).get("record_id", "")


def _clear_cache():
    try:
        for fn in os.listdir(DATA_DIR):
            if fn.startswith("cache_"):
                os.remove(os.path.join(DATA_DIR, fn))
    except Exception:
        pass


ADMIN_NAME = "朱超"
REVIEWER_NAMES = ("侯梦梦", "潘齐千")
T_APPROVAL = "tblN5cbVhLjaO1EC"


def me():
    try:
        return (_load_token() or {}).get("name", "") or ""
    except Exception:
        return ""


def is_admin():
    return me() == ADMIN_NAME


def is_reviewer():
    return me() in REVIEWER_NAMES


def can_approve():
    return is_admin() or is_reviewer()


def append_approval(quote, action, status, note="", rec_id=""):
    """写一条审批记录。quote: 报价 dict（含 fig/cust/spec/price/no）。"""
    fields = {"时间": time.strftime("%Y-%m-%d %H:%M"), "动作": action, "状态": status,
              "NO.": quote.get("no", ""), "图号": quote.get("fig", ""),
              "客户编号": quote.get("cust", ""), "规格": quote.get("spec", ""),
              "单价": str(quote.get("price", "")), "发起人": quote.get("starter") or me(),
              "审批人": quote.get("approver") or me(),
              "报价记录ID": rec_id or quote.get("row", ""), "备注": note or ""}
    r = api("POST", "/open-apis/bitable/v1/apps/%s/tables/%s/records"
            % (BASE_APP, T_APPROVAL), {"fields": fields})
    if r.get("code") not in (0, None):
        raise RuntimeError(str(r.get("msg") or r.get("code"))[:120])
    return True


def decide_quote(rec_id, quote, approve, note=""):
    """审单员通过/驳回。"""
    status = "通过" if approve else "驳回"
    fields = {"审批状态": status, "审批人": me(),
              "审批时间": time.strftime("%Y-%m-%d %H:%M")}
    r = api("PUT", "/open-apis/bitable/v1/apps/%s/tables/%s/records/%s"
            % (BASE_APP, T_ITEM, rec_id), {"fields": fields})
    if r.get("code") not in (0, None):
        raise RuntimeError(str(r.get("msg") or r.get("code"))[:120])
    q = dict(quote)
    q["approver"] = me()
    append_approval(q, "审批", status, note, rec_id)
    _clear_cache()
    return status


def quote_status_fields():
    """新建/修改报价时该带的审批字段。"""
    fields = {"发起人": me()}
    if can_approve():
        fields["审批状态"] = "通过"
        fields["审批人"] = me()
        fields["审批时间"] = time.strftime("%Y-%m-%d %H:%M")
    else:
        fields["审批状态"] = "待审核"
        fields["审批人"] = ""
    return fields


def upload_attachment(data, name):
    """上传附件到 Base，返回 file_token（用于 附件文件 字段）。"""
    import uuid
    boundary = "----dsh" + uuid.uuid4().hex
    body = io.BytesIO()

    def field(k, v):
        body.write(("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n"
                    % (boundary, k, v)).encode())

    def ff(k, fn, payload):
        body.write(("--%s\r\nContent-Disposition: form-data; name=\"%s\"; filename=\"%s\"\r\n"
                    "Content-Type: application/octet-stream\r\n\r\n"
                    % (boundary, k, fn)).encode("utf-8"))
        body.write(payload)
        body.write(b"\r\n")

    field("file_name", name)
    field("parent_type", "bitable_file")
    field("parent_node", BASE_APP)
    field("size", str(len(data)))
    ff("file", name, data)
    body.write(("--%s--\r\n" % boundary).encode())
    req = urllib.request.Request(
        API + "/open-apis/drive/v1/medias/upload_all", data=body.getvalue(), method="POST",
        headers={"Authorization": "Bearer " + user_token(),
                 "Content-Type": "multipart/form-data; boundary=" + boundary})
    with urllib.request.urlopen(req, timeout=300) as r:
        d = json.loads(r.read().decode())
    if d.get("code") != 0:
        raise RuntimeError(str(d.get("msg"))[:120])
    return (d.get("data") or {}).get("file_token", "")
