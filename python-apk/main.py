"""Maik Subs, versione Python (Kivy) con animazioni 3D.

Avvio sul computer:   python main.py
APK Android:          buildozer android debug   (vedi README.md)
"""
import os
from datetime import date, timedelta

from kivy.animation import Animation
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics.texture import Texture
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import BooleanProperty, ListProperty, NumericProperty, ObjectProperty, StringProperty
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView
from kivy.uix.screenmanager import CardTransition, FadeTransition, NoTransition, RiseInTransition, Screen, ScreenManager
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget
from kivy.utils import escape_markup, get_color_from_hex, platform

import store as S
from gl3d import Donut3D, Logo3D

ACCENT = "#7C5CFF"


def hexc(h, a=1.0):
    c = get_color_from_hex(h)
    return [c[0], c[1], c[2], a]


THEMES = {
    False: dict(bg="#F4F4F8", card="#FFFFFF", card2="#EEEEF3", text="#0B0B12", text2="#6B6F7B", text3="#A3A6B1",
                nav="#FFFFFF"),
    True: dict(bg="#0A0A0F", card="#16161D", card2="#22222C", text="#F5F5FA", text2="#9A9DAA", text3="#5F6270",
               nav="#16161D"),
}


# Simboli che Roboto non ha: li disegniamo con DejaVuSans (incluso in Kivy).
SYMBOLS = set("★✓↑✎◉○∞◷◕☺▦⌂❚▶✕")


def sym(text):
    out = []
    for ch in escape_markup(text):
        out.append("[font=DejaVuSans]%s[/font]" % ch if ch in SYMBOLS else ch)
    return "".join(out)


def vibrate():
    if platform == "android":
        try:
            from plyer import vibrator
            vibrator.vibrate(0.015)
        except Exception:
            pass


def gradient_texture(c1, c2):
    """Texture 2x2 che, stirata, dà una sfumatura diagonale."""
    a, b = hexc(c1), hexc(c2)
    m = [(a[i] + b[i]) / 2 for i in range(4)]
    px = []
    for c in (m, b, a, m):  # basso-sx, basso-dx, alto-sx, alto-dx
        px.extend(int(v * 255) for v in c)
    tex = Texture.create(size=(2, 2), colorfmt="rgba")
    tex.blit_buffer(bytes(px), colorfmt="rgba", bufferfmt="ubyte")
    tex.mag_filter = "linear"
    tex.min_filter = "linear"
    return tex


KV = r"""
#:import dp kivy.metrics.dp
#:import sp kivy.metrics.sp

<RoundBox>:
    canvas.before:
        PushMatrix
        Scale:
            origin: self.center
            x: self.zoom
            y: self.zoom * self.flip
        Color:
            rgba: self.bg_color
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [self.radius]
            texture: self.bg_texture
    canvas.after:
        PopMatrix

<Txt>:
    color: app.c_text
    text_size: self.width, None
    size_hint_y: None
    height: self.texture_size[1]
    halign: 'left'
    valign: 'middle'
    font_size: sp(15)

<Icon>:
    font_name: 'DejaVuSans'
    color: app.c_text
    font_size: sp(20)
    size_hint: None, None
    size: dp(40), dp(40)

<IconBtn>:
    size_hint: None, None
    size: dp(42), dp(42)
    radius: dp(21)
    bg_color: app.c_card2
    Label:
        text: root.icon
        font_name: 'DejaVuSans'
        font_size: sp(20)
        color: root.icon_color or app.c_text
        pos: root.pos
        size: root.size

<Chip>:
    size_hint: None, None
    height: dp(38)
    width: lbl.texture_size[0] + dp(30)
    radius: dp(19)
    bg_color: (root.color or app.c_accent) if root.selected else app.c_card
    Label:
        id: lbl
        text: app.sym(root.text)
        markup: True
        bold: True
        font_size: sp(14)
        color: (1, 1, 1, 1) if root.selected else app.c_text
        pos: root.pos
        size: root.size

<PrimaryButton>:
    size_hint_y: None
    height: dp(56)
    radius: dp(18)
    bg_color: app.c_accent if root.kind == 'primary' else (app.c_danger_soft if root.kind == 'danger' else app.c_card2)
    Label:
        text: app.sym(root.text)
        markup: True
        bold: True
        font_size: sp(16)
        color: (1, 1, 1, 1) if root.kind == 'primary' else (app.c_danger if root.kind == 'danger' else app.c_text)
        pos: root.pos
        size: root.size

<Field@TextInput>:
    size_hint_y: None
    height: dp(52)
    background_normal: ''
    background_active: ''
    background_color: 0, 0, 0, 0
    canvas.before:
        Color:
            rgba: app.c_card
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(16)]
        Color:
            rgba: app.c_accent if self.focus else (0, 0, 0, 0)
        Line:
            rounded_rectangle: (self.x, self.y, self.width, self.height, dp(16)) if self.width > dp(40) else (0, 0, dp(40), dp(40), dp(4))
            width: dp(1.2)
        # TextInput usa l'ultimo colore di canvas.before per il testo: lo ripristiniamo.
        Color:
            rgba: self.disabled_foreground_color if self.disabled else (self.hint_text_color if not self.text else self.foreground_color)
    foreground_color: app.c_text
    hint_text_color: app.c_text3
    cursor_color: app.c_accent
    selection_color: app.c_accent[:3] + [0.3]
    padding: dp(16), (self.height - self.line_height) / 2
    font_size: sp(16)
    multiline: False
    write_tab: False

<SectionLabel@Label>:
    color: app.c_text2
    bold: True
    font_size: sp(12)
    text_size: self.width, None
    size_hint_y: None
    height: dp(26)
    halign: 'left'
    valign: 'bottom'

<TopBar>:
    size_hint_y: None
    height: dp(60)
    padding: dp(16), dp(8)
    spacing: dp(8)
    IconBtn:
        icon: root.left_icon
        opacity: 1 if root.left_icon else 0
        disabled: not root.left_icon
        on_release: root.dispatch('on_back_press')
    Label:
        text: root.title
        bold: True
        font_size: sp(18)
        color: app.c_text
    IconBtn:
        icon: root.right_icon
        opacity: 1 if root.right_icon else 0
        disabled: not root.right_icon
        on_release: root.dispatch('on_action_press')

<Page>:
    canvas.before:
        Color:
            rgba: app.c_bg
        Rectangle:
            pos: self.pos
            size: self.size

<Scroller@ScrollView>:
    do_scroll_x: False
    bar_width: 0
    effect_cls: 'ScrollEffect'

<Column@BoxLayout>:
    orientation: 'vertical'
    size_hint_y: None
    height: self.minimum_height
    padding: dp(16), dp(8), dp(16), dp(130)
    spacing: dp(16)

<BottomNav>:
    size_hint: 1, None
    height: dp(96)
    pos_hint: {'x': 0, 'y': 0}
    padding: dp(14), dp(6), dp(14), dp(18)
    RoundBox:
        bg_color: app.c_nav
        radius: dp(28)
        padding: dp(6), 0
        NavTab:
            name: 'home'
            icon: '⌂'
            label: 'Home'
        NavTab:
            name: 'calendar'
            icon: '▦'
            label: 'Calendario'
        AnchorLayout:
            Tappable:
                size_hint: None, None
                size: dp(58), dp(58)
                radius: dp(21)
                bg_color: app.c_accent
                on_release: app.open_add()
                Label:
                    text: '+'
                    font_size: sp(34)
                    color: 1, 1, 1, 1
                    pos: self.parent.pos
                    size: self.parent.size
        NavTab:
            name: 'stats'
            icon: '◕'
            label: 'Statistiche'
        NavTab:
            name: 'settings'
            icon: '☺'
            label: 'Profilo'

<NavTab>:
    orientation: 'vertical'
    padding: 0, dp(10)
    Label:
        text: root.icon
        font_name: 'DejaVuSans'
        font_size: sp(23)
        color: app.c_accent if app.current_tab == root.name else app.c_text3
    Label:
        text: root.label
        font_size: sp(10.5)
        bold: True
        size_hint_y: None
        height: dp(16)
        color: app.c_accent if app.current_tab == root.name else app.c_text3
"""


class RoundBox(BoxLayout):
    bg_color = ListProperty([0, 0, 0, 0])
    bg_texture = ObjectProperty(None, allownone=True)
    radius = NumericProperty(dp(22))
    zoom = NumericProperty(1.0)
    flip = NumericProperty(1.0)

    def pop_in(self, delay=0.0):
        """Entrata 3D: la scheda si "ribalta" verso lo schermo."""
        self.flip, self.opacity = 0.05, 0
        anim = Animation(flip=1, opacity=1, d=0.45, t="out_back")
        Clock.schedule_once(lambda *_: anim.start(self), delay)


