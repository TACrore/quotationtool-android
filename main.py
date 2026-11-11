# -*- coding: utf-8 -*-
"""报价单工具 Android 版（Kivy）— 界面参照 Windows 版"""
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
from kivy.uix.textinput import TextInput

FONT = fontutil.font_path()
INK = (0.12, 0.15, 0.2, 1)
MUTED = (0.42, 0.47, 0.55, 1)
ACCENT = (0.20, 0.45, 0.90, 1)
GREEN = (0.18, 0.60, 0.35, 1)
CARD = (1, 1, 1, 1)
BG = (0.96, 0.97, 0.99, 1)


def log_crash(tag, text):
    for d in (os.environ.get("ANDROID_PRIVATE") or "", appdata.DATA_DIR,
              "/storage/emulated/0/Android/data/cn.wzshenyi.quotationtool/files"):
        try:
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, "crash.log"), "a", encoding="utf-8") as f:
                f.write(f"--- {tag} ---\n{text}\n")
        except Exception:
            continue


class _KeepAlive(ExceptionHandler):
    def handle_exception(self, inst):
        import traceback as tb
        log_crash("uncaught", tb.format_exc())
        return ExceptionManager.PASS


ExceptionManager.add_handler(_KeepAlive())


def paint(widget, color=CARD):
    with widget.canvas.before:
        Color(*color)
        rect = Rectangle(pos=widget.pos, size=widget.size)
    widget.bind(pos=lambda *_: setattr(rect, "pos", widget.pos),
                size=lambda *_: setattr(rect, "size", widget.size))


def L(text="", size=dp(13), color=INK, bold=False, **kw):
    kw.setdefault("halign", "left")
    kw.setdefault("valign", "middle")
    lab = Label(text=text, font_size=size, color=color, bold=bold, **kw)
    if FONT:
        lab.font_name = FONT
    lab.bind(size=lambda w, *_: setattr(w, "text_size", (w.width, None)))
    return lab


def B(text, cb, color=ACCENT, height=dp(42), size=dp(13)):
    b = Button(text=text, size_hint_y=None, height=height, background_color=color,
               font_size=size, on_release=lambda *_: cb())
    if FONT:
        b.font_name = FONT
    return b


def header(title, right=""):
    bar = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(52),
                    padding=(dp(10), 0))
    paint(bar, ACCENT)
    bar.add_widget(L(title, dp(17), (1, 1, 1, 1), True))
    bar.add_widget(L(right, dp(12), (0.92, 0.95, 1, 1), halign="right"))
    return bar


