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
    """用 authorization_code 换 user_access_token；失败抛出可读原因"""
    import json as _json
    import time as _time
    import urllib.error
    import urllib.request

    c = load_app_conf()
    raw = (code or "").strip()
    if "code=" in raw:  # 允许整段回调 URL
        raw = urllib.parse.parse_qs(urllib.parse.urlparse(raw).query).get("code", [""])[0]
    if not raw:
        raise RuntimeError("没找到 code，请粘贴包含 ?code= 的完整回调网址")

    payload = {
        "grant_type": "authorization_code",
        "client_id": c.get("app_id", ""),
        "client_secret": c.get("app_secret", ""),
        "code": raw,
        "redirect_uri": c.get("redirect_uri", ""),
    }
    url = API + "/open-apis/authen/v2/oauth/token"
    last = ""
    for kind in ("json", "form"):
        try:
            if kind == "json":
                body = _json.dumps(payload).encode()
                hdr = {"Content-Type": "application/json; charset=utf-8"}
            else:
                body = urllib.parse.urlencode(payload).encode()
                hdr = {"Content-Type": "application/x-www-form-urlencoded"}
            req = urllib.request.Request(url, data=body, headers=hdr)
            t0 = _time.time()
            with urllib.request.urlopen(req, timeout=12) as r:
                resp = _json.loads(r.read().decode())
            d = resp.get("data") or resp
            if d.get("access_token"):
                appdata_mod._save_token({
                    "user_access_token": d["access_token"],
                    "refresh_token": d.get("refresh_token", ""),
                    "expire_at": _time.time() + int(d.get("expires_in", 7200)),
                })
                return d.get("refresh_token", "")
            last = str(resp)[:200]
        except urllib.error.HTTPError as e:
            try:
                last = e.read().decode()[:200]
            except Exception:
                last = f"HTTP {e.code}"
        except Exception as e:  # noqa: BLE001
            last = f"{type(e).__name__}: {e}"
        print("[auth]", kind, "failed:", last)
    raise RuntimeError(last or "换 token 失败")