class Tappable(ButtonBehavior, RoundBox):
    def on_press(self):
        Animation.cancel_all(self, "zoom")
        Animation(zoom=0.95, d=0.08).start(self)

    def on_release(self):
        vibrate()
        Animation.cancel_all(self, "zoom")
        Animation(zoom=1, d=0.25, t="out_back").start(self)

    def on_touch_up(self, touch):
        if self.zoom != 1 and not self.collide_point(*touch.pos):
            Animation(zoom=1, d=0.2).start(self)
        return super().on_touch_up(touch)


class Txt(Label):
    pass


class Icon(Label):
    pass


class IconBtn(Tappable):
    icon = StringProperty("")
    icon_color = ListProperty([])


class Chip(Tappable):
    text = StringProperty("")
    selected = BooleanProperty(False)
    color = ListProperty([])


class PrimaryButton(Tappable):
    text = StringProperty("")
    kind = StringProperty("primary")


class TopBar(BoxLayout):
    title = StringProperty("")
    left_icon = StringProperty("‹")
    right_icon = StringProperty("")
    __events__ = ("on_back_press", "on_action_press")

    def on_back_press(self):
        pass

    def on_action_press(self):
        pass


class Page(Screen):
    def refresh(self):
        pass

    def on_pre_enter(self, *_):
        self.refresh()


class NavTab(ButtonBehavior, BoxLayout):
    name = StringProperty("")
    icon = StringProperty("")
    label = StringProperty("")

    def on_release(self):
        vibrate()
        App.get_running_app().go_tab(self.name)


class BottomNav(FloatLayout):
    pass


class ServiceTile(Widget):
    """Riquadro colorato con l'iniziale del servizio (funziona offline)."""

    def __init__(self, name, color, size=dp(48), **kw):
        super().__init__(size_hint=(None, None), size=(size, size), **kw)
        from kivy.graphics import Color, RoundedRectangle
        c = hexc(color)
        lum = 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]
        with self.canvas:
            Color(*c)
            self._rr = RoundedRectangle(pos=self.pos, size=self.size, radius=[size * 0.3])
        words = name.split()
        initial = (words[0][0] + words[1][0]) if len(words) > 1 and len(name) > 12 else (name[:1] or "?")
        self.lbl = Label(text=initial.upper(), bold=True, font_size=size * 0.4, color=(0.05, 0.05, 0.1, 1) if lum > 0.68 else (1, 1, 1, 1))
        self.add_widget(self.lbl)
        self.bind(pos=self._upd, size=self._upd)

    def _upd(self, *_):
        self._rr.pos, self._rr.size = self.pos, self.size
        self.lbl.pos, self.lbl.size = self.pos, self.size


def hbox(*children, spacing=dp(12), height=None, padding=0):
    b = BoxLayout(orientation="horizontal", spacing=spacing, padding=padding)
    if height:
        b.size_hint_y, b.height = None, height
    for c in children:
        b.add_widget(c)
    return b


def vbox(*children, spacing=dp(2), padding=0):
    b = BoxLayout(orientation="vertical", spacing=spacing, size_hint_y=None, padding=padding)
    b.bind(minimum_height=b.setter("height"))
    for c in children:
        b.add_widget(c)
    return b


def txt(text, size=15, bold=False, color=None, halign="left", **kw):
    app = App.get_running_app()
    t = Txt(text=sym(text), markup=True, font_size=dp(size), bold=bold, halign=halign, **kw)
    t.color = color or app.c_text
    return t


def card(*children, padding=dp(16), spacing=dp(10), orientation="vertical", height=None, tap=None, bg=None):
    app = App.get_running_app()
    cls = Tappable if tap else RoundBox
    c = cls(orientation=orientation, padding=padding, spacing=spacing, size_hint_y=None)
    c.bg_color = bg or app.c_card
    if tap:
        c.bind(on_release=lambda *_: tap())
    if height:
        c.height = height
    else:
        c.bind(minimum_height=c.setter("height"))
    for ch in children:
        c.add_widget(ch)
    return c


def flow(children, spacing=dp(8)):
    """Righe che vanno a capo (per le chip)."""
    from kivy.uix.stacklayout import StackLayout
    s = StackLayout(size_hint_y=None, spacing=spacing)
    s.bind(minimum_height=s.setter("height"))
    for c in children:
        s.add_widget(c)
    return s


# ------------------------------------------------------------------ schermate

class SplashScreen(Page):
    def __init__(self, **kw):
        super().__init__(**kw)
        app = App.get_running_app()
        root = BoxLayout(orientation="vertical", padding=dp(28), spacing=dp(14))
        self.logo = Logo3D(size_hint=(1, 0.5), tilt=34)
        root.add_widget(self.logo)
        self.title = txt("maik subs", size=40, bold=True, halign="center")
        self.tag = txt("Tutti i tuoi abbonamenti, sotto controllo.", size=17, color=app.c_text2, halign="center")
        root.add_widget(self.title)
        root.add_widget(self.tag)
        self.points = vbox(
            txt("•  Totale al mese e all'anno in un colpo d'occhio", 15, color=app.c_text2, halign="center"),
            txt("•  Avvisi prima di ogni rinnovo e fine prova", 15, color=app.c_text2, halign="center"),
            txt("•  Niente banca, niente account: tutto sul telefono", 15, color=app.c_text2, halign="center"),
            spacing=dp(8))
        root.add_widget(self.points)
        root.add_widget(Widget())
        self.btn = PrimaryButton(text="Inizia")
        self.btn.bind(on_release=lambda *_: app.finish_onboarding())
        root.add_widget(self.btn)
        root.add_widget(txt("Creato da Maik", 13, color=app.c_text3, halign="center"))
        self.add_widget(root)

    def on_enter(self, *_):
        self.logo.spin(1)
        for i, w in enumerate((self.title, self.tag, self.points, self.btn)):
            w.opacity = 0
            Animation(opacity=1, d=0.5, t="out_quad").start(w) if i == 0 else Clock.schedule_once(
                lambda _dt, w=w: Animation(opacity=1, d=0.5).start(w), 0.15 * i)
        app = App.get_running_app()
        if app.store.settings["onboarded"]:
            self.btn.opacity = 0
            Clock.schedule_once(lambda *_: app.go_tab("home", transition=RiseInTransition(duration=0.45)), 1.5)


