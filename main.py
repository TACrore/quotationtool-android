# -*- coding: utf-8 -*-
"""报价单工具 Android 版（Kivy）— 客户 → 报价 → PDF

UI 对齐 Windows 报价单：蓝色顶栏 / 白卡片 / 灰底 / 圆角列表。
"""
import datetime
import os
import sys
import threading

import appdata
import auth
import datepicker_ui
import dialog
import fontutil
import pdf_out
from kivy.app import App
from kivy.base import ExceptionHandler, ExceptionManager
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.screenmanager import Screen, ScreenManager, SlideTransition
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget

APP_VERSION = "1.6.15"
try:
    _base = (os.path.dirname(sys.executable) if getattr(sys, "frozen", False)
             else os.path.dirname(os.path.abspath(__file__)))
    _vo = os.path.join(_base, "version_override.txt")
    if os.path.exists(_vo):
        APP_VERSION = open(_vo, encoding="utf-8").read().strip() or APP_VERSION
except Exception:
    pass
FONT = fontutil.font_path()

BLUE = dialog.BLUE
BLUE_D = dialog.BLUE_D
BG = (0.961, 0.969, 0.984, 1)
CARD = (1, 1, 1, 1)
INK = (0.122, 0.165, 0.227, 1)
MUTED = (0.420, 0.463, 0.525, 1)
GREY = (0.945, 0.953, 0.969, 1)
GREEN = (0.216, 0.698, 0.302, 1)
RED = (0.788, 0.165, 0.165, 1)


def font(w):
    if FONT:
        w.font_name = FONT
    return w


def lab(text="", size=14, color=INK, bold=False, height=None, halign="left"):
    h = height if height is not None else sp(size) * 1.6
    w = Label(text=text, font_size=sp(size), color=color, bold=bold, halign=halign,
              valign="middle", size_hint_y=None, height=h, shorten=True, shorten_from="right")
    w.bind(size=lambda x, *_: setattr(x, "text_size", (x.width, None)))
    return font(w)


def btn(text, cb, color=BLUE, height=44, size=14, text_color=(1, 1, 1, 1)):
    b = Button(text=text, size_hint_y=None, height=dp(height), background_normal="",
               background_color=color, font_size=sp(size), color=text_color,
               on_release=lambda *_: cb())
    return font(b)


def flat(text, cb, color=GREY, text_color=INK, height=38, size=13):
    return btn(text, cb, color=color, height=height, size=size, text_color=text_color)


def card(padding=10, spacing=4):
    from kivy.graphics import Color, RoundedRectangle

    class Card(BoxLayout):
        def __init__(self, **kw):
            super().__init__(**kw)
            with self.canvas.before:
                self._c = Color(rgba=CARD)
                self._r = RoundedRectangle(radius=[dp(6)])
                Color(rgba=(0.88, 0.90, 0.94, 1))
            self.bind(pos=self._sync, size=self._sync)

        def _sync(self, *a):
            self._r.pos = self.pos
            self._r.size = self.size

    return Card(orientation="vertical", size_hint_y=None, padding=[dp(padding)] * 2,
                spacing=dp(spacing))


class Header(BoxLayout):
    def __init__(self, title, right="", **kw):
        super().__init__(size_hint_y=None, height=dp(56), padding=[dp(14), 0],
                         spacing=dp(8), **kw)
        from kivy.graphics import Color, Rectangle
        with self.canvas.before:
            self._c = Color(rgba=BLUE)
            self._r = Rectangle()
        self.bind(pos=self._sync, size=self._sync)
        self.add_widget(lab(title, 18, (1, 1, 1, 1), True))
        self.right_lab = lab(right, 12, (0.85, 0.90, 0.98, 1), halign="right")
        self.add_widget(self.right_lab)

    def _sync(self, *a):
        self._r.pos = self.pos
        self._r.size = self.size


def bg(work, done):
    def run():
        try:
            res = work()
            Clock.schedule_once(lambda *_: done(res, None), 0)
        except BaseException as e:  # noqa: BLE001
            import traceback as tb
            _log_crash("bg", tb.format_exc())
            Clock.schedule_once(lambda *_: done(None, str(e)[:200]), 0)
    threading.Thread(target=run, daemon=True).start()


def _log_crash(tag, text):
    try:
        fn = getattr(appdata, "log_crash", None)
        if fn:
            fn(tag, text)
            return
    except Exception:
        pass
    try:
        import os as _os
        with open(_os.path.join(appdata._data_dir(), "crash.log"), "a",
                  encoding="utf-8") as f:
            f.write("== %s\n%s\n" % (tag, text))
    except Exception:
        pass


class _KeepAlive(ExceptionHandler):
    def handle_exception(self, inst):
        import traceback as tb
        _log_crash("uncaught", tb.format_exc())
        return ExceptionManager.PASS


ExceptionManager.add_handler(_KeepAlive())


class LoginScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        root = BoxLayout(orientation="vertical")
        root.add_widget(Header("报价单工具", "V" + APP_VERSION))
        body = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(10))
        c = card(padding=14, spacing=6)
        c.height = dp(104)
        c.add_widget(lab("飞书账号登录", 16, INK, True))
        c.add_widget(lab("点「打开授权页」→ 飞书同意 → 回到本页自动识别剪贴板里的回调地址。", 12, MUTED))
        body.add_widget(c)
        body.add_widget(btn("打开授权页", self.open_url, height=46, size=15))
        self.code = TextInput(hint_text="粘贴回调网址 / code", multiline=False,
                              size_hint_y=None, height=dp(40), font_size=sp(13),
                              padding=[dp(8), dp(10)])
        font(self.code)
        body.add_widget(self.code)
        body.add_widget(btn("登录", self.do_login, color=GREEN, height=46, size=15))
        self.tip = lab("", 12, MUTED)
        body.add_widget(self.tip)
        body.add_widget(Widget())
        root.add_widget(body)
        self.add_widget(root)
        self._tried = ""
        Clock.schedule_interval(self._poll, 1.5)

    def _auto_code(self, code):
        if not code:
            return
        self.code.text = code
        self.tip.text = "已自动收到授权码，正在登录…"
        self.do_login()

    def open_url(self):
        import webbrowser
        url = auth.auth_url()
        try:
            auth.start_callback(lambda c: Clock.schedule_once(lambda *_: self._auto_code(c), 0))
        except Exception:
            pass
        try:
            from kivy.core.clipboard import Clipboard
            Clipboard.copy(url)
            self.tip.text = "授权链接已复制。没自动打开浏览器就粘贴到浏览器地址栏。"
        except Exception:
            self.tip.text = "打开下面这段链接（长按/选中复制）"
        try:
            if hasattr(self, "url_box"):
                self.url_box.text = url
        except Exception:
            pass
        try:
            webbrowser.open(url)
        except Exception:
            pass

    def _poll(self, *_):
        try:
            from kivy.core.clipboard import Clipboard
            txt = Clipboard.paste() or ""
        except Exception:
            return
        if "code=" in txt and txt != self._tried:
            self._tried = txt
            self.code.text = txt
            self.tip.text = "已识别剪贴板 code，自动登录…"
            self.do_login()

    def do_login(self):
        self.tip.text = "登录中…"

        def check():
            try:
                cs = appdata.load_customers(refresh=True)
                return len(cs)
            except BaseException as e:
                return "ERR:" + str(e)[:120]

        def done(_res, err):
            if err:
                self.tip.text = "失败：" + err
                return
            try:
                auth.stop_callback()
            except Exception:
                pass

            try:
                appdata.READ_AS_APP["on"] = (appdata.me() == "朱超")
            except Exception:
                pass

            def after(n, e2):
                if e2:
                    self.tip.text = "登录成功，但读客户失败：" + e2
                    return
                if isinstance(n, str) and n.startswith("ERR:"):
                    self.tip.text = "登录成功，但读客户失败：" + n[4:]
                    return
                self.tip.text = "登录成功，共 %s 家客户" % n
                self.manager.current = "customers"

            bg(check, after)

        bg(lambda: auth.exchange_code(self.code.text, appdata), done)




class HomeScreen(Screen):
    """登录后首页：与样品 APK 同样式"""

    def __init__(self, **kw):
        super().__init__(**kw)
        root = BoxLayout(orientation="vertical")
        root.add_widget(Header("报价单工具", "V" + APP_VERSION))
        body = BoxLayout(orientation="vertical", padding=[dp(14), dp(12)], spacing=dp(10))

        c = card(padding=14, spacing=4)
        c.height = dp(92)
        self.who = lab("账号：", 18, INK, True)
        c.add_widget(self.who)
        c.add_widget(lab("手机端 V%s ｜ 与电脑端数据实时同步" % APP_VERSION, 12, MUTED))
        body.add_widget(c)

        body.add_widget(btn("客户报价", self.go_customers, height=56, size=18))
        body.add_widget(btn("在线更新", check_apk_update, color=(0.35, 0.60, 0.90, 1),
                            height=52, size=16))
        body.add_widget(Widget())
        body.add_widget(btn("退出登录", self.logout, color=RED, height=52, size=16))
        root.add_widget(body)
        self.add_widget(root)

    def on_pre_enter(self, *_):
        try:
            self.who.text = "账号：" + (appdata.me() or "未登录")
        except Exception:
            pass

    def go_customers(self):
        self.manager.current = "customers"

    def about(self):
        dialog.info("报价单工具 V%s\n飞书 Base 实时同步\n新建/编辑报价、附件、审批、PDF" % APP_VERSION,
                    "关于")

    def logout(self):
        def yes():
            try:
                appdata._save_token({})
            except Exception:
                pass
            self.manager.current = "login"

        dialog.confirm("退出后需要重新授权，确定？", yes, "退出登录", "退出")

class CustomersScreen(Screen):

    def _back_home(self, w, touch):
        if w.collide_point(*touch.pos):
            self.manager.current = "home"
            return True
        return False

    def __init__(self, **kw):
        super().__init__(**kw)
        self.items = {}
        root = BoxLayout(orientation="vertical")
        self.header = Header("客户报价", "← 返回")
        self.header.right_lab.bind(on_touch_down=self._back_home)
        root.add_widget(self.header)
        bar = BoxLayout(size_hint_y=None, height=dp(48), padding=[dp(8), dp(6)], spacing=dp(6))
        self.kw = TextInput(hint_text="客户编号 / 名称 / 业务员", multiline=False,
                            size_hint_y=None, height=dp(36), font_size=sp(13),
                            padding=[dp(8), dp(9)])
        font(self.kw)
        self.kw.bind(on_text_validate=lambda *_: self.render())
        bar.add_widget(self.kw)
        bar.add_widget(flat("搜索", self.render, color=BLUE, text_color=(1, 1, 1, 1), height=36))
        bar.add_widget(flat("刷新", self.reload, color=GREEN, text_color=(1, 1, 1, 1), height=36))

        bar.add_widget(flat("新增客户", lambda: (self.manager.get_screen("customerform").show(),
                                              setattr(self.manager, "current", "customerform")),
                            color=(0.90, 0.55, 0.15, 1), text_color=(1, 1, 1, 1), height=36))
        root.add_widget(bar)
        self.count = lab("", 13, (0.35, 0.40, 0.47, 1), False)
        root.add_widget(self.count)
        self.scroll = ScrollView(bar_width=dp(3))
        self.box = GridLayout(cols=1, spacing=dp(6), size_hint_y=None, padding=[dp(8), dp(4)])
        self.box.bind(minimum_height=self.box.setter("height"))
        self.scroll.add_widget(self.box)
        root.add_widget(self.scroll)
        self.add_widget(root)

    def on_pre_enter(self, *_):
        if not self.items:
            self.reload()

    def reload(self):
        self.count.text = "加载中…"
        self.box.clear_widgets()
        self.box.add_widget(lab("正在读取飞书 Base…", 13, MUTED))

        def done(res, err):
            self.box.clear_widgets()
            if err:
                self.count.text = "失败"
                self.box.add_widget(lab("读取失败：" + err, 13, RED))
                return
            self.items = res or {}
            self.render()

        bg(appdata.load_customers, done)

    def render(self):
        kw = (self.kw.text or "").strip().upper()
        rows = [c for c in self.items.values()
                if not kw or kw in ("%s %s %s" % (c["code"], c["name"], c["owner"])).upper()]
        rows.sort(key=lambda c: c["code"])
        self.count.text = "   %d 家客户（显示前 80 家，输入关键字缩小范围）" % len(rows)
        self.box.clear_widgets()
        if len(rows) > 80:
            self.count.text += "（显示前 80 家，输入关键字缩小范围）"
        for c in rows[:80]:
            cc = card(padding=10, spacing=2)
            cc.height = dp(58)
            cc.add_widget(lab("%s   %s" % (c["code"], c["name"]), 15, INK, True))
            cc.add_widget(lab("业务员 %s ｜ %s ｜ %s" % (c["owner"] or "-", c["cur"],
                                                     c["term"] or "-"), 12, MUTED))
            cc.bind(on_touch_down=lambda w, t, code=c["code"]: self._tap(w, t, code))
            self.box.add_widget(cc)

    def _tap(self, w, touch, code):
        if w.collide_point(*touch.pos):
            self.manager.get_screen("quotes").set_customer(code, self.items.get(code, {}))
            self.manager.current = "quotes"
            return True
        return False


class QuotesScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.code = ""
        self.cust = {}
        self.items = []
        root = BoxLayout(orientation="vertical")
        self.header = Header("报价", "")
        root.add_widget(self.header)
        bar = BoxLayout(size_hint_y=None, height=dp(46), padding=[dp(8), dp(6)], spacing=dp(6))
        bar.add_widget(flat("←", lambda: setattr(self.manager, "current", "customers"),
                            height=34, size=16))
        self.title = lab("", 14, INK, True)
        bar.add_widget(self.title)
        root.add_widget(bar)
        self.sub = lab("", 12, MUTED)
        root.add_widget(self.sub)
        srow = BoxLayout(size_hint_y=None, height=dp(44), padding=[dp(8), 0], spacing=dp(6))
        self.kw = TextInput(hint_text="图号 / 规格 / 品号", multiline=False,
                            size_hint_y=None, height=dp(36), font_size=sp(13),
                            padding=[dp(8), dp(9)])
        font(self.kw)
        self.kw.bind(on_text_validate=lambda *_: self.render())
        srow.add_widget(self.kw)
        srow.add_widget(flat("筛选", self.render, color=BLUE, text_color=(1, 1, 1, 1), height=36))
        srow.add_widget(flat("新建报价", self.new_quote, color=GREEN,
                             text_color=(1, 1, 1, 1), height=36))
        srow.add_widget(flat("批量添加", self.batch_add, color=(0.90, 0.55, 0.15, 1),
                             text_color=(1, 1, 1, 1), height=36))
        root.add_widget(srow)
        self.scroll = ScrollView(bar_width=dp(3))
        self.box = GridLayout(cols=1, spacing=dp(6), size_hint_y=None, padding=[dp(8), dp(4)])
        self.box.bind(minimum_height=self.box.setter("height"))
        self.scroll.add_widget(self.box)
        root.add_widget(self.scroll)
        self.add_widget(root)

    def set_customer(self, code, cust):
        self.code = code
        self.cust = cust or {}
        self.title.text = "%s  %s" % (code, self.cust.get("name", ""))
        self.sub.text = "业务员 %s ｜ 币种 %s ｜ 交易条件 %s" % (
            self.cust.get("owner") or "-", self.cust.get("cur") or "RMB",
            self.cust.get("term") or "-")
        self.items = []
        self.load()

    def load(self):
        self.box.clear_widgets()
        self.box.add_widget(lab("读取报价…", 13, MUTED))

        def done(res, err):
            self.box.clear_widgets()
            if err:
                self.box.add_widget(lab("失败：" + err, 13, RED))
                return
            self.items = res or []
            self.render()

        bg(lambda: appdata.items_for_customer(self.code), done)

    def render(self):
        kw = (self.kw.text or "").strip().upper()
        rows = [x for x in self.items
                if not kw or kw in ("%s %s %s" % (x["fig"], x["spec"], x.get("part", ""))).upper()]
        rows.sort(key=lambda x: (str(x.get("date") or ""), str(x.get("fig") or "")), reverse=True)
        self.box.clear_widgets()
        if not rows:
            self.box.add_widget(lab("该客户没有报价记录", 13, MUTED))
            return
        for it in rows:
            c = card(padding=10, spacing=2)
            c.height = dp(64)
            line = BoxLayout(size_hint_y=None, height=dp(24))
            line.add_widget(lab(it["fig"], 15, INK, True))
            line.add_widget(lab("%s %s" % (it["price"], it["cur"]), 13, BLUE_D, True,
                                halign="right"))
            c.add_widget(line)
            c.add_widget(lab("%s ｜ %s ｜ MOQ %s ｜ %s" % (
                it["spec"], it["date"], it["moq"] or "-", it["confirm"] or "-"), 12, MUTED))
            c.bind(on_touch_down=lambda w, t, item=it: self._tap(w, t, item))
            self.box.add_widget(c)

    def _tap(self, w, touch, item):
        if w.collide_point(*touch.pos):
            self._detail = QuoteDetail(self.code, self.cust, item, on_edit=self.edit_quote)
            self._detail.open()
            return True
        return False

    def batch_add(self):
        sh = dialog.Sheet("批量添加报价", height=0.7)
        sh.body.add_widget(dialog.lab(
            "每行一条：图号 规格 品号 单价 起订量（空格或 Tab 分隔），自动按当前客户+今天日期保存",
            11, dialog.MUTED))
        ti = TextInput(text="", multiline=True, font_size=sp(12))
        font(ti)
        sh.body.add_widget(ti)

        def go():
            sh.dismiss()
            lines = [ln.strip() for ln in ti.text.splitlines() if ln.strip()]
            if not lines:
                dialog.info("没有内容")
                return

            def work():
                ok = 0
                for ln in lines:
                    parts = ln.replace("\t", " ").split()
                    if len(parts) < 2:
                        continue
                    fig = parts[0]
                    spec = parts[1]
                    part = parts[2] if len(parts) > 2 else ""
                    price = parts[3] if len(parts) > 3 else ""
                    moq = parts[4] if len(parts) > 4 else ""
                    fields = {"客户编号": self.code, "图号": fig, "规格": spec,
                              "品号": part, "单价": price, "起订量": moq,
                              "币种": (self.cust or {}).get("cur") or "RMB",
                              "报价日期": datetime.date.today().strftime("%Y-%m-%d")}
                    fields.update(appdata.quote_status_fields(is_new=True))
                    appdata.save_quote(fields, "")
                    ok += 1
                return ok

            def done(n, err):
                if err:
                    dialog.info("批量添加失败：" + err)
                    return
                dialog.info("已添加 %s 条" % n)
                self.load()

            bg(work, done)

        foot = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        foot.add_widget(dialog.btn("取消", lambda *_: sh.dismiss(), color=dialog.GREY,
                                   text_color=dialog.INK))
        foot.add_widget(dialog.btn("保存", go, color=dialog.GREEN))
        sh.body.add_widget(foot)
        sh.open()

    def new_quote(self):
        self.manager.get_screen("quoteform").show(self.code, self.cust, None)
        self.manager.current = "quoteform"

    def edit_quote(self, item):
        self.manager.get_screen("quoteform").show(self.code, self.cust, item)
        self.manager.current = "quoteform"