class LoginScreen(Screen):
    def __init__(self, **kw):
        super().__init__(name="login", **kw)
        paint(self, BG)
        root = BoxLayout(orientation="vertical", padding=dp(14), spacing=dp(10))
        root.add_widget(L("登录飞书", dp(20), INK, True))
        root.add_widget(L("点「登录飞书」→ 应用内授权 → 自动登录\n"
                          "（如弹出外部浏览器，复制跳转网址回来即可）", dp(12), MUTED))
        self.code = TextInput(font_name=(FONT or "Roboto"), multiline=False,
                              size_hint_y=None, height=dp(44),
                              hint_text="可手动粘贴回调网址")
        root.add_widget(self.code)
        root.add_widget(B("登录飞书", self.open_auth, ACCENT, dp(56), dp(18)))
        root.add_widget(B("我已复制，登录", self.do_login, GREEN, dp(48), dp(15)))
        root.add_widget(B("测试网络", self.test_net, (0.45, 0.47, 0.5, 1), dp(40)))
        self.tip = L("", dp(12), MUTED)
        root.add_widget(self.tip)
        self.add_widget(root)
        self._tried = ""

    def _say(self, t):
        try:
            self.tip.text = t
        except Exception:
            pass

    def on_pre_enter(self, *a):
        Clock.schedule_interval(self._poll, 1.5)

    def on_leave(self, *a):
        Clock.unschedule(self._poll)

    def _poll(self, *_):
        """回到应用后自动读取剪贴板里的回调 code"""
        try:
            from kivy.core.clipboard import Clipboard
            txt = Clipboard.paste() or ""
        except Exception:
            return
        if "code=" not in txt or txt == self._tried:
            return
        self._tried = txt
        self.code.text = txt
        self._say("已识别剪贴板 code，自动登录…")
        self.do_login()

    def open_auth(self):
        import auth
        import webview_login
        self._say("打开授权页…")
        if webview_login.available():
            def got(code):
                self.code.text = code
                Clock.schedule_once(lambda *_: self.do_login())
            ok = webview_login.open_login(got, lambda msg: Clock.schedule_once(
                lambda *_: self._say(msg)))
            if ok:
                return
        # 桌面端 / WebView 不可用：退回浏览器 + 剪贴板
        url = auth.auth_url()
        try:
            from kivy.core.clipboard import Clipboard
            Clipboard.copy(url)
        except Exception:
            pass
        try:
            import webbrowser
            webbrowser.open(url)
        except Exception:
            pass
        self._say("已打开授权页；同意后复制跳转网址，切回本应用会自动登录")

    def test_net(self):
        import urllib.request
        self._say("测试网络…")

        def work():
            try:
                r = urllib.request.urlopen("https://open.feishu.cn/open-apis/authen/v1/authorize",
                                           timeout=8)
                msg = f"网络 OK（HTTP {r.getcode()}）"
            except Exception as e:  # noqa: BLE001
                msg = f"网络失败：{type(e).__name__}: {str(e)[:80]}"
            Clock.schedule_once(lambda *_: self._say(msg))

        threading.Thread(target=work, daemon=True).start()

    def do_login(self):
        import auth
        self._say("登录中…")

        def work():
            import traceback as tb
            try:
                name = auth.exchange_code(self.code.text, appdata)
                app = App.get_running_app()
                app.me = name or ""
                Clock.schedule_once(lambda *_: self.ok())
            except BaseException as e:  # noqa: BLE001
                log_crash("login", tb.format_exc())
                msg = f"失败：{type(e).__name__}: {str(e)[:160]}"
                Clock.schedule_once(lambda *_: self._say(msg))

        threading.Thread(target=work, daemon=True).start()

    @mainthread
    def ok(self):
        self._say("登录成功")
        self.code.text = ""
        App.get_running_app().sm.current = "home"



class HomeScreen(Screen):
    """首页：账号 + 版本 + 大按钮（风格对齐样品工具）"""

    def __init__(self, **kw):
        super().__init__(name="home", **kw)
        paint(self, BG)
        root = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(12))
        self.who = L("", dp(18), INK, True)
        root.add_widget(self.who)
        root.add_widget(L("报价单工具 · Android", dp(12), MUTED))
        root.add_widget(B("客户报价", self.go_customers, ACCENT, dp(56), dp(18)))
        root.add_widget(B("刷新数据", self.go_customers, GREEN, dp(56), dp(18)))
        root.add_widget(B("账号信息", self.account, (0.35, 0.60, 0.90, 1), dp(48)))
        root.add_widget(BoxLayout())
        root.add_widget(B("退出登录", self.logout, (0.75, 0.30, 0.30, 1), dp(48)))
        self.add_widget(root)

    def on_pre_enter(self, *a):
        app = App.get_running_app()
        self.who.text = "账号：" + (app.me or "未登录")

    def go_customers(self):
        App.get_running_app().sm.current = "customers"

    def account(self):
        app = App.get_running_app()
        Popup(title="账号", content=L(f"账号：{app.me or '未登录'}\n"
                                     f"客户数：{len(app.custs) if hasattr(app,'custs') else 0}",
                                     dp(13), INK), size_hint=(0.8, 0.3)).open()

    def logout(self):
        from kivy.uix.popup import Popup as P2
        Box = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8))
        paint(Box, CARD)

        def do():
            try:
                appdata._save_token({})
            except Exception:
                pass
            App.get_running_app().me = ""
            App.get_running_app().sm.current = "login"

        Box.add_widget(L("确认退出登录？下次需重新授权。", dp(13), INK))
        Box.add_widget(B("确认退出", do, (0.75, 0.30, 0.30, 1), dp(46)))
        pop = P2(title="退出登录", content=Box, size_hint=(0.85, 0.32))
        Box.add_widget(B("取消", pop.dismiss, (0.45, 0.47, 0.5, 1), dp(44)))
        pop.open()