class HomeScreen(Page):
    shown_total = NumericProperty(0)
    period = StringProperty("month")

    def __init__(self, **kw):
        super().__init__(**kw)
        self.query = ""
        self.sort = "date"
        self.scroll = Builder.load_string("Scroller:")
        self.col = Builder.load_string("Column:")
        self.scroll.add_widget(self.col)
        self.add_widget(self.scroll)
        self.bind(shown_total=self._update_total)
        self.total_label = None

    def _update_total(self, *_):
        if self.total_label:
            self.total_label.text = S.money(self.shown_total, App.get_running_app().cur)

    def refresh(self):
        app = App.get_running_app()
        st = app.store
        col = self.col
        col.clear_widgets()
        today = date.today()

        # Intestazione con logo 3D
        logo = Logo3D(size_hint=(None, None), size=(dp(58), dp(58)), distance=4.0, tilt=30)
        head_text = vbox(txt("Ciao!", 20, True), txt("%s" % S.fmt_date(today, long=True).capitalize(), 13, color=app.c_text2))
        head = hbox(logo, head_text, height=dp(60))
        logo.bind(on_touch_down=lambda w, t: w.collide_point(*t.pos) and w.spin(1))
        if not st.settings["premium"]:
            pro = Chip(text="★ PRO", selected=True)
            pro.bind(on_release=lambda *_: app.push("premium"))
            head.add_widget(AnchorWrap(pro))
        col.add_widget(head)

        if not st.subs:
            col.add_widget(self._empty())
            return

        active = st.active()
        total = st.month_total()
        target = total if self.period == "month" else total * 12

        # Scheda principale con sfumatura
        hero = RoundBox(orientation="vertical", padding=dp(22), spacing=dp(12), size_hint_y=None, height=dp(210))
        hero.bg_color = [1, 1, 1, 1]
        hero.bg_texture = gradient_texture("#A88BFF", "#5B3DF5")
        hero.radius = dp(30)
        sw = hbox(height=dp(32), spacing=dp(6))
        sw.add_widget(txt("SPESA MENSILE" if self.period == "month" else "SPESA ANNUALE", 12, True, color=[1, 1, 1, 0.85]))
        for key, lab in (("month", "al mese"), ("year", "all'anno")):
            c = Chip(text=lab, selected=self.period == key, color=[1, 1, 1, 0.28])
            c.bg_color = [1, 1, 1, 0.28] if self.period == key else [1, 1, 1, 0.1]
            c.bind(on_release=lambda _c, k=key: self._set_period(k))
            sw.add_widget(c)
        hero.add_widget(sw)
        self.total_label = txt(S.money(self.shown_total, app.cur), 44, True, color=[1, 1, 1, 1])
        hero.add_widget(self.total_label)
        Animation.cancel_all(self, "shown_total")
        Animation(shown_total=target, d=0.9, t="out_cubic").start(self)
        stats = hbox(height=dp(44))
        for val, lab in ((S.money(total * 12 if self.period == "month" else total, app.cur),
                          "all'anno" if self.period == "month" else "al mese"),
                         (S.money(total / 30.436875, app.cur), "al giorno"), (str(len(active)), "attivi")):
            stats.add_widget(vbox(txt(val, 16, True, color=[1, 1, 1, 1]), txt(lab, 11, color=[1, 1, 1, 0.75])))
        hero.add_widget(stats)
        budget = st.settings.get("budget") or 0
        if budget:
            hero.height = dp(240)
            over = total > budget
            hero.add_widget(txt("Budget %s · %s" % (S.money(budget, app.cur, 0), ("sforato di " if over else "rimasti ") +
                                                   S.money(abs(budget - total), app.cur)), 13, color=[1, 1, 1, 0.9]))
        col.add_widget(hero)
        hero.pop_in()

        # Prossimo rinnovo
        upcoming = sorted(((S.next_renewal(s), s) for s in active), key=lambda x: x[0])
        if upcoming:
            nxt, s = upcoming[0]
            days = (nxt - today).days
            badge = RoundBox(orientation="vertical", size_hint=(None, None), size=(dp(70), dp(62)), padding=dp(4), radius=dp(18))
            badge.bg_color = app.c_danger_soft if days <= 3 else app.c_accent_soft
            badge.add_widget(txt("Oggi" if days == 0 else str(days), 26 if days else 18, True, halign="center",
                                 color=app.c_danger if days <= 3 else app.c_accent))
            if days:
                badge.add_widget(txt("giorno" if days == 1 else "giorni", 11, color=app.c_text2, halign="center"))
            info = vbox(txt("PROSSIMO RINNOVO", 11, True, color=app.c_text2), txt(s["name"], 18, True),
                        txt("%s · %s" % (S.money(s["price"], app.cur), S.fmt_date(nxt)), 13, color=app.c_text2))
            c = card(hbox(ServiceTile(s["name"], s["color"], dp(56)), info, AnchorWrap(badge), height=dp(66)),
                     tap=lambda s=s: app.open_detail(s["id"]))
            col.add_widget(c)
            c.pop_in(0.08)

        # In arrivo (scorrimento orizzontale)
        soon = [(d, s) for d, s in upcoming if (d - today).days <= 14]
        if len(soon) > 1:
            col.add_widget(txt("In arrivo", 18, True))
            sv = ScrollView(size_hint_y=None, height=dp(150), do_scroll_y=False, bar_width=0)
            row = BoxLayout(size_hint_x=None, spacing=dp(10))
            row.bind(minimum_width=row.setter("width"))
            for i, (d, s) in enumerate(soon[:8]):
                days = (d - today).days
                t = card(ServiceTile(s["name"], s["color"], dp(38)), txt(s["name"], 13, True, shorten=True),
                         txt(S.money(s["price"], app.cur), 16, True),
                         txt(S.days_text(days), 12, color=app.c_danger if days <= 3 else app.c_text2),
                         padding=dp(14), spacing=dp(4), height=dp(146), tap=lambda s=s: app.open_detail(s["id"]))
                t.size_hint_x, t.width = None, dp(124)
                row.add_widget(t)
                t.pop_in(0.1 + i * 0.05)
            sv.add_widget(row)
            col.add_widget(sv)

        saved = sum(S.saved_since_cancel(s) for s in st.inactive())
        if saved > 0.5:
            col.add_widget(card(txt("%s risparmiati" % S.money(saved, app.cur), 18, True, color=app.c_success),
                                txt("grazie agli abbonamenti disdetti", 13, color=app.c_text2), spacing=dp(2)))

        if not st.settings["premium"]:
            col.add_widget(card(txt("★  Passa a Premium", 16, True, color=app.c_accent),
                                txt("Abbonamenti illimitati, promemoria su misura e statistiche complete.", 13, color=app.c_text2),
                                spacing=dp(4), tap=lambda: app.push("premium"), bg=app.c_accent_soft))

        # Lista
        col.add_widget(txt("I tuoi abbonamenti", 18, True))
        search = Builder.load_string("Field:")
        search.hint_text = "Cerca un abbonamento"
        search.text = self.query
        search.bind(text=self._on_search)
        col.add_widget(search)
        sorts = []
        for key, lab in (("date", "Data"), ("price", "Prezzo"), ("name", "Nome")):
            c = Chip(text=lab, selected=self.sort == key)
            c.bind(on_release=lambda _c, k=key: self._set_sort(k))
            sorts.append(c)
        col.add_widget(flow(sorts))
        self.list_box = vbox(spacing=dp(10))
        col.add_widget(self.list_box)
        self._fill_list()

    def _fill_list(self, animate=True):
        app = App.get_running_app()
        st = app.store
        box = self.list_box
        box.clear_widgets()
        q = self.query.strip().lower()
        items = [s for s in st.active() if q in s["name"].lower()]
        key = {"date": lambda s: S.next_renewal(s), "price": lambda s: -S.monthly_cost(s),
               "name": lambda s: s["name"].lower()}[self.sort]
        items.sort(key=key)
        inactive = [s for s in st.inactive() if q in s["name"].lower()]
        for i, s in enumerate(items):
            row = sub_row(s)
            box.add_widget(row)
            if animate:
                row.pop_in(0.05 * min(i, 8))
        if inactive:
            box.add_widget(txt("Disdetti e in pausa", 16, True, color=app.c_text2))
            for s in inactive:
                box.add_widget(sub_row(s))
        if not items and not inactive:
            box.add_widget(txt("Nessun risultato", 15, color=app.c_text2, halign="center"))

    def _on_search(self, _w, value):
        self.query = value
        self._fill_list(animate=False)

    def _set_sort(self, key):
        self.sort = key
        self.refresh()

    def _set_period(self, key):
        self.period = key
        self.refresh()

    def _empty(self):
        app = App.get_running_app()
        b1 = PrimaryButton(text="+  Aggiungi abbonamento")
        b1.bind(on_release=lambda *_: app.open_add())
        b2 = PrimaryButton(text="Carica dati di esempio", kind="secondary")
        b2.bind(on_release=lambda *_: (app.store.load_sample(), self.refresh()))
        logo = Logo3D(size_hint_y=None, height=dp(170), tilt=40)
        c = card(logo, txt("Nessun abbonamento", 26, True, halign="center"),
                 txt("Aggiungi il primo in 3 tocchi e ti avviseremo prima di ogni rinnovo.", 15, color=app.c_text2, halign="center"),
                 b1, b2, padding=dp(24), spacing=dp(16))
        c.pop_in()
        return c


class AnchorWrap(BoxLayout):
    """Centra verticalmente un widget di dimensione fissa dentro una riga."""

    def __init__(self, child, **kw):
        from kivy.uix.anchorlayout import AnchorLayout
        super().__init__(size_hint_x=None, width=child.width, **kw)
        a = AnchorLayout(anchor_x="right", anchor_y="center")
        a.add_widget(child)
        self.add_widget(a)
        child.bind(width=lambda _w, v: setattr(self, "width", v))


def sub_row(s):
    app = App.get_running_app()
    today = date.today()
    nxt = S.next_renewal(s)
    if s["status"] == "paused":
        status, col = "In pausa", app.c_text3
    elif s["status"] == "cancelled":
        status, col = "Disdetto", app.c_text3
    else:
        days = (nxt - today).days
        status = S.days_text(days)
        col = app.c_danger if days <= 3 else (app.c_warning if S.is_trial(s) else app.c_text2)
    meta = S.cycle_label(s["unit"], s["every"]) + (" · %s" % S.fmt_date(nxt) if nxt else "")
    if S.is_trial(s):
        meta = "Prova · " + meta
    hist = s.get("history") or []
    if hist and hist[-1][1] < s["price"]:
        meta = "↑ aumentato · " + meta
    left = vbox(txt(s["name"], 16, True, shorten=True), txt(meta, 12, color=app.c_text2, shorten=True))
    right = vbox(txt(S.money(s["price"], app.cur), 16, True, halign="right"), txt(status, 12, True, color=col, halign="right"))
    right.size_hint_x, right.width = None, dp(110)
    c = card(hbox(ServiceTile(s["name"], s["color"]), left, right, height=dp(50)), padding=dp(14),
             tap=lambda: app.open_detail(s["id"]))
    if s["status"] != "active":
        c.opacity = 0.6
    return c


