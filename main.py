# -*- coding: utf-8 -*-
"""报价单工具 Android 版（Kivy）— 客户 → 报价 → 出 PDF"""
import os
import threading

import appdata
import fontutil
from kivy.app import App
from kivy.base import ExceptionHandler, ExceptionManager
from kivy.clock import Clock, mainthread
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import Screen, ScreenManager
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput

FONT = fontutil.font_path()



def auth_saved_user():
    try:
        t = appdata._load_token()
        return t.get("name", "") or ""
    except Exception:
        return ""


CRASH_PATHS = [
    os.environ.get("ANDROID_PRIVATE") or "",
    appdata.DATA_DIR,
    "/sdcard/Android/data/cn.wzshenyi.quotationtool/files",
    "/storage/emulated/0/Android/data/cn.wzshenyi.quotationtool/files",
    ".",
]


def log_crash(tag, exc_text):
    line = f"--- {tag} ---\n{exc_text}\n"
    for d in CRASH_PATHS:
        if not d:
            continue
        try:
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, "crash.log"), "a", encoding="utf-8") as f:
                f.write(line)
        except Exception:
            continue


def paint_bg(widget, color=(1, 1, 1, 1)):
    with widget.canvas.before:
        Color(*color)
        rect = Rectangle(pos=widget.pos, size=widget.size)
    widget.bind(pos=lambda *_: setattr(rect, "pos", widget.pos),
                size=lambda *_: setattr(rect, "size", widget.size))


def mk_label(text="", size=dp(14), bold=False, color=(0.1, 0.1, 0.1, 1), **kw):
    kw.setdefault("halign", "left")
    kw.setdefault("valign", "middle")
    lab = Label(text=text, font_size=size, color=color, bold=bold, **kw)
    if FONT:
        lab.font_name = FONT
    lab.bind(size=lambda w, *_: setattr(w, "text_size", (w.width, None)))
    return lab


def mk_button(text, on_press, color=(0.20, 0.45, 0.90, 1), height=dp(46)):
    b = Button(text=text, size_hint_y=None, height=height, background_color=color,
               on_release=lambda *_: on_press())
    if FONT:
        b.font_name = FONT
    return b




class _KeepAlive(ExceptionHandler):
    """把未捕获异常写进 crash.log，尽量不让应用直接退出"""

    def handle_exception(self, inst):
        import traceback as _tb
        try:
            log_crash("uncaught", _tb.format_exc())
        except BaseException:
            pass
        return ExceptionManager.PASS


ExceptionManager.add_handler(_KeepAlive())

class HomeScreen(Screen):
    def __init__(self, **kw):
        super().__init__(name="home", **kw)
        paint_bg(self)
        root = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(8))
        root.add_widget(mk_label("报价单工具", dp(22), True))
        root.add_widget(mk_label("账号：" + (App.get_running_app().me or "未登录"), dp(13)))
        self.list_box = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(6))
        self.list_box.bind(minimum_height=self.list_box.setter("height"))
        sv = ScrollView()
        sv.add_widget(self.list_box)
        root.add_widget(sv)
        row = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
        row.add_widget(mk_button("加载客户", self.load_customers))
        row.add_widget(mk_button("刷新", self.load_customers, (0.30, 0.62, 0.35, 1)))
        row.add_widget(mk_button("登录", self.open_login, (0.45, 0.47, 0.5, 1)))
        root.add_widget(row)
        self.add_widget(root)

    def open_login(self):
        App.get_running_app().sm.current = "login"

    def load_customers(self):
        self.list_box.clear_widgets()
        self.list_box.add_widget(mk_label("加载中…", dp(13)))

        def work():
            try:
                custs = appdata.load_customers()
                self.show_customers(custs)
            except Exception as e:  # noqa: BLE001
                self.show_error(str(e))

        threading.Thread(target=work, daemon=True).start()

    @mainthread
    def show_customers(self, custs):
        self.list_box.clear_widgets()
        if not custs:
            self.list_box.add_widget(mk_label("没有数据（需先登录）", dp(13)))
            return
        for code, c in list(custs.items())[:300]:
            btn = Button(text=f"{code}  {c['name'][:14]}", size_hint_y=None, height=dp(44),
                         background_color=(0.93, 0.95, 0.99, 1), color=(0.1, 0.1, 0.1, 1))
            if FONT:
                btn.font_name = FONT
            btn.bind(on_release=lambda _b, c=code: self.open_customer(c))
            self.list_box.add_widget(btn)

    @mainthread
    def show_error(self, msg):
        self.list_box.clear_widgets()
        self.list_box.add_widget(mk_label("失败：" + msg, dp(13), color=(0.8, 0.1, 0.1, 1)))

    def open_customer(self, code):
        app = App.get_running_app()
        app.cur_customer = code
        app.sm.current = "quotes"