class QuoteDetail(dialog.Sheet):
    def __init__(self, code, cust, item, on_edit=None):
        super().__init__("报价详情", height=0.72)
        self.code, self.cust, self.item = code, cust, item

        def row(k, v):
            b = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(6))
            kl = dialog.lab(k, 12, dialog.MUTED)
            kl.size_hint_x = 0.28
            txt = str(v) if str(v).strip() not in ("", "-") else "-"
            vl = dialog.lab(txt, 12, dialog.INK)
            vl.size_hint_x = 0.72
            try:
                vl.text_size = (None, None)
                vl.shorten = True
                vl.shorten_from = "right"
            except Exception:
                pass
            b.add_widget(kl)
            b.add_widget(vl)
            return b

        body = BoxLayout(orientation="vertical", spacing=dp(2), size_hint_y=None)
        body.bind(minimum_height=body.setter("height"))
        body.add_widget(row("图号", item.get("fig")))
        body.add_widget(row("规格", item.get("spec")))
        body.add_widget(row("品号/品名", item.get("part")))
        body.add_widget(row("单价", "%s %s" % (item.get("price"), item.get("cur"))))
        body.add_widget(row("起订量", item.get("moq")))
        body.add_widget(row("报价日期", item.get("date")))
        body.add_widget(row("报价确认人", item.get("confirm")))
        body.add_widget(row("邮箱", item.get("email")))
        body.add_widget(row("审批", item.get("approve")))
        body.add_widget(row("客户", "%s %s" % (code, (cust or {}).get("name", ""))))
        self.body.add_widget(body)

        self.tip = dialog.lab("", 12, dialog.MUTED)
        self.body.add_widget(self.tip)

        status = (item.get("approve") or "").strip()
        if status:
            self.body.add_widget(dialog.lab("审批状态：" + status, 12, dialog.MUTED,
                                            height=dp(22)))

        foot = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        foot.add_widget(dialog.btn("关闭", lambda *_: self.dismiss(), color=dialog.GREY,
                                   text_color=dialog.INK))
        if on_edit:
            foot.add_widget(dialog.btn("编辑", lambda *_: (self.dismiss(), on_edit(item)),
                                       color=(0.90, 0.55, 0.15, 1)))
        foot.add_widget(dialog.btn("生成 PDF", self.make_pdf, color=dialog.BLUE))
        foot.add_widget(dialog.btn("删除", self._delete, color=dialog.RED))
        self.body.add_widget(foot)

    def _delete(self):
        def yes():
            def work():
                return appdata.delete_quote(self.item.get("row", ""))

            def done(res, err):
                if err:
                    dialog.info("删除失败：" + err)
                    return
                self.dismiss()
                dialog.info("已删除")

            bg(work, done)

        dialog.confirm("删除这条报价？\n%s  %s" % (self.item.get("fig"), self.item.get("spec")),
                       yes, "删除报价", "删除")

    def _decide(self, approve):
        def work():
            return appdata.decide_quote(self.item.get("row", ""), self.item, approve)

        def done(res, err):
            if err:
                self.tip.text = "失败：" + err
                return
            self.dismiss()
            dialog.info("已%s" % ("通过" if approve else "驳回"))

        bg(work, done)

    def make_pdf(self):
        sh = dialog.Sheet("生成 PDF", height=0.42)
        info = dialog.lab("正在生成 PDF，请稍候...", 13, dialog.INK)
        sh.body.add_widget(info)
        sh.body.add_widget(dialog.lab("", 4, dialog.MUTED, height=dp(6)))
        sh.body.add_widget(dialog.btn("关闭", lambda *_: sh.dismiss(), color=dialog.GREY,
                                      text_color=dialog.INK, height=42))
        sh.open()

        def work():
            import time as _t
            t0 = _t.time()
            cur = str(self.item.get("cur") or "RMB").upper()
            label = "Quotation" if cur not in ("RMB", "") else "报价单"
            day = _t.strftime("%Y.%m.%d")
            base = "%s_%s_%s" % (str(self.item.get("fig", "")).replace("/", "_"),
                                 label, day)
            d = appdata._data_dir()
            out = os.path.join(d, base + ".pdf")
            n = 1
            while os.path.exists(out):
                out = os.path.join(d, "%s_%d.pdf" % (base, n))
                n += 1
            merged = dict(self.item)
            c = self.cust or {}
            for k in ("addr", "tel", "contact", "email", "term", "owner", "confirm"):
                v = c.get(k) or ""
                if v:
                    merged[k] = v
            if c.get("contact"):
                merged["attn"] = c["contact"]
            pdf_out.make_quote_pdf(out, self.code, merged, c.get("name", ""))
            return out, _t.time() - t0

        def done(res, err):
            if err:
                info.text = "生成失败：" + err
                info.color = RED
                return
            path, sec = res
            mb = os.path.getsize(path) / 1024.0
            info.text = "生成成功（%.1f 秒，%.0f KB）\n%s" % (sec, mb, path)
            info.color = GREEN
            sh.body.add_widget(dialog.btn(
                "转发 / 分享",
                lambda *_: dialog.info("Windows 上无系统分享，已保存到：\n" + path)
                if not share_pdf(path) else sh.dismiss(),
                color=dialog.BLUE, height=44))

        bg(work, done)