class AddScreen(Page):
    def __init__(self, **kw):
        super().__init__(**kw)
        app = App.get_running_app()
        root = BoxLayout(orientation="vertical")
        bar = TopBar(title="Nuovo abbonamento", left_icon="", right_icon="✕")
        bar.bind(on_action_press=lambda *_: app.back())
        root.add_widget(bar)
        pad = BoxLayout(size_hint_y=None, height=dp(60), padding=(dp(16), dp(4)))
        self.search = Builder.load_string("Field:")
        self.search.hint_text = "Cerca: Netflix, palestra, telefono…"
        self.search.bind(text=lambda *_: self.fill())
        pad.add_widget(self.search)
        root.add_widget(pad)
        self.scroll = Builder.load_string("Scroller:")
        self.col = Builder.load_string("Column:")
        self.col.padding = (dp(16), dp(8), dp(16), dp(40))
        self.scroll.add_widget(self.col)
        root.add_widget(self.scroll)
        self.add_widget(root)

    def refresh(self):
        self.search.text = ""
        self.fill()

    def fill(self):
        app = App.get_running_app()
        col = self.col
        col.clear_widgets()
        q = self.search.text.strip()
        custom = card(hbox(Label(text="✎", font_name="DejaVuSans", font_size=dp(24), color=app.c_accent, size_hint_x=None, width=dp(48)),
                           vbox(txt("Personalizzato: “%s”" % q if q else "Personalizzato", 16, True),
                                txt("Scrivi tu il nome", 13, color=app.c_text2)), height=dp(48)),
                      tap=lambda: app.open_form(name=q))
        col.add_widget(custom)
        if q:
            items = [s for s in S.CATALOG if q.lower() in s[1].lower()]
            col.add_widget(self._grid(items))
        else:
            col.add_widget(Builder.load_string("SectionLabel:\n    text: 'POPOLARI'"))
            col.add_widget(self._grid([S.find_service(i) for i in S.POPULAR]))
            for cat, (label, _c) in S.CATEGORIES.items():
                items = [s for s in S.CATALOG if s[3] == cat]
                if items:
                    sl = Builder.load_string("SectionLabel:")
                    sl.text = label.upper()
                    col.add_widget(sl)
                    col.add_widget(self._grid(items))

    def _grid(self, items):
        app = App.get_running_app()
        g = GridLayout(cols=4, spacing=dp(6), size_hint_y=None)
        g.bind(minimum_height=g.setter("height"))
        for i, s in enumerate(items):
            tile = Tappable(orientation="vertical", size_hint_y=None, height=dp(112), padding=(dp(2), dp(8)), spacing=dp(4))
            tile.bg_color = [0, 0, 0, 0]
            wrap = BoxLayout(size_hint_y=None, height=dp(58))
            wrap.add_widget(Widget())
            wrap.add_widget(ServiceTile(s[1], s[2], dp(58)))
            wrap.add_widget(Widget())
            tile.add_widget(wrap)
            tile.add_widget(txt(s[1], 11, True, halign="center", shorten=True))
            tile.add_widget(txt(S.money(s[4], app.cur), 11, color=app.c_text3, halign="center"))
            tile.bind(on_release=lambda _t, s=s: app.open_form(service=s))
            g.add_widget(tile)
            tile.zoom = 0.6
            tile.opacity = 0
            Animation(zoom=1, opacity=1, d=0.35, t="out_back").start(tile) if i < 16 else (setattr(tile, "zoom", 1), setattr(tile, "opacity", 1))
        return g


class FormScreen(Page):
    def __init__(self, **kw):
        super().__init__(**kw)
        app = App.get_running_app()
        self.editing = None
        self.service = None
        root = BoxLayout(orientation="vertical")
        self.bar = TopBar(title="Nuovo abbonamento", right_icon="✕")
        self.bar.bind(on_back_press=lambda *_: app.back(), on_action_press=lambda *_: app.go_tab("home", transition=FadeTransition(duration=0.2)))
        root.add_widget(self.bar)
        self.scroll = Builder.load_string("Scroller:")
        self.col = Builder.load_string("Column:")
        self.col.padding = (dp(16), dp(8), dp(16), dp(40))
        self.scroll.add_widget(self.col)
        root.add_widget(self.scroll)
        foot = BoxLayout(size_hint_y=None, height=dp(84), padding=(dp(16), dp(12), dp(16), dp(16)))
        self.save_btn = PrimaryButton(text="✓  Salva")
        self.save_btn.bind(on_release=lambda *_: self.save())
        foot.add_widget(self.save_btn)
        root.add_widget(foot)
        self.add_widget(root)

    def setup(self, service=None, editing=None, name=""):
        app = App.get_running_app()
        self.service, self.editing = service, editing
        if editing:
            e = editing
            self.state = dict(name=e["name"], price=("%.2f" % e["price"]).replace(".", ","), unit=e["unit"], every=e["every"],
                              start=e["start"], trial=e.get("trial", False), reminders=list(e.get("reminders", [3])),
                              category=e["category"], color=e["color"], notes=e.get("notes", ""))
        elif service:
            sid, sname, color, cat, price, unit, every = service
            self.state = dict(name=sname, price=("%.2f" % price).replace(".", ","), unit=unit, every=every,
                              start=date.today().isoformat(), trial=False,
                              reminders=[app.store.settings["default_reminder"]], category=cat, color=color, notes="")
        else:
            self.state = dict(name=name, price="", unit="month", every=1, start=date.today().isoformat(), trial=False,
                              reminders=[app.store.settings["default_reminder"]], category="other", color=ACCENT, notes="")
        self.bar.title = "Modifica" if editing else "Nuovo abbonamento"
        self.bar.left_icon = "‹"
        self.save_btn.text = "✓  Salva modifiche" if editing else "✓  Salva"

    def refresh(self):
        self.build_form()

    def build_form(self):
        app = App.get_running_app()
        st = self.state
        col = self.col
        col.clear_widgets()

        def label(text):
            sl = Builder.load_string("SectionLabel:")
            sl.text = text
            return sl

        self.tile_holder = BoxLayout(size_hint=(None, None), size=(dp(72), dp(72)))
        self.tile_holder.add_widget(ServiceTile(st["name"] or "?", st["color"], dp(72)))
        name = Builder.load_string("Field:")
        name.text, name.hint_text = st["name"], "Es. Palestra"
        name.bind(text=lambda _w, v: st.__setitem__("name", v))
        col.add_widget(hbox(self.tile_holder, vbox(label("NOME"), name, spacing=dp(6)), height=dp(84)))

        col.add_widget(label("PREZZO (%s)" % app.cur))
        price = Builder.load_string("Field:")
        price.height, price.font_size, price.bold = dp(76), dp(34), True
        price.text, price.hint_text = st["price"], "0,00"
        price.input_filter = lambda s, _undo: "".join(c for c in s if c.isdigit() or c in ",.")
        price.bind(text=lambda _w, v: st.__setitem__("price", v))
        col.add_widget(price)
        if self.service and not self.editing:
            col.add_widget(txt("Prezzo indicativo, modificalo se serve", 12, color=app.c_text3))

        col.add_widget(label("FREQUENZA"))
        chips = []
        for unit, every, lab in S.CYCLES:
            c = Chip(text=lab, selected=st["unit"] == unit and st["every"] == every)
            c.bind(on_release=lambda _c, u=unit, e=every: (st.update(unit=u, every=e), self.build_form()))
            chips.append(c)
        col.add_widget(flow(chips))

        col.add_widget(label("FINE PROVA" if st["trial"] else "PRIMO PAGAMENTO"))
        d = S.parse_date(st["start"])
        date_btn = card(txt("▦   " + S.fmt_date(d, long=True).capitalize(), 16, True), padding=dp(16),
                        tap=lambda: DatePopup(d, self._set_date).open())
        col.add_widget(date_btn)
        trial = Chip(text="✓ Prova gratuita" if st["trial"] else "Prova gratuita", selected=st["trial"], color=app.c_warning)
        trial.bind(on_release=lambda *_: (st.update(trial=not st["trial"]), self.build_form()))
        col.add_widget(flow([trial]))

        col.add_widget(label("PROMEMORIA"))
        rem = []
        premium = app.store.settings["premium"]
        for days in (0, 1, 3, 7, 14):
            lab = "Il giorno stesso" if days == 0 else ("%d giorno prima" % days if days == 1 else "%d giorni prima" % days)
            c = Chip(text=lab, selected=days in st["reminders"])
            c.bind(on_release=lambda _c, dd=days: self._toggle_rem(dd))
            rem.append(c)
        col.add_widget(flow(rem))
        if not premium:
            col.add_widget(txt("★ Con Premium puoi scegliere più promemoria per lo stesso rinnovo.", 12, color=app.c_text3))

        col.add_widget(label("CATEGORIA"))
        cats = []
        for key, (lab, color) in S.CATEGORIES.items():
            c = Chip(text=lab, selected=st["category"] == key, color=hexc(color))
            c.bind(on_release=lambda _c, k=key: (st.update(category=k), self.build_form()))
            cats.append(c)
        col.add_widget(flow(cats))

        col.add_widget(label("NOTE"))
        notes = Builder.load_string("Field:")
        notes.text, notes.hint_text = st["notes"], "Piano, email dell'account, codice cliente…"
        notes.bind(text=lambda _w, v: st.__setitem__("notes", v))
        col.add_widget(notes)

    def _toggle_rem(self, days):
        app = App.get_running_app()
        r = self.state["reminders"]
        if not app.store.settings["premium"]:
            self.state["reminders"] = [] if days in r else [days]
        elif days in r:
            r.remove(days)
        else:
            r.append(days)
            r.sort()
        self.build_form()

    def _set_date(self, d):
        self.state["start"] = d.isoformat()
        self.build_form()

    def save(self):
        app = App.get_running_app()
        st = self.state
        price = S.parse_price(st["price"])
        if not st["name"].strip():
            app.toast("Inserisci un nome")
            return
        if price is None:
            app.toast("Inserisci un prezzo valido")
            return
        data = dict(name=st["name"].strip()[:60], price=round(price, 2), unit=st["unit"], every=st["every"], start=st["start"],
                    trial=st["trial"], reminders=st["reminders"], category=st["category"], color=st["color"],
                    notes=st["notes"].strip())
        if self.editing:
            app.store.update(self.editing["id"], **data)
            app.toast("Modifiche salvate ✓")
            app.open_detail(self.editing["id"], replace=True)
            return
        if not app.store.can_add():
            app.push("premium")
            return
        data.update(id=S.new_id(), service=self.service[0] if self.service else None, status="active",
                    status_date=None, history=[])
        app.store.add(data)
        app.toast("%s · %s ✓" % (data["name"], S.money(data["price"], app.cur)))
        app.go_tab("home", transition=FadeTransition(duration=0.25))