class CustomersScreen(Screen):
    def __init__(self, **kw):
        super().__init__(name="customers", **kw)
        paint(self, BG)
        root = BoxLayout(orientation="vertical")
        self.bar = header("报价单工具", "")
        root.add_widget(self.bar)

        body = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(8))
        row = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(8))
        self.kw = TextInput(font_name=(FONT or "Roboto"), multiline=False,
                            hint_text="搜索客户编号 / 名称")
        row.add_widget(self.kw)
        row.add_widget(B("搜索", self.show_customers, ACCENT, dp(42), dp(12)))
        body.add_widget(row)

        self.count = L("未加载", dp(12), MUTED)
        body.add_widget(self.count)

        self.box = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(6))
        self.box.bind(minimum_height=self.box.setter("height"))
        sv = ScrollView()
        sv.add_widget(self.box)
        body.add_widget(sv)

        bottom = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        bottom.add_widget(B("加载客户", self.load_customers, ACCENT, dp(48)))
        bottom.add_widget(B("刷新", self.load_customers, GREEN, dp(48)))
        bottom.add_widget(B("返回首页", self.account, (0.45, 0.47, 0.5, 1), dp(48)))
        body.add_widget(bottom)
        root.add_widget(body)
        self.add_widget(root)
        self._custs = {}

    def on_pre_enter(self, *a):
        try:
            self.bar.clear_widgets()
            self.bar.add_widget(L("报价单工具", dp(17), (1, 1, 1, 1), True))
            self.bar.add_widget(L("账号：" + (App.get_running_app().me or "未登录"),
                                  dp(12), (0.92, 0.95, 1, 1), halign="right"))
        except Exception:
            pass
        if not self._custs:
            self.load_customers()

    def account(self):
        App.get_running_app().sm.current = "home"

    def load_customers(self):
        self.count.text = "加载中…"

        def work():
            try:
                c = appdata.load_customers()
                Clock.schedule_once(lambda *_: self.fill(c))
            except BaseException as e:  # noqa: BLE001
                Clock.schedule_once(lambda *_: setattr(self.count, "text", "失败：" + str(e)[:120]))

        threading.Thread(target=work, daemon=True).start()

    @mainthread
    def fill(self, custs):
        self._custs = custs or {}
        self.show_customers()

    @mainthread
    def show_customers(self):
        self.box.clear_widgets()
        kw = (self.kw.text or "").strip().lower()
        n = 0
        for code in sorted(self._custs):
            c = self._custs[code]
            blob = f"{code}{c.get('name','')}{c.get('owner','')}".lower()
            if kw and kw not in blob:
                continue
            row = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(58),
                            padding=(dp(10), dp(6)))
            paint(row, CARD)
            row.add_widget(L(f"{code}  {c.get('name','')[:20]}", dp(14), INK, True))
            row.add_widget(L(f"负责人 {c.get('owner','') or '-'}   币种 {c.get('cur','RMB')}"
                             f"   确认人 {c.get('confirm','') or '-'}", dp(11), MUTED))
            btn = Button(background_color=(0, 0, 0, 0), size_hint=(None, None))
            row.add_widget(btn)
            row.bind(on_touch_down=lambda w, t, code=code: self._tap(w, t, code))
            self.box.add_widget(row)
            n += 1
        self.count.text = f"共 {n} 家客户（点一行看报价）"

    def _tap(self, widget, touch, code):
        if widget.collide_point(*touch.pos):
            app = App.get_running_app()
            app.cur_customer = code
            app.sm.current = "quotes"
            return True
        return False