class QuoteForm(Screen):
    """新建 / 编辑报价"""

    FIELDS = [("fig", "图号"), ("spec", "规格"), ("part", "品号/品名"),
              ("price", "单价"), ("moq", "起订量"), ("date", "报价日期")]

    def __init__(self, **kw):
        super().__init__(**kw)
        self.code = ""
        self.cust = {}
        self.rec = None
        root = BoxLayout(orientation="vertical")
        self.header = Header("新建报价", "")
        root.add_widget(self.header)
        body = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(6))
        self.sub = lab("", 12, MUTED)
        body.add_widget(self.sub)
        scroll = ScrollView(bar_width=dp(3))
        form = GridLayout(cols=1, spacing=dp(4), size_hint_y=None)
        form.bind(minimum_height=form.setter("height"))
        self.inputs = {}
        for key, label in self.FIELDS:
            form.add_widget(lab(label, 12, MUTED, height=dp(20)))
            if key == "date":
                b = Button(text="日期：未设置", size_hint_y=None, height=dp(38),
                           background_normal="", background_color=GREY, color=INK,
                           font_size=sp(13))
                font(b)
                b.bind(on_release=lambda *_: self.pick_date())
                form.add_widget(b)
                self.inputs[key] = b
                continue
            t = TextInput(multiline=False, size_hint_y=None, height=dp(38),
                          font_size=sp(13), padding=[dp(8), dp(10)])
            font(t)
            self.inputs[key] = t
            form.add_widget(t)
        form.add_widget(lab("报价确认人（点选）", 12, MUTED, height=dp(20)))
        self.confirm_btn = Button(text="未选择", size_hint_y=None, height=dp(38),
                                  background_normal="", background_color=GREY, color=INK,
                                  font_size=sp(13))
        font(self.confirm_btn)
        self.confirm_btn.bind(on_release=lambda *_: self.pick_confirmer())
        form.add_widget(self.confirm_btn)

        form.add_widget(lab("邮箱（自动带出）", 12, MUTED, height=dp(20)))
        self.email = TextInput(multiline=False, size_hint_y=None, height=dp(38),
                               font_size=sp(13), padding=[dp(8), dp(10)], readonly=True)
        font(self.email)
        form.add_widget(self.email)

        form.add_widget(lab("币种（点选）", 12, MUTED, height=dp(20)))
        self.cur_btn = Button(text="RMB", size_hint_y=None, height=dp(38),
                              background_normal="", background_color=GREY, color=INK,
                              font_size=sp(13))
        font(self.cur_btn)
        self.cur_btn.bind(on_release=lambda *_: self.pick_currency())
        form.add_widget(self.cur_btn)
        form.add_widget(lab("审批状态", 12, MUTED, height=dp(20)))
        self.approve = TextInput(text="待审批", multiline=False, size_hint_y=None,
                                 height=dp(38), font_size=sp(13), padding=[dp(8), dp(10)])
        font(self.approve)
        form.add_widget(self.approve)
        form.add_widget(lab("附件（图纸/确认图）", 12, MUTED, height=dp(20)))
        self.attach_btn = Button(text="选择文件（可多选后逐个添加）", size_hint_y=None,
                                 height=dp(40), background_normal="",
                                 background_color=GREY, color=INK, font_size=sp(13))
        font(self.attach_btn)
        self.attach_btn.bind(on_release=lambda *_: self.pick_file())
        form.add_widget(self.attach_btn)
        self.files = []
        scroll.add_widget(form)
        body.add_widget(scroll)
        foot = BoxLayout(size_hint_y=None, height=dp(58), spacing=dp(8))
        foot.add_widget(flat("返回", lambda: setattr(self.manager, "current", "quotes"),
                             height=44))
        foot.add_widget(btn("保存", self.save, color=GREEN, height=44, size=15))
        body.add_widget(foot)
        root.add_widget(body)
        self.add_widget(root)

    def show(self, code, cust, rec):
        self._cur = "RMB"
        self.code, self.cust, self.rec = code, cust, rec
        self.header.right_lab.text = code
        self.sub.text = "%s ｜ %s" % (code, (cust or {}).get("name", ""))
        vals = rec or {}
        defaults = {"cur": (cust or {}).get("cur") or "RMB", "confirm": (cust or {}).get("confirm"),
                    "date": datetime.date.today().strftime("%Y-%m-%d")}
        for key, widget in self.inputs.items():
            widget.text = str(vals.get(key) or defaults.get(key, ""))
        self._cur = (vals.get("cur") or defaults["cur"] or "RMB").upper()
        self.cur_btn.text = self._cur
        cval = vals.get("confirm") or defaults.get("confirm") or ""
        self.confirm_btn.text = cval or "未选择"
        self.email.text = vals.get("email") or (appdata.confirm_email(cval) if cval else "")
        self.approve.text = vals.get("approve") or "待审批"

    def pick_currency(self):
        sh = dialog.Sheet("选择币种", height=0.4)
        for code in ("RMB", "USD", "EUR"):
            def pick(c=code):
                self._cur = c
                self.cur_btn.text = c
                sh.dismiss()
            b = Button(text=code, size_hint_y=None, height=dp(46), background_normal="",
                       background_color=GREY, color=INK, font_size=sp(15))
            font(b)
            b.bind(on_release=lambda *_x, cb=pick: cb())
            sh.body.add_widget(b)
        sh.body.add_widget(dialog.btn("取消", lambda *_: sh.dismiss(), color=dialog.GREY,
                                      text_color=dialog.INK, height=42))
        sh.open()

    def pick_confirmer(self):
        rows = appdata.load_confirmers()
        if not rows:
            dialog.info("Base 里没有「确认人」记录")
            return
        sh = dialog.Sheet("选择报价确认人", height=0.6)
        sv = ScrollView(bar_width=dp(3))
        box = GridLayout(cols=1, spacing=dp(4), size_hint_y=None)
        box.bind(minimum_height=box.setter("height"))
        for r in rows:
            def pick(r=r):
                self.confirm_btn.text = r["name"]
                self.email.text = r.get("email", "")
                sh.dismiss()
            b = Button(text="%s  %s" % (r["name"], r.get("email", "")),
                       size_hint_y=None, height=dp(42), background_normal="",
                       background_color=GREY, color=INK, font_size=sp(13))
            font(b)
            b.bind(on_release=lambda *_x, cb=pick: cb())
            box.add_widget(b)
        sv.add_widget(box)
        sh.body.add_widget(sv)
        sh.body.add_widget(dialog.btn("取消", lambda *_: sh.dismiss(), color=dialog.GREY,
                                      text_color=dialog.INK, height=42))
        sh.open()

    def pick_date(self):
        cur = self.inputs["date"].text
        cur = cur.split("：", 1)[-1] if "：" in cur else ""
        cur = "" if cur in ("未设置", "日期") else cur

        def picked(val):
            self.inputs["date"].text = "日期：" + (val or "未设置")

        datepicker_ui.DatePicker(current=cur, on_pick=picked).open()

    def pick_file(self):
        def got(data, name):
            def work():
                tok = appdata.upload_attachment(data, name)
                return tok

            def done(tok, err):
                if err:
                    dialog.info("上传失败：" + err)
                    return
                self.files.append(tok)
                self.attach_btn.text = "已添加 %d 个附件" % len(self.files)

            bg(work, done)

        try:
            from android import activity
            from jnius import autoclass
            Intent = autoclass("android.content.Intent")
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            act = PythonActivity.mActivity

            def on_result(req, res, intent):
                if req != 1001 or not intent:
                    return
                uri = intent.getData()
                if uri is None:
                    return
                stream = act.getContentResolver().openInputStream(uri)
                JavaString = autoclass("java.lang.String")
                buf = autoclass("java.io.ByteArrayOutputStream")()
                tmp = bytearray(8192)
                while True:
                    n = stream.read(tmp)
                    if n <= 0:
                        break
                    buf.write(tmp, 0, n)
                stream.close()
                data = bytes(buf.toByteArray())
                name = str(uri.getLastPathSegment()).split("/")[-1] or "attachment.bin"
                Clock.schedule_once(lambda *_: got(data, name), 0)

            activity.bind(on_activity_result=on_result)
            i = Intent(Intent.ACTION_GET_CONTENT)
            i.setType("*/*")
            act.startActivityForResult(i, 1001)
        except Exception:
            dialog.info("本机测试版无法选文件，装 APK 后可用")

    def save(self):
        fields = {"客户编号": self.code}
        for key, widget in self.inputs.items():
            val = widget.text.strip()
            if key == "fig" and not val:
                dialog.info("图号必填")
                return
            if val:
                fields[{"fig": "图号", "spec": "规格", "part": "品号", "price": "单价",
                        "moq": "起订量", "date": "报价日期",
                        "confirm": "报价确认人"}[key]] = val
        fields["币种"] = getattr(self, "_cur", "RMB")
        if self.approve.text.strip():
            fields["审批状态"] = self.approve.text.strip()

        if self.confirm_btn.text and self.confirm_btn.text != "未选择":
            fields["报价确认人"] = appdata.name_for_currency(
                self.confirm_btn.text, getattr(self, "_cur", "RMB"))
        if self.email.text.strip():
            fields["邮箱"] = self.email.text.strip()
        fields.update(appdata.quote_status_fields(
            is_new=not (self.rec or {}).get("row"),
            cur_status=(self.rec or {}).get("approve", "")))
        if getattr(self, "files", None):
            fields["附件文件"] = [{"file_token": t} for t in self.files if t]

        def work():
            rid = appdata.save_quote(fields, (self.rec or {}).get("row", ""))
            try:
                if not appdata.is_admin():
                    q = {"fig": fields.get("图号", ""), "cust": self.code,
                         "spec": fields.get("规格", ""), "price": fields.get("单价", ""),
                         "no": fields.get("NO.", "")}
                    appdata.append_approval(q, "提交", fields.get("审批状态", "待审批"),
                                            "手机端保存报价", rid)
            except Exception:
                pass
            return rid

        def done(res, err):
            if err:
                dialog.info("保存失败：" + err)
                return
            dialog.info("已保存")
            if fields.get("审批状态") in ("待审批", "待审核"):
                try:
                    appdata.push_approval_notice(fields.get("图号", ""), self.code,
                                                 fields.get("单价", ""),
                                                 fields.get("币种", ""),
                                                 spec=fields.get("规格", ""),
                                                 moq=fields.get("起订量", ""),
                                                 confirm=fields.get("报价确认人", ""))
                except Exception:
                    pass
            self.manager.current = "quotes"
            self.manager.get_screen("quotes").load()

        bg(work, done)