class DatePopup(ModalView):
    def __init__(self, current, on_pick, **kw):
        super().__init__(size_hint=(0.92, None), height=dp(470), background_color=(0, 0, 0, 0.45), background="", **kw)
        app = App.get_running_app()
        self.on_pick = on_pick
        self.selected = current
        self.month = current.replace(day=1)
        self.box = card(padding=dp(18), spacing=dp(10), height=dp(470))
        self.add_widget(self.box)
        self.app = app
        self.build()

    def build(self):
        self.box.clear_widgets()
        self.box.add_widget(month_header(self.month, self._move))
        self.box.add_widget(month_grid(self.month, self.selected, self._select))
        ok = PrimaryButton(text="Fatto")
        ok.bind(on_release=lambda *_: (self.on_pick(self.selected), self.dismiss()))
        self.box.add_widget(ok)

    def _move(self, n):
        self.month = S.add_months(self.month, n, 1)
        self.build()

    def _select(self, d):
        self.selected = d
        self.build()


def month_header(month, on_move):
    app = App.get_running_app()
    prev = IconBtn(icon="‹")
    prev.bind(on_release=lambda *_: on_move(-1))
    nxt = IconBtn(icon="›")
    nxt.bind(on_release=lambda *_: on_move(1))
    title = Label(text="%s %d" % (S.MONTHS_LONG[month.month - 1].capitalize(), month.year), bold=True, font_size=dp(18), color=app.c_text)
    return hbox(prev, title, nxt, height=dp(44))


def month_grid(month, selected, on_select, marks=None):
    app = App.get_running_app()
    g = GridLayout(cols=7, size_hint_y=None, spacing=dp(2))
    g.bind(minimum_height=g.setter("height"))
    for w in "LMMGVSD":
        g.add_widget(Label(text=w, color=app.c_text3, bold=True, font_size=dp(11), size_hint_y=None, height=dp(22)))
    lead = month.weekday()
    for _ in range(lead):
        g.add_widget(Widget(size_hint_y=None, height=dp(44)))
    days = (S.add_months(month, 1, 1) - timedelta(days=1)).day
    today = date.today()
    for n in range(1, days + 1):
        d = month.replace(day=n)
        sel = selected == d
        cell = Tappable(orientation="vertical", size_hint_y=None, height=dp(44), radius=dp(14), padding=(0, dp(4)))
        cell.bg_color = app.c_accent if sel else (app.c_accent_soft if d == today else [0, 0, 0, 0])
        cell.add_widget(Label(text=str(n), bold=sel or d == today, color=[1, 1, 1, 1] if sel else app.c_text, font_size=dp(15)))
        dots = BoxLayout(size_hint_y=None, height=dp(6), spacing=dp(2))
        cols = (marks or {}).get(d.isoformat(), [])
        if cols:
            dots.add_widget(Widget())
            for c in cols[:3]:
                dot = RoundBox(size_hint=(None, None), size=(dp(5), dp(5)), radius=dp(2.5))
                dot.bg_color = [1, 1, 1, 1] if sel else hexc(c)
                dots.add_widget(dot)
            dots.add_widget(Widget())
        cell.add_widget(dots)
        cell.bind(on_release=lambda _c, d=d: on_select(d))
        g.add_widget(cell)
    return g


class DetailScreen(Page):
    sub_id = StringProperty("")

    def __init__(self, **kw):
        super().__init__(**kw)
        app = App.get_running_app()
        root = BoxLayout(orientation="vertical")
        bar = TopBar(title="", right_icon="✎")
        bar.bind(on_back_press=lambda *_: app.back(), on_action_press=lambda *_: app.open_form(editing=app.store.get(self.sub_id)))
        root.add_widget(bar)
        self.scroll = Builder.load_string("Scroller:")
        self.col = Builder.load_string("Column:")
        self.col.padding = (dp(16), dp(4), dp(16), dp(40))
        self.scroll.add_widget(self.col)
        root.add_widget(self.scroll)
        self.add_widget(root)

    def refresh(self):
        app = App.get_running_app()
        s = app.store.get(self.sub_id)
        col = self.col
        col.clear_widgets()
        if not s:
            col.add_widget(txt("Abbonamento non trovato", 18, True, halign="center"))
            return
        cur = app.cur
        tile_row = BoxLayout(size_hint_y=None, height=dp(96))
        tile_row.add_widget(Widget())
        tile = ServiceTile(s["name"], s["color"], dp(92))
        tile_row.add_widget(tile)
        tile_row.add_widget(Widget())
        col.add_widget(tile_row)
        cat = S.CATEGORIES.get(s["category"], S.CATEGORIES["other"])[0]
        badges = [cat]
        if S.is_trial(s):
            badges.append("Prova gratuita")
        if s["status"] == "paused":
            badges.append("In pausa")
        if s["status"] == "cancelled":
            badges.append("Disdetto")
        col.add_widget(txt(s["name"], 28, True, halign="center"))
        col.add_widget(txt(" · ".join(badges), 13, True, color=app.c_text2, halign="center"))
        price = txt(S.money(s["price"], cur), 44, True, halign="center")
        col.add_widget(price)
        col.add_widget(txt(S.cycle_label(s["unit"], s["every"]), 15, color=app.c_text2, halign="center"))
        price.opacity = 0
        Animation(opacity=1, d=0.5).start(price)

        mc = S.monthly_cost(s)
        g = GridLayout(cols=2, spacing=dp(10), size_hint_y=None, height=dp(160))
        last = ("Risparmiati", S.money(S.saved_since_cancel(s), cur)) if s["status"] == "cancelled" else ("Al giorno", S.money(mc / 30.436875, cur))
        for i, (lab, val) in enumerate((("Al mese", S.money(mc, cur)), ("All'anno", S.money(mc * 12, cur)),
                                         ("Speso finora", S.money(S.spent_so_far(s), cur)), last)):
            k = card(txt(lab, 12, color=app.c_text2), txt(val, 19, True), height=dp(75), spacing=dp(2))
            g.add_widget(k)
            k.pop_in(0.06 * i)
        col.add_widget(g)

        ups = S.upcoming(s, 5)
        if ups:
            rows = [txt("Prossimi rinnovi", 18, True)]
            for i, d in enumerate(ups):
                badge = RoundBox(orientation="vertical", size_hint=(None, None), size=(dp(50), dp(50)), radius=dp(14), padding=dp(4))
                badge.bg_color = app.c_accent if i == 0 else app.c_card2
                badge.add_widget(txt(str(d.day), 17, True, halign="center", color=[1, 1, 1, 1] if i == 0 else app.c_text))
                badge.add_widget(txt(S.MONTHS_SHORT[d.month - 1].upper(), 10, color=[1, 1, 1, 0.9] if i == 0 else app.c_text2, halign="center"))
                rows.append(hbox(badge, vbox(txt(S.WEEKDAYS[d.weekday()].capitalize(), 15, True),
                                             txt(S.days_text((d - date.today()).days), 12, color=app.c_text2)),
                                 txt(S.money(s["price"], cur), 15, True, halign="right"), height=dp(54)))
            col.add_widget(card(*rows))

        info = [txt("Dettagli", 18, True),
                txt("%s:  %s" % ("Fine prova" if s.get("trial") else "Primo pagamento", S.fmt_date(S.parse_date(s["start"]), True)), 14),
                txt("Promemoria:  %s" % (", ".join("%d g prima" % r for r in s.get("reminders", [])) or "nessuno"), 14)]
        if s.get("notes"):
            info.append(txt("Note:  " + s["notes"], 14))
        for d_, p in reversed(s.get("history", [])):
            info.append(txt("Prezzo cambiato il %s (prima %s)" % (S.fmt_date(S.parse_date(d_), True), S.money(p, cur)), 13, color=app.c_danger))
        col.add_widget(card(*info, spacing=dp(8)))

        def act(text, kind, fn):
            b = PrimaryButton(text=text, kind=kind)
            b.bind(on_release=lambda *_: fn())
            col.add_widget(b)

        if s["status"] == "active":
            act("❚❚  Metti in pausa", "secondary", lambda: self._status("paused"))
            act("✕  Segna come disdetto", "secondary", lambda: self._status("cancelled"))
        else:
            act("▶  Riattiva", "primary", lambda: self._status("active"))
        act("Elimina", "danger", self._delete)

    def _status(self, status):
        app = App.get_running_app()
        s = app.store.get(self.sub_id)
        if status == "active":
            app.store.update(self.sub_id, status="active", status_date=None, start=date.today().isoformat())
        else:
            app.store.update(self.sub_id, status=status, status_date=date.today().isoformat())
        app.toast({"active": "Riattivato", "paused": "Messo in pausa", "cancelled": "Segnato come disdetto"}[status])
        self.refresh()

    def _delete(self):
        app = App.get_running_app()
        s = app.store.get(self.sub_id)
        confirm(app, "Eliminare %s?" % s["name"], "Verranno rimossi anche i promemoria.", "Elimina", lambda: self._do_delete())

    def _do_delete(self):
        app = App.get_running_app()
        index = app.store.subs.index(app.store.get(self.sub_id))
        removed = app.store.remove(self.sub_id)
        app.go_tab("home", transition=FadeTransition(duration=0.2))

        def undo():
            app.store.subs.insert(index, removed)
            app.store.save()
            app.screens["home"].refresh()

        app.toast("%s eliminato" % removed["name"], action="Annulla", on_action=undo)


