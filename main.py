# -*- coding: utf-8 -*-
"""报价单工具 Android 版（Kivy）— 客户 → 报价 → PDF

UI 对齐 Windows 报价单：蓝色顶栏 / 白卡片 / 灰底 / 圆角列表。
"""
import datetime
import os
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

APP_VERSION = "1.6.11"
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
            appdata.log_crash("bg", tb.format_exc())
            Clock.schedule_once(lambda *_: done(None, str(e)[:200]), 0)
    threading.Thread(target=run, daemon=True).start()


class _KeepAlive(ExceptionHandler):
    def handle_exception(self, inst):
        import traceback as tb
        appdata.log_crash("uncaught", tb.format_exc())
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
        try:
            auth.start_callback(lambda c: Clock.schedule_once(lambda *_: self._auto_code(c), 0))
        except Exception:
            pass
        try:
            webbrowser.open(auth.auth_url())
        except Exception:
            pass
        self.tip.text = "已打开授权页；同意后自动登录"

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

        def done(_res, err):
            if err:
                self.tip.text = "失败：" + err
                return
            try:
                auth.stop_callback()
            except Exception:
                pass
            self.manager.current = "customers"

        bg(lambda: auth.exchange_code(self.code.text, appdata), done)


class CustomersScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.items = {}
        root = BoxLayout(orientation="vertical")
        self.header = Header("客户报价", "")
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
        self.count = lab("", 12, MUTED)
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
        self.count.text = "%d 家客户" % len(rows)
        self.box.clear_widgets()
        for c in rows:
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
                if not kw or kw in ("%s %s %s" % (x["fig"], x["spec"], x.get("no", ""))).upper()]
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

    def new_quote(self):
        self.manager.get_screen("quoteform").show(self.code, self.cust, None)
        self.manager.current = "quoteform"

    def edit_quote(self, item):
        self.manager.get_screen("quoteform").show(self.code, self.cust, item)
        self.manager.current = "quoteform"


class QuoteDetail(dialog.Sheet):
    def __init__(self, code, cust, item, on_edit=None):
        super().__init__("报价详情", height=0.7)
        self.code, self.cust, self.item = code, cust, item
        rows = [("图号", item["fig"]), ("规格", item["spec"]), ("单价", "%s %s" % (item["price"], item["cur"])),
                ("起订量", item["moq"] or "-"), ("报价日期", item["date"]),
                ("确认人", item["confirm"] or "-"), ("审批", item["approve"] or "-"),
                ("客户", "%s %s" % (code, cust.get("name", "")))]
        g = GridLayout(cols=2, size_hint_y=None, spacing=dp(4))
        g.bind(minimum_height=g.setter("height"))
        for k, v in rows:
            g.add_widget(lab(k, 12, MUTED, height=dp(28)))
            g.add_widget(lab(str(v), 13, INK, height=dp(28)))
        self.body.add_widget(g)

        self.tip = lab("", 12, MUTED)
        self.body.add_widget(self.tip)
        foot = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
        foot.add_widget(dialog.btn("关闭", lambda *_: self.dismiss(), color=GREY, text_color=INK))
        status = (item.get("approve") or "").strip()
        if appdata.can_approve() and status not in ("通过", "驳回"):
            self.body.add_widget(dialog.lab("当前状态：%s，可审核" % (status or "待审核"), 12,
                                            dialog.MUTED))
            ab = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
            ab.add_widget(dialog.btn("驳回", lambda *_: self._decide(False), color=RED))
            ab.add_widget(dialog.btn("通过", lambda *_: self._decide(True), color=GREEN))
            self.body.add_widget(ab)
        if on_edit:
            def go_edit(*_):
                self.dismiss()
                on_edit(item)
            foot.add_widget(dialog.btn("编辑", go_edit, color=(0.90, 0.55, 0.15, 1)))
        foot.add_widget(dialog.btn("生成 PDF", self.make_pdf, color=BLUE))
        self.body.add_widget(foot)

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
        self.tip.text = "生成 PDF…"

        def work():
            out = os.path.join(appdata._data_dir(), "quote-%s-%s.pdf" %
                               (self.code, str(self.item["fig"]).replace("/", "_")[:20]))
            pdf_out.make_quote_pdf(out, self.code, self.item, self.cust.get("name", ""))
            return out

        def done(res, err):
            if err:
                self.tip.text = "失败：" + err
                return
            self.tip.text = "PDF 已生成"
            dialog.confirm("PDF 已生成，是否转发？（微信 / 企业微信 / 飞书 / 邮件）",
                           lambda: (self.dismiss(), share_pdf(res)), "转发 PDF", "转发")




class QuoteForm(Screen):
    """新建 / 编辑报价"""

    FIELDS = [("fig", "图号"), ("spec", "规格"), ("price", "单价"), ("moq", "起订量"),
              ("date", "报价日期"), ("confirm", "报价确认人")]

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
        form.add_widget(lab("币种", 12, MUTED, height=dp(20)))
        self.cur = TextInput(text="RMB", multiline=False, size_hint_y=None, height=dp(38),
                             font_size=sp(13), padding=[dp(8), dp(10)])
        font(self.cur)
        form.add_widget(self.cur)
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
        self.code, self.cust, self.rec = code, cust, rec
        self.header.right_lab.text = code
        self.sub.text = "%s ｜ %s" % (code, (cust or {}).get("name", ""))
        vals = rec or {}
        defaults = {"cur": (cust or {}).get("cur") or "RMB", "confirm": (cust or {}).get("confirm"),
                    "date": datetime.date.today().strftime("%Y-%m-%d")}
        for key, widget in self.inputs.items():
            widget.text = str(vals.get(key) or defaults.get(key, ""))
        self.cur.text = vals.get("cur") or defaults["cur"]
        self.approve.text = vals.get("approve") or "待审批"

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
                fields[{"fig": "图号", "spec": "规格", "price": "单价", "moq": "起订量",
                        "date": "报价日期", "confirm": "报价确认人"}[key]] = val
        if self.cur.text.strip():
            fields["币种"] = self.cur.text.strip()
        if self.approve.text.strip():
            fields["审批状态"] = self.approve.text.strip()

        fields.update(appdata.quote_status_fields())
        if getattr(self, "files", None):
            fields["附件文件"] = [{"file_token": t} for t in self.files if t]

        def work():
            rid = appdata.save_quote(fields, (self.rec or {}).get("row", ""))
            try:
                q = {"fig": fields.get("图号", ""), "cust": self.code,
                     "spec": fields.get("规格", ""), "price": fields.get("单价", ""),
                     "no": fields.get("NO.", "")}
                appdata.append_approval(q, "提交", fields.get("审批状态", "待审核"),
                                        "手机端保存报价", rid)
            except Exception:
                pass
            return rid

        def done(res, err):
            if err:
                dialog.info("保存失败：" + err)
                return
            dialog.info("已保存")
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


class QuoteApp(App):
    def build(self):
        Window.clearcolor = BG
        self.title = "报价单工具"
        sm = ScreenManager(transition=SlideTransition(duration=0.12))
        sm.add_widget(LoginScreen(name="login"))
        sm.add_widget(CustomersScreen(name="customers"))
        sm.add_widget(QuotesScreen(name="quotes"))
        sm.add_widget(QuoteForm(name="quoteform"))
        sm.add_widget(CustomerForm(name="customerform"))
        sm.current = "customers" if (appdata._load_token() or {}).get("refresh_token") else "login"
        return sm


if __name__ == "__main__":
    QuoteApp().run()