class CustomerForm(Screen):
    FIELDS = [("code", "客户编号"), ("name", "名称"), ("owner", "负责业务员"),
              ("term", "交易条件"), ("cur", "币种"), ("confirm", "报价确认人")]

    def __init__(self, **kw):
        super().__init__(**kw)
        self.rec = None
        root = BoxLayout(orientation="vertical")
        root.add_widget(Header("新增客户", ""))
        scroll = ScrollView(bar_width=dp(3))
        form = GridLayout(cols=1, spacing=dp(4), size_hint_y=None, padding=dp(10))
        form.bind(minimum_height=form.setter("height"))
        self.inputs = {}
        for key, label in self.FIELDS:
            form.add_widget(lab(label, 12, MUTED, height=dp(20)))
            if key == "date":
                b = Button(text="日期：未设置", size_hint_y=None, height=dp(38),
                           background_normal="", background_color=GREY, color=INK,
                           font_size=sp(13))
                font(b)
                b.bind(on_release=lambda *_: self.pick_date())
                form.add_widget(b)
                self.inputs[key] = b
                continue
            t = TextInput(multiline=False, size_hint_y=None, height=dp(38),
                          font_size=sp(13), padding=[dp(8), dp(10)])
            font(t)
            self.inputs[key] = t
            form.add_widget(t)
        scroll.add_widget(form)
        root.add_widget(scroll)
        foot = BoxLayout(size_hint_y=None, height=dp(58), spacing=dp(8), padding=dp(8))
        foot.add_widget(flat("返回", lambda: setattr(self.manager, "current", "customers"),
                             height=44))
        foot.add_widget(btn("保存", self.save, color=GREEN, height=44, size=15))
        root.add_widget(foot)
        self.add_widget(root)

    def show(self, rec=None):
        self.rec = rec
        for key, widget in self.inputs.items():
            widget.text = str((rec or {}).get(key) or ("RMB" if key == "cur" else ""))

    def save(self):
        code = self.inputs["code"].text.strip()
        if not code:
            dialog.info("客户编号必填")
            return
        fields = {}
        for key in ("name", "owner", "term", "confirm"):
            val = self.inputs[key].text.strip()
            if val:
                fields[{"name": "名称", "owner": "负责业务员", "term": "交易条件",
                        "confirm": "报价确认人"}[key]] = val
        if self.inputs["cur"].text.strip():
            fields["币种"] = self.inputs["cur"].text.strip()

        def work():
            return appdata.save_customer(code, fields, (self.rec or {}).get("row_id", ""))

        def done(res, err):
            if err:
                dialog.info("保存失败：" + err)
                return
            dialog.info("已保存")
            self.manager.current = "customers"
            self.manager.get_screen("customers").reload()

        bg(work, done)