def confirm(app, title, body, ok_text, on_ok):
    m = ModalView(size_hint=(0.88, None), height=dp(250), background="", background_color=(0, 0, 0, 0.45))
    ok = PrimaryButton(text=ok_text, kind="danger")
    cancel = PrimaryButton(text="Annulla", kind="secondary")
    ok.bind(on_release=lambda *_: (m.dismiss(), on_ok()))
    cancel.bind(on_release=lambda *_: m.dismiss())
    m.add_widget(card(txt(title, 20, True), txt(body, 14, color=app.c_text2), ok, cancel, padding=dp(20), spacing=dp(12), height=dp(250)))
    m.open()


class CalendarScreen(Page):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.month = date.today().replace(day=1)
        self.selected = date.today()
        self.scroll = Builder.load_string("Scroller:")
        self.col = Builder.load_string("Column:")
        self.scroll.add_widget(self.col)
        self.add_widget(self.scroll)

    def refresh(self):
        app = App.get_running_app()
        col = self.col
        col.clear_widgets()
        col.add_widget(txt("Calendario", 30, True))
        end = S.add_months(self.month, 1, 1) - timedelta(days=1)
        marks, by_day, total = {}, {}, 0.0
        for s in app.store.subs:
            for d in S.charges_between(s, self.month, end):
                marks.setdefault(d.isoformat(), []).append(s["color"])
                by_day.setdefault(d.isoformat(), []).append(s)
                total += s["price"]
        c = card(month_header(self.month, self._move), month_grid(self.month, self.selected, self._select, marks),
                 hbox(txt("Totale del mese", 15, color=app.c_text2), txt(S.money(total, app.cur), 18, True, halign="right"), height=dp(40)))
        col.add_widget(c)
        c.pop_in()
        title = "Oggi" if self.selected == date.today() else S.fmt_date(self.selected, True).capitalize()
        col.add_widget(txt(title, 18, True))
        items = by_day.get(self.selected.isoformat(), [])
        if not items:
            col.add_widget(txt("Nessun rinnovo in questo giorno", 15, color=app.c_text2))
        for i, s in enumerate(items):
            r = card(hbox(ServiceTile(s["name"], s["color"], dp(44)), vbox(txt(s["name"], 16, True), txt(S.cycle_label(s["unit"], s["every"]), 12, color=app.c_text2)),
                          txt(S.money(s["price"], app.cur), 18, True, halign="right"), height=dp(46)),
                     tap=lambda s=s: app.open_detail(s["id"]))
            col.add_widget(r)
            r.pop_in(0.05 * i)

    def _move(self, n):
        self.month = S.add_months(self.month, n, 1)
        self.refresh()

    def _select(self, d):
        self.selected = d
        self.refresh()


class Bar(RoundBox):
    """Barra del grafico che cresce con un'animazione."""

    level = NumericProperty(0)


class StatsScreen(Page):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.past = False
        self.scroll = Builder.load_string("Scroller:")
        self.col = Builder.load_string("Column:")
        self.scroll.add_widget(self.col)
        self.add_widget(self.scroll)
        self.donut = Donut3D(size_hint_y=None, height=dp(250))

    def refresh(self):
        app = App.get_running_app()
        st = app.store
        col = self.col
        col.clear_widgets()
        col.add_widget(txt("Statistiche", 30, True))
        active = st.active()
        if not active:
            col.add_widget(card(txt("Aggiungi qualche abbonamento per vedere le statistiche.", 15, color=app.c_text2, halign="center"), padding=dp(30)))
            return
        total = st.month_total()
        g = GridLayout(cols=2, spacing=dp(10), size_hint_y=None, height=dp(180))
        for i, (lab, val) in enumerate((("Spesa mensile", S.money(total, app.cur)), ("Spesa annuale", S.money(total * 12, app.cur)),
                                         ("Costo al giorno", S.money(total / 30.436875, app.cur)), ("Media", S.money(total / len(active), app.cur)))):
            k = card(txt(lab, 12, color=app.c_text2), txt(val, 22 if i < 2 else 18, True, shorten=True), height=dp(85), spacing=dp(2))
            g.add_widget(k)
            k.pop_in(0.05 * i)
        col.add_widget(g)

        cats = st.by_category()
        if self.donut.parent:
            self.donut.parent.remove_widget(self.donut)
        self.donut.data = [(v, S.CATEGORIES.get(k, S.CATEGORIES["other"])[1]) for k, v in cats]
        legend = [txt("Per categoria", 18, True), self.donut,
                  txt("%s al mese" % S.money(total, app.cur), 20, True, halign="center")]
        for key, v in cats:
            label, color = S.CATEGORIES.get(key, S.CATEGORIES["other"])
            pct = v / total if total else 0
            dot = RoundBox(size_hint=(None, None), size=(dp(14), dp(14)), radius=dp(7))
            dot.bg_color = hexc(color)
            legend.append(hbox(AnchorWrap(dot), txt(label, 15, True), txt("%d%%" % round(pct * 100), 13, color=app.c_text2, halign="right"),
                               txt(S.money(v, app.cur), 15, True, halign="right"), height=dp(30)))
        col.add_widget(card(*legend, spacing=dp(8)))

        head = hbox(txt("Andamento", 18, True), height=dp(38))
        for past, lab in ((False, "Prossimi 12"), (True, "Ultimi 12")):
            c = Chip(text=lab, selected=self.past == past)
            c.bind(on_release=lambda _c, p=past: self._set_past(p))
            head.add_widget(AnchorWrap(c))
        months = st.months_forecast(past=self.past)
        mx = max([v for _, v in months] + [1])
        bars = BoxLayout(size_hint_y=None, height=dp(160), spacing=dp(5))
        labels = BoxLayout(size_hint_y=None, height=dp(18), spacing=dp(5))
        for i, (lab, v) in enumerate(months):
            holder = BoxLayout(orientation="vertical")
            holder.add_widget(Widget())
            b = Bar(size_hint_y=None, height=dp(3), radius=dp(6))
            highlight = (i == 0 and not self.past) or (i == 11 and self.past)
            b.bg_color = app.c_accent if highlight else app.c_accent_soft
            holder.add_widget(b)
            bars.add_widget(holder)
            Clock.schedule_once(lambda _dt, b=b, h=max(dp(4), dp(150) * v / mx): Animation(height=h, d=0.6, t="out_back").start(b), 0.03 * i)
            labels.add_widget(Label(text=lab, font_size=dp(10), color=app.c_text3))
        col.add_widget(card(head, bars, labels, txt("Totale: %s" % S.money(sum(v for _, v in months), app.cur), 13, color=app.c_text2)))

        top = sorted(active, key=lambda s: -S.monthly_cost(s))[:5]
        rows = [txt("I più costosi", 18, True)]
        for i, s in enumerate(top):
            rows.append(hbox(txt(str(i + 1), 15, True, color=app.c_text3, size_hint_x=None, width=dp(18)),
                             ServiceTile(s["name"], s["color"], dp(36)), txt(s["name"], 15, True, shorten=True),
                             txt(S.money(S.monthly_cost(s), app.cur) + "/m", 15, True, halign="right"), height=dp(40)))
        col.add_widget(card(*rows))

        tips = []
        if top:
            tips.append("%s pesa il %d%% della tua spesa mensile." % (top[0]["name"], round(S.monthly_cost(top[0]) / total * 100)))
        trials = [s for s in active if S.is_trial(s)]
        if trials:
            tips.append("Hai %d prove gratuite attive: ricordati di disdire quelle che non usi." % len(trials))
        big = [s for s in active if s["unit"] == "month" and s["every"] == 1 and s["price"] >= 9]
        if big:
            tips.append("Passando %s al piano annuale potresti risparmiare circa il 15-20%%." % max(big, key=lambda s: s["price"])["name"])
        if tips:
            shown = tips if st.settings["premium"] else tips[:1]
            items = [txt("Consigli", 18, True)] + [txt("•  " + t_, 14) for t_ in shown]
            if len(shown) < len(tips):
                items.append(txt("★ Altri %d consigli con Premium" % (len(tips) - len(shown)), 14, True, color=app.c_accent))
            col.add_widget(card(*items, spacing=dp(8)))

    def _set_past(self, past):
        self.past = past
        self.refresh()


