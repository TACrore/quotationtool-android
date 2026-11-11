# -*- coding: utf-8 -*-
"""Android 登录：OAuth 授权码（复制回调 code 粘贴）"""
import json
import os
import time
import urllib.parse

API = "https://open.feishu.cn"
CONF_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "feishu_android.json")



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
    """用授权码换 user_access_token；错误信息尽量原文返回"""
    import json as _json
    import time as _time
    import urllib.error
    import urllib.request

    c = load_app_conf()
    raw = (code or "").strip()
    if "code=" in raw:
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

    def _post(strict_ssl=True):
        body = _json.dumps(payload).encode()
        hdr = {"Content-Type": "application/json; charset=utf-8"}
        req = urllib.request.Request(url, data=body, headers=hdr)
        with urllib.request.urlopen(req, timeout=15,
                                    context=_ssl_ctx(strict_ssl)) as r:
            return _json.loads(r.read().decode())

    resp, err = None, ""
    try:
        resp = _post(True)
    except urllib.error.HTTPError as e:
        try:
            err = e.read().decode()[:300]
        except Exception:
            err = f"HTTP {e.code}"
    except Exception as e:  # noqa: BLE001  (含 SSL 自签)
        err = f"{type(e).__name__}: {e}"
        print("[auth] strict ssl failed:", err[:120], "→ retry unverified")
        try:
            resp = _post(False)
            err = ""
        except urllib.error.HTTPError as e2:
            try:
                err = e2.read().decode()[:300]
            except Exception:
                err = f"HTTP {e2.code}"
        except Exception as e2:  # noqa: BLE001
            err = f"{type(e2).__name__}: {e2}"

    if resp is None:
        raise RuntimeError(err or "请求失败")
    d = resp.get("data") or resp
    if not d.get("access_token"):
        raise RuntimeError(str(resp)[:300])
    appdata_mod._save_token({
        "user_access_token": d["access_token"],
        "refresh_token": d.get("refresh_token", ""),
        "expire_at": _time.time() + int(d.get("expires_in", 7200)),
    })
    print("[auth] login ok")
    return d.get("refresh_token", "")