class LoginScreen(Screen):
    """手机端登录：打开飞书授权页 → 复制回调 URL 里的 code 粘贴回来"""

    def __init__(self, **kw):
        super().__init__(name="login", **kw)
        paint_bg(self)
        root = BoxLayout(orientation="vertical", padding=dp(14), spacing=dp(10))
        root.add_widget(mk_label("登录飞书", dp(20), True))
        root.add_widget(mk_label(
            "1) 点下面按钮打开授权页并同意\n"
            "2) 页面跳转后，复制地址栏整段网址\n"
            "3) 粘贴到下面输入框，点登录", dp(12)))
        self.code = TextInput(font_name=(FONT or 'Roboto'), hint_text="粘贴回调网址或 code", multiline=False,
                              size_hint_y=None, height=dp(44))
        root.add_widget(self.code)
        root.add_widget(mk_button("打开授权页", self.open_auth, (0.20, 0.45, 0.90, 1)))
        root.add_widget(mk_button("登录", self.do_login, (0.30, 0.62, 0.35, 1)))
        root.add_widget(mk_button("测试网络", self.test_net, (0.45, 0.47, 0.5, 1)))
        self.tip = mk_label("", dp(12))
        root.add_widget(self.tip)
        self.add_widget(root)

    def open_auth(self):
        import auth
        url = auth.auth_url()
        try:
            from kivy.core.clipboard import Clipboard
            Clipboard.copy(url)
        except Exception:
            pass
        opened = False
        try:
            import webbrowser
            webbrowser.open(url)
            opened = True
        except BaseException:
            pass
        self.tip.text = ("已复制授权链接并尝试打开浏览器" if opened else "已复制授权链接") + \
            "\n请到浏览器打开（或长按粘贴），授权后复制回调网址回来"

    def _say(self, text):
        try:
            self.tip.text = text
        except Exception:
            pass

    def test_net(self):
        import socket
        import urllib.request
        self._say("测试中…")
        socket.setdefaulttimeout(8)

        def work():
            try:
                r = urllib.request.urlopen("https://open.feishu.cn/open-apis/authen/v1/authorize",
                                           timeout=8)
                code = r.getcode()
                msg = f"网络 OK（HTTP {code}）"
            except BaseException as e:  # noqa: BLE001
                import traceback as _tb
                log_crash("nettest", _tb.format_exc())
                msg = f"网络失败：{type(e).__name__}: {str(e)[:80]}"
            Clock.schedule_once(lambda *_: self._say(msg))

        threading.Thread(target=work, daemon=True).start()

    def do_login(self):
        import auth
        self._say("步骤1/3 启动线程…")

        def work():
            import socket
            import traceback as _tb
            socket.setdefaulttimeout(12)
            try:
                Clock.schedule_once(lambda *_: self._say("步骤2/3 请求飞书换 token…"))
                auth.exchange_code(self.code.text, appdata)
                Clock.schedule_once(lambda *_: self._say("步骤3/3 保存登录态…"))
                Clock.schedule_once(lambda *_: self.ok())
            except BaseException as e:  # noqa: BLE001
                log_crash("login", _tb.format_exc())
                msg = f"失败：{type(e).__name__}: {str(e)[:140]}"
                Clock.schedule_once(lambda *_: self._say(msg))

        threading.Thread(target=work, daemon=True).start()

    @mainthread
    def ok(self):
        self.tip.text = "登录成功"
        try:
            App.get_running_app().sm.current = "home"
            app = App.get_running_app()
            app.me = auth_saved_user()
        except BaseException:
            import traceback as _tb
            log_crash("login-ok", _tb.format_exc())