class PremiumScreen(Page):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.plan = "yearly"
        self.scroll = Builder.load_string("Scroller:")
        self.col = Builder.load_string("Column:")
        self.col.padding = (dp(16), dp(8), dp(16), dp(40))
        self.scroll.add_widget(self.col)
        root = BoxLayout(orientation="vertical")
        bar = TopBar(title="Premium", left_icon="", right_icon="✕")
        bar.bind(on_action_press=lambda *_: App.get_running_app().back())
        root.add_widget(bar)
        root.add_widget(self.scroll)
        self.add_widget(root)
        self.logo = Logo3D(size_hint_y=None, height=dp(200), tilt=40, speed=1.3)

    def refresh(self):
        app = App.get_running_app()
        col = self.col
        col.clear_widgets()
        if self.logo.parent:
            self.logo.parent.remove_widget(self.logo)
        col.add_widget(self.logo)
        self.logo.spin(2)
        col.add_widget(txt("Maik Subs Premium", 30, True, halign="center"))
        limit_hit = not app.store.can_add()
        col.add_widget(txt("Hai raggiunto il limite di %d abbonamenti della versione gratuita." % S.FREE_LIMIT if limit_hit
                           else "Il massimo controllo sulle tue spese ricorrenti.", 15, color=app.c_text2, halign="center"))
        feats = [("∞", "Abbonamenti illimitati", "La versione gratuita ne include fino a %d." % S.FREE_LIMIT),
                 ("◷", "Promemoria personalizzati", "Più avvisi per lo stesso rinnovo."),
                 ("◕", "Statistiche complete", "Storico di 12 mesi e consigli di risparmio."),
                 ("☺", "Famiglia", "Dividi i costi con chi condivide l'abbonamento.")]
        for i, (ic, t_, b_) in enumerate(feats):
            icon = Label(text=ic, font_name="DejaVuSans", font_size=dp(22), color=app.c_accent, size_hint_x=None, width=dp(44))
            r = card(hbox(icon, vbox(txt(t_, 15, True), txt(b_, 13, color=app.c_text2)), height=dp(44)), padding=dp(12))
            col.add_widget(r)
            r.pop_in(0.1 + 0.07 * i)
        if app.store.settings["premium"]:
            col.add_widget(card(txt("✓  Premium attivo. Grazie!", 18, True, color=app.c_accent, halign="center"), bg=app.c_accent_soft))
            off = PrimaryButton(text="Demo: disattiva Premium", kind="secondary")
            off.bind(on_release=lambda *_: self._set(False))
            col.add_widget(off)
            return
        for key, lab, price, note in (("monthly", "Mensile", "2,99 €", ""), ("yearly", "Annuale", "19,99 €", "1,67 € al mese · più conveniente"),
                                      ("lifetime", "A vita", "49,99 €", "")):
            sel = self.plan == key
            items = [txt(("◉  " if sel else "○  ") + lab, 16, True, color=app.c_accent if sel else app.c_text)]
            if note:
                items.append(txt(note, 12, color=app.c_text2))
            c = card(hbox(vbox(*items), txt(price, 18, True, halign="right"), height=dp(44)), padding=dp(14),
                     tap=lambda k=key: self._pick(k), bg=app.c_accent_soft if sel else app.c_card)
            col.add_widget(c)
        buy = PrimaryButton(text="★  Continua")
        buy.bind(on_release=lambda *_: self._set(True))
        col.add_widget(buy)
        col.add_widget(txt("Versione demo: il pulsante attiva Premium senza pagamento. Per incassare davvero serve "
                           "Google Play Billing (vedi README).", 12, color=app.c_text3, halign="center"))

    def _pick(self, key):
        self.plan = key
        self.refresh()

    def _set(self, value):
        app = App.get_running_app()
        app.store.settings["premium"] = value
        app.store.save()
        if value:
            self.logo.spin(3)
            app.toast("Premium attivo ★")
        self.refresh()


class SettingsScreen(Page):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.scroll = Builder.load_string("Scroller:")
        self.col = Builder.load_string("Column:")
        self.scroll.add_widget(self.col)
        self.add_widget(self.scroll)

    def refresh(self):
        app = App.get_running_app()
        st = app.store.settings
        col = self.col
        col.clear_widgets()
        col.add_widget(txt("Profilo", 30, True))
        prem = card(txt("★  " + ("Premium attivo" if st["premium"] else "Passa a Premium"), 18, True, color=app.c_accent),
                    txt("Abbonamenti illimitati, promemoria su misura e statistiche complete.", 13, color=app.c_text2),
                    tap=lambda: app.push("premium"), bg=app.c_accent_soft, spacing=dp(4))
        col.add_widget(prem)

        def section(title, *children):
            sl = Builder.load_string("SectionLabel:")
            sl.text = title
            col.add_widget(sl)
            col.add_widget(card(*children, spacing=dp(12)))

        themes = []
        for dark, lab in ((False, "Chiaro"), (True, "Scuro")):
            c = Chip(text=lab, selected=st["dark"] == dark)
            c.bind(on_release=lambda _c, d=dark: app.set_dark(d))
            themes.append(c)
        currencies = []
        for code in S.CURRENCIES:
            c = Chip(text=code, selected=st["currency"] == code)
            c.bind(on_release=lambda _c, k=code: (st.update(currency=k), app.store.save(), self.refresh()))
            currencies.append(c)
        budget = Builder.load_string("Field:")
        budget.hint_text = "Budget mensile (vuoto = nessuno)"
        budget.text = ("%.2f" % st["budget"]).replace(".", ",") if st.get("budget") else ""
        budget.input_filter = lambda s, _u: "".join(ch for ch in s if ch.isdigit() or ch in ",.")

        def save_budget(w, focus):
            if not focus:
                v = S.parse_price(w.text)
                st["budget"] = v if v and v > 0 else 0.0
                app.store.save()

        budget.bind(focus=save_budget)
        section("ASPETTO E VALUTA", txt("Tema", 15, True), flow(themes), txt("Valuta", 15, True), flow(currencies),
                txt("Budget mensile", 15, True), budget)

        rems = []
        for days in (0, 1, 3, 7):
            c = Chip(text="Stesso giorno" if days == 0 else "%d g prima" % days, selected=st["default_reminder"] == days)
            c.bind(on_release=lambda _c, d=days: (st.update(default_reminder=d), app.store.save(), self.refresh()))
            rems.append(c)
        notif = Chip(text="✓ Attive" if st["notifications"] else "Disattivate", selected=st["notifications"])
        notif.bind(on_release=lambda *_: (st.update(notifications=not st["notifications"]), app.store.save(), self.refresh()))
        test = PrimaryButton(text="Invia notifica di prova", kind="secondary")
        test.bind(on_release=lambda *_: app.notify("Netflix si rinnova tra 3 giorni", "13,99 € · Mensile"))
        section("NOTIFICHE", txt("Promemoria rinnovi", 15, True), flow([notif]), txt("Promemoria predefinito", 15, True),
                flow(rems), test)

        sample = PrimaryButton(text="Carica dati di esempio", kind="secondary")
        sample.bind(on_release=lambda *_: (app.store.load_sample(), app.toast("Dati di esempio caricati")))
        reset = PrimaryButton(text="Cancella tutti i dati", kind="danger")
        reset.bind(on_release=lambda *_: confirm(app, "Cancellare tutto?", "L'operazione non si può annullare.", "Cancella",
                                                 lambda: (app.store.reset(), app.toast("Dati cancellati"))))
        section("DATI", txt("I dati restano sul telefono: niente banca, niente account.", 14, color=app.c_text2), sample, reset)

        logo = Logo3D(size_hint_y=None, height=dp(130), tilt=45)
        col.add_widget(card(logo, txt("maik subs", 24, True, halign="center"), txt("Creato da Maik", 14, color=app.c_text2, halign="center"),
                            txt("Versione 1.0 · © %d Maik" % date.today().year, 12, color=app.c_text3, halign="center"), padding=dp(20)))