def share_pdf(path):
    """把 PDF 交给系统分享（微信/企业微信/飞书/邮件都会出现在列表里）。"""
    try:
        from android import mActivity  # type: ignore
        from jnius import autoclass, cast  # type: ignore
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        Intent = autoclass("android.content.Intent")
        Uri = autoclass("android.net.Uri")
        File = autoclass("java.io.File")
        activity = PythonActivity.mActivity
        ctx = activity.getApplicationContext()
        uri = None
        try:  # Android 10+：走 MediaStore.Downloads，无需 FileProvider
            MediaStore = autoclass("android.provider.MediaStore")
            Downloads = autoclass("android.provider.MediaStore$Downloads")
            ContentValues = autoclass("android.content.ContentValues")
            Build = autoclass("android.os.Build")
            if Build.VERSION.SDK_INT >= 29:
                values = ContentValues()
                values.put("_display_name", File(path).getName())
                values.put("mime_type", "application/pdf")
                values.put("relative_path", "Download")
                resolver = ctx.getContentResolver()
                uri = resolver.insert(Downloads.EXTERNAL_CONTENT_URI, values)
                out = resolver.openOutputStream(uri)
                data = open(path, "rb").read()
                out.write(bytearray(data))
                out.flush()
                out.close()
        except Exception:
            uri = None
        if uri is None:
            uri = Uri.fromFile(File(path))
        intent = Intent(Intent.ACTION_SEND)
        intent.setType("application/pdf")
        intent.putExtra(Intent.EXTRA_STREAM, cast("android.os.Parcelable", uri))
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        activity.startActivity(Intent.createChooser(intent, "转发报价单 PDF"))
        return True
    except Exception:
        return False


def install_apk(path):
    """FileProvider 失败则 StrictMode 关闭后 file:// 兜底（Windows 上直接返回 False）。"""
    try:
        from jnius import autoclass, cast
    except Exception:
        return False
    Intent = autoclass("android.content.Intent")
    File = autoclass("java.io.File")
    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    activity = PythonActivity.mActivity
    try:
        Uri = autoclass("android.net.Uri")
        FileProvider = autoclass("androidx.core.content.FileProvider")
        uri = FileProvider.getUriForFile(activity.getPackageName() + ".fileprovider",
                                         File(path))
        i = Intent(Intent.ACTION_VIEW)
        i.setDataAndType(cast("android.net.Uri", uri),
                         "application/vnd.android.package-archive")
        i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        activity.startActivity(i)
        return True
    except Exception:
        pass
    try:
        StrictMode = autoclass("android.os.StrictMode")
        StrictMode.setVmPolicy(StrictMode.VmPolicy.Builder().build())
        Uri = autoclass("android.net.Uri")
        i = Intent(Intent.ACTION_VIEW)
        i.setDataAndType(Uri.fromFile(File(path)), "application/vnd.android.package-archive")
        i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        activity.startActivity(i)
        return True
    except Exception:
        return False


def check_apk_update():
    def done(res, err):
        if err:
            dialog.info("检查失败：" + err)
            return
        if not res:
            dialog.info("暂无报价 APK 更新")
            return
        latest = res["version"]
        if appdata._vkey(latest) <= appdata._vkey(APP_VERSION):
            dialog.info("已是最新版本 V%s" % APP_VERSION)
            return
        dialog.confirm("发现新版本 V%s（当前 V%s）\n下载并安装？" % (latest, APP_VERSION),
                       lambda: _start_update(latest, res), "在线更新", "下载安装")

    bg(lambda: appdata.latest_release("android-quote"), done)


