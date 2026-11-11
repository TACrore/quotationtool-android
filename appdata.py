# -*- coding: utf-8 -*-
"""Android 端数据层：飞书 Base 精简客户端（不依赖 tkinter / DPAPI）"""
import json
import os
import time
import urllib.parse
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
    try:
        with open(CONF_FILE, encoding="utf-8") as f:
            conf.update(json.load(f))
    except Exception:
        pass
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
        with urllib.request.urlopen(req, timeout=30, context=_ssl_ctx()) as r:
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
