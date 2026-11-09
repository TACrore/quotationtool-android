# -*- coding: utf-8 -*-
"""报价单工具 Android 版（Kivy）— 最小可用：客户 → 报价 → 出 PDF"""
import os
import threading

import appdata
from kivy.app import App
from kivy.clock import Clock, mainthread
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import Screen, ScreenManager
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput

FONT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sy-cjk.ttf")


def mk_label(text="", size=dp(14), bold=False, color=(0.12, 0.16, 0.22, 1), **kw):
    kw.setdefault("halign", "left")
    kw.setdefault("valign", "middle")
    lab = Label(text=text, font_size=size, color=color, bold=bold, **kw)
    if os.path.exists(FONT):
        lab.font_name = FONT
    lab.bind(size=lambda w, *_: setattr(w, "text_size", (w.width, None)))
    return lab


class HomeScreen(Screen):
    def __init__(self, **kw):
        super().__init__(name="home", **kw)
        root = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(8))
        root.add_widget(mk_label("报价单工具", dp(22), True))
        root.add_widget(mk_label("账号：" + (App.get_running_app().me or "未登录"), dp(13)))
        self.list_box = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(6))
        self.list_box.bind(minimum_height=self.list_box.setter("height"))
        sv = ScrollView()
        sv.add_widget(self.list_box)
        root.add_widget(sv)
        row = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
        b1 = Button(text="加载客户", on_release=lambda *_: self.load_customers())
        b2 = Button(text="刷新", on_release=lambda *_: self.load_customers())
        row.add_widget(b1)
        row.add_widget(b2)
        root.add_widget(row)
        self.add_widget(root)

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
        for code, c in list(custs.items())[:300]:
            btn = Button(text=f"{code}  {c['name'][:14]}", size_hint_y=None, height=dp(44),
                         halign="left")
            btn.bind(on_release=lambda _b, c=code: self.open_customer(c))
            self.list_box.add_widget(btn)

    @mainthread
    def show_error(self, msg):
        self.list_box.clear_widgets()
        self.list_box.add_widget(mk_label("失败：" + msg, dp(13), color=(0.7, 0.1, 0.1, 1)))

    def open_customer(self, code):
        app = App.get_running_app()
        app.cur_customer = code
        app.sm.current = "quotes"


class QuotesScreen(Screen):
    def __init__(self, **kw):
        super().__init__(name="quotes", **kw)
        root = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(8))
        self.title = mk_label("报价", dp(18), True)
        root.add_widget(self.title)
        self.picker = Spinner(text="选择图号", values=[], size_hint_y=None, height=dp(44))
        root.add_widget(self.picker)
        self.info = mk_label("", dp(13))
        root.add_widget(self.info)
        self.items = []
        b = Button(text="生成 PDF 并分享", size_hint_y=None, height=dp(52),
                   on_release=lambda *_: self.make_pdf())
        root.add_widget(b)
        back = Button(text="返回客户", size_hint_y=None, height=dp(44),
                      on_release=lambda *_: setattr(App.get_running_app().sm, "current", "home"))
        root.add_widget(back)
        self.add_widget(root)

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
        figs = sorted({i["fig"] for i in items})
        self.picker.values = figs
        if figs:
            self.picker.text = figs[0]
        self.info.text = f"共 {len(items)} 条，{len(figs)} 个图号"

    def make_pdf(self):
        fig = self.picker.text
        if not fig or fig == "选择图号":
            return
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
        pop = Popup(title="已生成", content=mk_label(path, dp(12)),
                    size_hint=(0.9, 0.4))
        pop.open()

    @mainthread
    def _err(self, msg):
        Popup(title="失败", content=mk_label(msg, dp(12)), size_hint=(0.9, 0.4)).open()


class QuoteApp(App):
    me = ""
    cur_customer = ""
    sm = None

    def build(self):
        self.sm = ScreenManager()
        self.sm.add_widget(HomeScreen())
        self.sm.add_widget(QuotesScreen())
        return self.sm

    def on_start(self):
        try:
            self.me = appdata.load_conf().get("user_name", "")
        except Exception:
            self.me = ""

    def make_pdf(self, cust_code, fig):
        """生成单条报价单 PDF（reportlab），返回文件路径"""
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.pdfgen import canvas

        if os.path.exists(FONT):
            pdfmetrics.registerFont(TTFont("SY", FONT))
            font = "SY"
        else:
            font = "Helvetica"

        item = next((i for i in appdata.load_items()
                     if i["cust"] == cust_code and i["fig"] == fig), None)
        if not item:
            raise RuntimeError("找不到该图号报价")

        outdir = os.path.join(appdata.DATA_DIR, "pdf")
        os.makedirs(outdir, exist_ok=True)
        path = os.path.join(outdir, f"{fig}_{cust_code}.pdf")
        c = canvas.Canvas(path, pagesize=A4)
        c.setFont(font, 16)
        c.drawString(40, 800, "报价单")
        c.setFont(font, 10)
        lines = [f"客户编号：{cust_code}", f"图号：{item['fig']}", f"规格：{item['spec']}",
                 f"单价：{item['price']} {item['cur']}", f"起订量：{item['moq']}",
                 f"报价日期：{item['date']}", f"报价确认人：{item['confirm']}"]
        y = 770
        for ln in lines:
            c.drawString(40, y, ln)
            y -= 18
        c.showPage()
        c.save()
        return path


if __name__ == "__main__":
    QuoteApp().run()
