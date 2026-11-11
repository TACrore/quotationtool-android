# -*- coding: utf-8 -*-
"""应用内 WebView 登录：授权完成后自动截获 code，无需复制粘贴（仅 Android）"""
import os


def available():
    try:
        from jnius import autoclass  # noqa: F401
        return bool(os.environ.get("ANDROID_PRIVATE")
                    or os.environ.get("ANDROID_APP_PATH")
                    or os.path.exists("/system/build.prop"))
    except Exception:
        return False


def open_login(on_code, on_error=None, redirect_host="example.com"):
    """弹出全屏 WebView 打开飞书授权页；命中 redirect 时回调 on_code(code)"""
    if not available():
        if on_error:
            on_error("当前环境不支持内置浏览器")
        return False
    try:
        from android.runnable import run_on_ui_thread
        from jnius import PythonJavaClass, autoclass, java_method
    except Exception as e:  # noqa: BLE001
        if on_error:
            on_error(f"WebView 不可用：{e}")
        return False

    import auth

    WebView = autoclass("android.webkit.WebView")
    WebViewClient = autoclass("android.webkit.WebViewClient")
    Activity = autoclass("org.kivy.android.PythonActivity")
    LayoutParams = autoclass("android.view.ViewGroup$LayoutParams")
    LinearLayout = autoclass("android.widget.LinearLayout")
    activity = Activity.mActivity

    state = {"view": None, "done": False}

    def _parse(url):
        if "code=" not in url:
            return ""
        return url.split("code=", 1)[1].split("&", 1)[0]

    class _Client(PythonJavaClass):
        __javainterfaces__ = ["android/webkit/WebViewClient"]
        __javacontext__ = "app"

        @java_method("(Landroid/webkit/WebView;Ljava/lang/String;)Z")
        def shouldOverrideUrlLoading(self, view, url):
            if state["done"]:
                return True
            if redirect_host in (url or ""):
                code = _parse(url)
                state["done"] = True
                _close()
                if code:
                    on_code(code)
                elif on_error:
                    on_error("回调里没有 code")
            return True

        @java_method("(Landroid/webkit/WebView;Landroid/graphics/Bitmap;)V")
        def onPageStarted(self, view, url):  # noqa: N802
            if state["done"]:
                return
            if redirect_host in (url or ""):
                code = _parse(url)
                state["done"] = True
                _close()
                if code:
                    on_code(code)
                elif on_error:
                    on_error("回调里没有 code")

    @run_on_ui_thread
    def _show():
        try:
            view = WebView(activity)
            view.getSettings().setJavaScriptEnabled(True)
            view.getSettings().setDomStorageEnabled(True)
            view.setWebViewClient(_Client())
            view.loadUrl(auth.auth_url())
            activity.addContentView(view, LayoutParams(-1, -1))
            state["view"] = view
        except Exception as e:  # noqa: BLE001
            if on_error:
                on_error(f"打开内置浏览器失败：{e}")

    @run_on_ui_thread
    def _close():
        try:
            v = state["view"]
            if v is not None and v.getParent() is not None:
                v.getParent().removeView(v)
            state["view"] = None
        except Exception:
            pass

    _show()
    return True