def _write_update_result(ver, text):
    try:
        import time as _t
        with open(os.path.join(appdata._data_dir(), "update_result.txt"), "a",
                  encoding="utf-8") as f:
            f.write("%s  V%s  %s\n" % (_t.strftime("%Y-%m-%d %H:%M"), ver, text))
    except Exception:
        pass


def _start_update(latest, res):
    sh = dialog.Sheet("更新 V%s" % latest, height=0.5)
    info = dialog.lab("准备下载...", 13, dialog.INK)
    sh.body.add_widget(info)
    sh.body.add_widget(dialog.lab("", 4, dialog.MUTED, height=dp(6)))
    sh.body.add_widget(dialog.btn("关闭", lambda *_: sh.dismiss(), color=GREY,
                                  text_color=INK, height=42))
    sh.open()

    def set_text(txt, color=INK):
        def _u(*_):
            info.text = txt
            info.color = color if len(color) == 4 else (color[0], color[1], color[2], 1)
        Clock.schedule_once(_u, 0)

    def prog(n):
        set_text("下载中... %.1f MB" % (n / 1048576.0))

    def dl():
        out = os.path.join(appdata._data_dir(), "quote-%s.apk" % latest)
        appdata.download_parts(res["file_token"], out, on_progress=prog)
        return out

    def after_dl(path, e2):
        if e2:
            set_text("下载失败：" + e2, RED)
            _write_update_result(latest, "下载失败：" + e2)
            return
        mb = os.path.getsize(path) / 1048576.0
        set_text("下载完成 %.1f MB，校验中..." % mb)
        want = (res.get("sha256") or "").lower()
        try:
            import hashlib
            h = hashlib.sha256()
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(1 << 20), b""):
                    h.update(chunk)
            got = h.hexdigest()
        except Exception as e:
            set_text("校验异常：" + str(e)[:60], RED)
            return
        if want and got != want:
            set_text("SHA256 不一致，已中止（请重试）", RED)
            _write_update_result(latest, "SHA256 不一致")
            return
        set_text("SHA256 校验通过，%.1f MB\n正在打开安装器..." % mb)

        def inst():
            return install_apk(path)

        def after_inst(ok, e3):
            if ok:
                set_text("已调起系统安装器，装完版本变 V%s\n安装包：%s" % (latest, path))
                _write_update_result(latest, "已调起安装器")
            else:
                set_text("本机无法直接安装（Windows 属正常）\n安装包：%s" % path)
                _write_update_result(latest, "已下载，需手动安装")

        bg(inst, after_inst)

    bg(dl, after_dl)




class PendingScreen(Screen):
    """待审批列表：仅审单员/管理员"""

    def __init__(self, **kw):
        super().__init__(**kw)
        root = BoxLayout(orientation="vertical")
        self.header = Header("待审批报价", "← 返回")
        self.header.right_lab.bind(on_touch_down=self._back)
        root.add_widget(self.header)
        self.count = lab("", 13, (0.35, 0.40, 0.47, 1), False)
        root.add_widget(self.count)
        self.scroll = ScrollView(bar_width=dp(3))
        self.box = GridLayout(cols=1, spacing=dp(6), size_hint_y=None, padding=[dp(8), dp(4)])
        self.box.bind(minimum_height=self.box.setter("height"))
        self.scroll.add_widget(self.box)
        root.add_widget(self.scroll)
        self.add_widget(root)

    def _back(self, w, touch):
        if w.collide_point(*touch.pos):
            self.manager.current = "home"
            return True
        return False

    def on_pre_enter(self, *_):
        self.load()

    def load(self):
        self.box.clear_widgets()
        self.count.text = "加载中..."

        def work():
            items = appdata.load_items(refresh=True)
            return [x for x in items if (x.get("approve") or "").strip() in ("", "待审批", "待审核")]

        def done(res, err):
            self.box.clear_widgets()
            if err:
                self.count.text = "失败：" + err
                return
            rows = res or []
            self.count.text = "%d 条待审批" % len(rows)
            if not rows:
                self.box.add_widget(lab("没有待审批的报价", 13, MUTED))
                return
            for it in rows[:80]:
                c = card(padding=10, spacing=2)
                c.height = dp(76)
                c.add_widget(lab("%s  %s" % (it["fig"], it["spec"]), 14, INK, True))
                c.add_widget(lab("客户 %s | %s %s | %s" % (
                    it["cust"], it["price"], it["cur"], it["date"]), 12, MUTED))
                row = BoxLayout(size_hint_y=None, height=dp(38), spacing=dp(6))
                row.add_widget(flat("驳回", lambda *_, i=it: self.decide(i, False),
                                    color=RED, text_color=(1, 1, 1, 1), height=36))
                row.add_widget(flat("通过", lambda *_, i=it: self.decide(i, True),
                                    color=GREEN, text_color=(1, 1, 1, 1), height=36))
                c.add_widget(row)
                self.box.add_widget(c)

        bg(work, done)

    def decide(self, item, ok):
        def work():
            return appdata.decide_quote(item.get("row", ""), item, ok)

        def done(res, err):
            if err:
                dialog.info("失败：" + err)
                return
            dialog.info("已" + ("通过" if ok else "驳回"))
            self.load()

        bg(work, done)

class QuoteApp(App):
    def build(self):
        Window.clearcolor = BG
        self.title = "报价单工具"
        sm = ScreenManager(transition=SlideTransition(duration=0.12))
        sm.add_widget(LoginScreen(name="login"))
        sm.add_widget(HomeScreen(name="home"))
        sm.add_widget(PendingScreen(name="pending"))
        sm.add_widget(CustomersScreen(name="customers"))
        sm.add_widget(QuotesScreen(name="quotes"))
        sm.add_widget(QuoteForm(name="quoteform"))
        sm.add_widget(CustomerForm(name="customerform"))
        sm.current = "customers" if (appdata._load_token() or {}).get("refresh_token") else "login"
        return sm


if __name__ == "__main__":
    QuoteApp().run()
