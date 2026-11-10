# -*- coding: utf-8 -*-
"""Android 登录：OAuth 授权码（复制回调 code 粘贴）"""
import json
import os
import time
import urllib.parse

API = "https://open.feishu.cn"
CONF_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "feishu_android.json")


def load_app_conf():
    """读打包进 APK 的 app_id / app_secret / redirect_uri"""
    try:
        with open(CONF_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def auth_url():
    c = load_app_conf()
    q = urllib.parse.urlencode({
        "app_id": c.get("app_id", ""),
        "redirect_uri": c.get("redirect_uri", ""),
        "response_type": "code",
        "state": "quoteapp",
    })
    return f"{API}/open-apis/authen/v1/authorize?{q}"


def exchange_code(code, appdata_mod):
    """用 authorization_code 换 user_access_token，写入 token.json"""
    c = load_app_conf()
    code = (code or "").strip()
    if "code=" in code:  # 允许整段回调 URL
        code = urllib.parse.parse_qs(urllib.parse.urlparse(code).query).get("code", [""])[0]
    if not code:
        raise RuntimeError("没有找到 code")
    payload = {
        "grant_type": "authorization_code",
        "client_id": c.get("app_id", ""),
        "client_secret": c.get("app_secret", ""),
        "code": code,
        "redirect_uri": c.get("redirect_uri", ""),
    }
    r = appdata_mod._http("POST", "/open-apis/authen/v2/oauth/token", payload)
    d = r.get("data") or r
    if not d.get("access_token"):
        raise RuntimeError(str(r.get("msg") or r.get("error_description") or r)[:160])
    tok = {
        "user_access_token": d["access_token"],
        "refresh_token": d.get("refresh_token", ""),
        "expire_at": time.time() + int(d.get("expires_in", 7200)),
    }
    appdata_mod._save_token(tok)
    return d.get("refresh_token", "")