# ------------------------------------------------------------------ app

class MaikSubsApp(App):
    title = "Maik Subs"
    c_bg = ListProperty()
    c_card = ListProperty()
    c_card2 = ListProperty()
    c_text = ListProperty()
    c_text2 = ListProperty()
    c_text3 = ListProperty()
    c_nav = ListProperty()
    c_accent = ListProperty(hexc(ACCENT))
    c_accent_soft = ListProperty(hexc(ACCENT, 0.14))
    c_danger = ListProperty(hexc("#F0384E"))
    c_danger_soft = ListProperty(hexc("#F0384E", 0.12))
    c_success = ListProperty(hexc("#14B371"))
    c_warning = ListProperty(hexc("#F59E0B"))
    current_tab = StringProperty("home")

    TABS = ("home", "calendar", "stats", "settings")

    def sym(self, text):
        return sym(text)

    @property
    def cur(self):
        return self.store.settings["currency"]

    def apply_theme(self):
        t = THEMES[bool(self.store.settings["dark"])]
        for k, v in t.items():
            setattr(self, "c_" + k, hexc(v))
        Window.clearcolor = hexc(t["bg"])

    def build(self):
        self.store = S.Store(self.user_data_dir)
        self.apply_theme()
        Builder.load_string(KV)
        self.history = []
        root = FloatLayout()
        self.sm = ScreenManager(transition=NoTransition())
        self.screens = {
            "splash": SplashScreen(name="splash"), "home": HomeScreen(name="home"), "calendar": CalendarScreen(name="calendar"),
            "stats": StatsScreen(name="stats"), "settings": SettingsScreen(name="settings"), "add": AddScreen(name="add"),
            "form": FormScreen(name="form"), "detail": DetailScreen(name="detail"), "premium": PremiumScreen(name="premium"),
        }
        for sc in self.screens.values():
            self.sm.add_widget(sc)
        root.add_widget(self.sm)
        self.nav = BottomNav()
        root.add_widget(self.nav)
        self.toast_box = None
        self.root_layout = root
        self.sm.current = "splash"
        self._show_nav(False)
        Window.bind(on_keyboard=self._on_key)
        Window.softinput_mode = "below_target"
        Clock.schedule_once(lambda *_: self.check_reminders(), 2.5)
        return root

    # --- navigazione
    def _show_nav(self, show):
        Animation.cancel_all(self.nav)
        Animation(y=0 if show else -dp(120), opacity=1 if show else 0, d=0.3, t="out_cubic").start(self.nav)

    def go_tab(self, name, transition=None):
        old = self.TABS.index(self.current_tab) if self.current_tab in self.TABS else 0
        new = self.TABS.index(name)
        self.history = []
        self.current_tab = name
        if transition is None:
            transition = CardTransition(direction="left" if new >= old else "right", mode="push", duration=0.32)
        self.sm.transition = transition
        if self.sm.current == name:
            self.screens[name].refresh()
        self.sm.current = name
        self._show_nav(True)

    def push(self, name):
        self.history.append(self.sm.current)
        self.sm.transition = CardTransition(direction="up" if name in ("premium", "add") else "left", mode="push", duration=0.35)
        if self.sm.current == name:
            self.screens[name].refresh()
        self.sm.current = name
        self._show_nav(False)

    def back(self):
        if not self.history:
            if self.sm.current != "home":
                self.go_tab("home")
                return True
            return False
        prev = self.history.pop()
        self.sm.transition = CardTransition(direction="down" if self.sm.current in ("premium", "add") else "right", mode="pop", duration=0.3)
        self.sm.current = prev
        self._show_nav(prev in self.TABS)
        return True

    def _on_key(self, _w, key, *_):
        if key == 27:  # tasto indietro di Android / Esc
            return self.back()
        return False

    def open_add(self):
        if not self.store.can_add():
            self.push("premium")
            return
        self.push("add")

    def open_form(self, service=None, editing=None, name=""):
        self.screens["form"].setup(service=service, editing=editing, name=name)
        self.push("form")

    def open_detail(self, sub_id, replace=False):
        self.screens["detail"].sub_id = sub_id
        if replace:
            # Dopo la modifica: torna al dettaglio aggiornato senza lasciare il modulo nella cronologia.
            self.history = [h for h in self.history if h not in ("form", "detail")]
        self.push("detail")

    def finish_onboarding(self):
        self.store.settings["onboarded"] = True
        self.store.save()
        self.request_permissions()
        self.go_tab("home", transition=RiseInTransition(duration=0.45))

    def set_dark(self, dark):
        self.store.settings["dark"] = dark
        self.store.save()
        self.apply_theme()
        self.screens["settings"].refresh()

    # --- notifiche
    def request_permissions(self):
        if platform == "android":
            try:
                # Il modulo "android" esiste solo dentro l'APK: sul PC l'editor non lo trova, è normale.
                from android.permissions import Permission, request_permissions  # pyright: ignore[reportMissingImports]
                request_permissions([Permission.POST_NOTIFICATIONS])
            except Exception:
                pass

    def notify(self, title, message):
        try:
            from plyer import notification
            notification.notify(title=title, message=message, app_name="Maik Subs", timeout=10)
        except Exception:
            self.toast(title)

    def check_reminders(self):
        """Mostra i promemoria dovuti (all'apertura e quando l'app torna in primo piano)."""
        if not self.store.settings["notifications"]:
            return
        for key, title, body in self.store.due_reminders():
            self.notify(title, body)
            self.store.notified[key] = date.today().isoformat()
        cutoff = (date.today() - timedelta(days=60)).isoformat()
        self.store.notified = {k: v for k, v in self.store.notified.items() if v >= cutoff}
        self.store.save()

    def on_resume(self):
        self.check_reminders()
        if self.sm.current in self.screens:
            self.screens[self.sm.current].refresh()

    def on_pause(self):
        return True

    # --- toast
    def toast(self, message, action=None, on_action=None):
        if self.toast_box is not None:
            self.root_layout.remove_widget(self.toast_box)
        dark = self.store.settings["dark"]
        box = RoundBox(orientation="horizontal", size_hint=(None, None), padding=(dp(18), dp(10)), spacing=dp(12), radius=dp(18))
        box.bg_color = hexc("#F5F5FA") if dark else hexc("#15151C")
        box.width = min(Window.width - dp(32), dp(480))
        box.height = dp(54)
        box.pos = ((Window.width - box.width) / 2, dp(108))
        lbl = Label(text=sym(message), markup=True, bold=True, color=hexc("#0B0B12") if dark else [1, 1, 1, 1], halign="left", valign="middle",
                    shorten=True, font_size=dp(15))
        lbl.bind(size=lambda w, s: setattr(w, "text_size", s))
        box.add_widget(lbl)
        if action:
            b = ButtonLabel(text=action, bold=True, color=self.c_accent, size_hint_x=None, width=dp(80), font_size=dp(15))
            b.bind(on_release=lambda *_: (on_action(), self._hide_toast(box)))
            box.add_widget(b)
        self.root_layout.add_widget(box)
        self.toast_box = box
        box.opacity, box.zoom = 0, 0.8
        Animation(opacity=1, zoom=1, d=0.3, t="out_back").start(box)
        Clock.schedule_once(lambda *_: self._hide_toast(box), 4.5 if action else 2.8)

    def _hide_toast(self, box):
        if box.parent is None:
            return
        anim = Animation(opacity=0, zoom=0.9, d=0.2)
        anim.bind(on_complete=lambda *_: box.parent and box.parent.remove_widget(box))
        anim.start(box)
        if self.toast_box is box:
            self.toast_box = None


class ButtonLabel(ButtonBehavior, Label):
    pass


if __name__ == "__main__":
    if platform not in ("android", "ios"):
        Window.size = (412, 900)
    MaikSubsApp().run()