class QuotesScreen(Screen):
    def __init__(self, **kw):
        super().__init__(name="quotes", **kw)
        paint(self, BG)
        root = BoxLayout(orientation="vertical")
        self.bar = header("报价", "")
        root.add_widget(self.bar)

        body = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(8))
        self.info = L("", dp(12), MUTED)
        body.add_widget(self.info)

        row = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(8))
        self.kw = TextInput(font_name=(FONT or "Roboto"), multiline=False,
                            hint_text="搜索图号 / 规格 / 品号")
        row.add_widget(self.kw)
        row.add_widget(B("筛选", self.render, ACCENT, dp(42), dp(12)))
        body.add_widget(row)

        self.box = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(6))
        self.box.bind(minimum_height=self.box.setter("height"))
        sv = ScrollView()
        sv.add_widget(self.box)
        body.add_widget(sv)

        bottom = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        bottom.add_widget(B("生成 PDF", self.make_pdf, GREEN, dp(48)))
        bottom.add_widget(B("返回客户", self.back, (0.45, 0.47, 0.5, 1), dp(48)))
        body.add_widget(bottom)
        root.add_widget(body)
        self.add_widget(root)
        self.items = []

    def back(self):
        App.get_running_app().sm.current = "customers"

    def on_pre_enter(self, *a):
        app = App.get_running_app()
        code = app.cur_customer or ""
        c = appdata.load_customers().get(code, {}) if False else {}
        self.bar.clear_widgets()
        self.bar.add_widget(L("报价 · " + code, dp(16), (1, 1, 1, 1), True))
        self.info.text = "加载中…"

        def work():
            try:
                items = [i for i in appdata.load_items() if i["cust"] == code]
                Clock.schedule_once(lambda *_: self.fill(items))
            except BaseException as e:  # noqa: BLE001
                Clock.schedule_once(lambda *_: setattr(self.info, "text", "失败：" + str(e)[:120]))

        threading.Thread(target=work, daemon=True).start()

    @mainthread
    def fill(self, items):
        self.items = items or []
        App.get_running_app().items_cache = self.items
        self.render()

    @mainthread
    def render(self):
        self.box.clear_widgets()
        kw = (self.kw.text or "").strip().lower()
        n = 0
        for it in self.items:
            blob = f"{it.get('fig','')}{it.get('spec','')}{it.get('part','')}".lower()
            if kw and kw not in blob:
                continue
            row = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(62),
                            padding=(dp(10), dp(5)))
            paint(row, CARD)
            row.add_widget(L(f"{it.get('fig','')}  {it.get('spec','')}", dp(13), INK, True))
            row.add_widget(L(f"{it.get('price','')} {it.get('cur','')}   起订 {it.get('moq','')}"
                             f"   确认 {it.get('confirm','')}", dp(11), MUTED))
            row.bind(on_touch_down=lambda w, t, it=it: self._detail(w, t, it))
            self.box.add_widget(row)
            n += 1
        self.info.text = f"共 {len(self.items)} 条，显示 {n} 条（点一行看详情）"

    def _detail(self, widget, touch, it):
        if not widget.collide_point(*touch.pos):
            return False
        lines = [f"{k}：{it.get(k,'')}" for k in
                 ("date", "cust", "fig", "spec", "part", "price", "moq", "cur",
                  "confirm", "approve")]
        box = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(4))
        paint(box, CARD)
        box.add_widget(L("\n".join(lines), dp(12), INK))
        Popup(title="报价详情", content=box, size_hint=(0.92, 0.7)).open()
        return True

    def make_pdf(self):
        app = App.get_running_app()
        it = self.items[0] if self.items else None
        if not it:
            return self.info.__setattr__("text", "没有可用的报价数据")

        def work():
            try:
                import pdf_out
                outdir = os.path.join(appdata.DATA_DIR, "pdf")
                os.makedirs(outdir, exist_ok=True)
                path = os.path.join(outdir, f"{it.get('fig','quote')}.pdf")
                pdf_out.make_quote_pdf(path, it.get("cust", ""), it, font_path=FONT)
                Clock.schedule_once(lambda *_: self._done(path))
            except BaseException as e:  # noqa: BLE001
                import traceback as tb
                log_crash("pdf", tb.format_exc())
                Clock.schedule_once(lambda *_: setattr(self.info, "text", "PDF 失败：" + str(e)[:120]))

        threading.Thread(target=work, daemon=True).start()

    @mainthread
    def _done(self, path):
        self.info.text = "PDF 已生成：" + path
        Popup(title="已生成", content=L(path, dp(12), INK), size_hint=(0.92, 0.4)).open()


class QuoteApp(App):
    items_cache = []
    me = ""
    cur_customer = ""
    sm = None

    def build(self):
        self.sm = ScreenManager()
        self.sm.add_widget(LoginScreen())
        self.sm.add_widget(HomeScreen())
        self.sm.add_widget(CustomersScreen())
        self.sm.add_widget(QuotesScreen())
        try:
            tok = appdata._load_token() or {}
            self.sm.current = "home" if tok.get("refresh_token") else "login"
        except Exception:
            self.sm.current = "login"
        if os.environ.get("QUOTEAPP_START") == "login":
            self.sm.current = "login"
        return self.sm

    def on_resume(self):
        try:
            if self.sm and self.sm.current == "login":
                self.sm.get_screen("login")._poll()
        except Exception:
            pass

    def on_start(self):
        try:
            tok = appdata._load_token() or {}
            self.me = tok.get("name", "") or ""
        except Exception:
            self.me = ""


if __name__ == "__main__":
    QuoteApp().run()