class QuotesScreen(Screen):
    def __init__(self, **kw):
        super().__init__(name="quotes", **kw)
        paint_bg(self)
        root = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(8))
        self.title = mk_label("报价", dp(18), True)
        root.add_widget(self.title)
        self.picker = Spinner(text="选择图号", values=[], size_hint_y=None, height=dp(44))
        if FONT:
            self.picker.font_name = FONT
        root.add_widget(self.picker)
        self.info = mk_label("", dp(13))
        root.add_widget(self.info)
        root.add_widget(mk_button("生成 PDF", self.make_pdf))
        root.add_widget(mk_button("返回客户", self.back, (0.45, 0.47, 0.5, 1)))
        self.add_widget(root)

    def back(self):
        App.get_running_app().sm.current = "home"

    def on_pre_enter(self, *a):
        app = App.get_running_app()
        self.title.text = "报价 · " + (app.cur_customer or "")
        self.info.text = "加载中…"

        def work():
            try:
                items = [i for i in appdata.load_items() if i["cust"] == app.cur_customer]
                Clock.schedule_once(lambda *_: self.fill(items))
            except Exception as e:  # noqa: BLE001
                Clock.schedule_once(lambda *_: setattr(self.info, "text", "失败：" + str(e)))

        threading.Thread(target=work, daemon=True).start()

    @mainthread
    def fill(self, items):
        self.items = items
        App.get_running_app().items_cache = items
        figs = sorted({i["fig"] for i in items})
        self.picker.values = figs
        self.picker.text = figs[0] if figs else "示例图号"
        self.info.text = f"共 {len(items)} 条，{len(figs)} 个图号" if items else "无数据，可生成示例 PDF"

    def make_pdf(self):
        fig = self.picker.text
        app = App.get_running_app()

        def work():
            try:
                path = app.make_pdf(app.cur_customer, fig)
                Clock.schedule_once(lambda *_: self._done(path))
            except Exception as e:  # noqa: BLE001
                Clock.schedule_once(lambda *_: self._err(str(e)))

        threading.Thread(target=work, daemon=True).start()

    @mainthread
    def _done(self, path):
        Popup(title="已生成", content=mk_label(path, dp(12)), size_hint=(0.9, 0.4)).open()

    @mainthread
    def _err(self, msg):
        Popup(title="失败", content=mk_label(msg, dp(12)), size_hint=(0.9, 0.4)).open()


class QuoteApp(App):
    items_cache = []
    me = ""
    cur_customer = ""
    sm = None

    def build(self):
        self.sm = ScreenManager()
        self.sm.add_widget(HomeScreen())
        self.sm.add_widget(LoginScreen())
        self.sm.add_widget(QuotesScreen())
        if os.environ.get("QUOTEAPP_START") == "login":
            self.sm.current = "login"
        else:
            try:
                tok = appdata._load_token() or {}
                self.sm.current = "home" if tok.get("refresh_token") else "login"
            except Exception:
                self.sm.current = "login"
        return self.sm

    def on_start(self):
        try:
            self.me = appdata.load_conf().get("user_name", "")
        except Exception:
            self.me = ""

    def make_pdf(self, cust_code, fig):
        import pdf_out

        item = next((i for i in (self.items_cache or [])
                     if i["cust"] == cust_code and i["fig"] == fig), None)
        if item is None:
            item = {"fig": fig or "SAMPLE-001", "spec": "1.995*50", "price": "0.0245",
                    "cur": "USD", "moq": "600K/M", "date": "2026-11-10", "confirm": "朱超"}

        outdir = os.path.join(appdata.DATA_DIR, "pdf")
        os.makedirs(outdir, exist_ok=True)
        path = os.path.join(outdir, f"{item['fig']}_{cust_code or 'demo'}.pdf")
        pdf_out.make_quote_pdf(path, cust_code or "105B", item, font_path=FONT)
        return path


if __name__ == "__main__":
    QuoteApp().run()
