"""Widget custom disegnati su Canvas.

Tkinter di serie è datato (Checkbutton/Scale sembrano Windows 95). Qui i
controlli sono ridisegnati su Canvas: pill arrotondate, knob, hover states.
Dipende solo da tkinter → testabile senza il resto dell'app.
"""
import tkinter as tk

from . import theme as T


# ============================================================
# CARD — pannello con bordo 1px e titolo con barra d'accento
# ============================================================
class Card(tk.Frame):
    def __init__(self, parent, title=None, accent=None, pad=10, **kw):
        super().__init__(parent, bg=T.SURFACE, highlightthickness=1,
                         highlightbackground=T.BORDER, bd=0, **kw)
        self.accent = accent or T.ACCENT
        if title:
            head = tk.Frame(self, bg=T.SURFACE)
            head.pack(fill=tk.X, padx=pad, pady=(pad, 4))
            tk.Frame(head, bg=self.accent, width=3, height=12).pack(side=tk.LEFT,
                                                                    padx=(0, 7))
            tk.Label(head, text=title.upper(), bg=T.SURFACE, fg=T.TEXT_MUTE,
                     font=T.f(8, 'bold')).pack(side=tk.LEFT)
            self.head = head
        self.body = tk.Frame(self, bg=T.SURFACE)
        self.body.pack(fill=tk.BOTH, expand=True, padx=pad, pady=(0, pad))


# ============================================================
# BUTTON — rounded rect con hover/press
# ============================================================
class NeoButton(tk.Canvas):
    KINDS = {
        'primary': (T.ACCENT, T.BG),
        'accent': (T.VIOLET, T.BG),
        'ok': (T.OK, T.BG),
        'danger': (T.BAD, T.BG),
        'ghost': (T.RAISED, T.TEXT),
    }

    def __init__(self, parent, text, command=None, kind='ghost', h=32, r=8,
                 font=None, width=None):
        self.fill, self.fg = self.KINDS.get(kind, self.KINDS['ghost'])
        self._base = self.fill
        self._cmd = command
        self._text = text
        self._r = r
        self._enabled = True
        # NB: la width richiesta è un MINIMO che pack/grid non possono ridurre.
        # Tenerla piccola: con fill=X i bottoni si distribuiscono da soli,
        # altrimenti in una riga stretta l'ultimo viene tagliato.
        w = width if width is not None else max(44, 7 * len(text) + 16)
        super().__init__(parent, height=h, width=w, bg=T.SURFACE,
                         highlightthickness=0, bd=0)
        self._font = font or T.f(9, 'bold')
        self._shape = None
        self._label = None
        self.bind('<Configure>', self._redraw)
        self.bind('<Enter>', lambda e: self._tint(0.14))
        self.bind('<Leave>', lambda e: self._tint(0.0))
        self.bind('<ButtonPress-1>', lambda e: self._tint(-0.12))
        self.bind('<ButtonRelease-1>', self._click)

    def _redraw(self, _e=None):
        self.delete('all')
        w, h = self.winfo_width(), self.winfo_height()
        if w <= 1:
            return
        self._shape = T.round_rect(self, 1, 1, w - 1, h - 1, self._r,
                                   fill=self.fill, outline='')
        self._label = self.create_text(w / 2, h / 2, text=self._text,
                                       fill=self.fg, font=self._font)

    def _tint(self, amount):
        if not self._enabled:
            return
        target = T.TEXT if amount > 0 else '#000000'
        self.fill = (self._base if amount == 0
                     else T.mix(self._base, target, abs(amount)))
        if self._shape:
            self.itemconfig(self._shape, fill=self.fill)

    def _click(self, _e=None):
        self._tint(0.14)
        if self._enabled and self._cmd:
            self._cmd()

    def configure_text(self, text):
        self._text = text
        if self._label:
            self.itemconfig(self._label, text=text)

    def set_kind(self, kind):
        self.fill, self.fg = self.KINDS.get(kind, self.KINDS['ghost'])
        self._base = self.fill
        self._redraw()

    def set_enabled(self, on):
        self._enabled = bool(on)
        self.fill = self._base if on else T.mix(self._base, T.SURFACE, 0.80)
        self._redraw()
        if self._label:
            self.itemconfig(self._label,
                            fill=self.fg if on else T.TEXT_MUTE)


# ============================================================
# SWITCH — toggle stile iOS legato a una BooleanVar
# ============================================================
class NeoSwitch(tk.Frame):
    def __init__(self, parent, text, variable, command=None, accent=None,
                 wrap=None):
        super().__init__(parent, bg=T.SURFACE)
        self.var = variable
        self.cmd = command
        self.accent = accent or T.ACCENT
        self.cv = tk.Canvas(self, width=34, height=18, bg=T.SURFACE,
                            highlightthickness=0, bd=0)
        self.cv.pack(side=tk.LEFT, padx=(0, 8))
        self.lbl = tk.Label(self, text=text, bg=T.SURFACE, fg=T.TEXT_DIM,
                            font=T.f(9), anchor='w', justify='left',
                            wraplength=wrap or 0)
        self.lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)
        for w in (self.cv, self.lbl, self):
            w.bind('<Button-1>', self._toggle)
        self._track = None
        self._knob = None
        self._draw()
        try:
            self.var.trace_add('write', lambda *_: self._draw())
        except Exception:
            pass

    def _draw(self):
        on = bool(self.var.get())
        self.cv.delete('all')
        T.round_rect(self.cv, 1, 2, 33, 16, 7,
                     fill=self.accent if on else T.RAISED,
                     outline='' if on else T.BORDER)
        cx = 25 if on else 9
        self.cv.create_oval(cx - 6, 3, cx + 6, 15,
                            fill=T.BG if on else T.TEXT_MUTE, outline='')
        self.lbl.config(fg=T.TEXT if on else T.TEXT_DIM)

    def _toggle(self, _e=None):
        self.var.set(not bool(self.var.get()))
        self._draw()
        if self.cmd:
            self.cmd()


# ============================================================
# SLIDER — track sottile + knob, legato a una DoubleVar
# ============================================================
class NeoSlider(tk.Frame):
    def __init__(self, parent, label, variable, lo, hi, fmt='{:.2f}',
                 accent=None, hint=None):
        super().__init__(parent, bg=T.SURFACE)
        self.var, self.lo, self.hi, self.fmt = variable, float(lo), float(hi), fmt
        self.accent = accent or T.ACCENT
        self._drag = False

        head = tk.Frame(self, bg=T.SURFACE)
        head.pack(fill=tk.X)
        tk.Label(head, text=label, bg=T.SURFACE, fg=T.TEXT_DIM,
                 font=T.f(9)).pack(side=tk.LEFT)
        self.val = tk.Label(head, text=fmt.format(self.var.get()), bg=T.SURFACE,
                            fg=self.accent, font=T.f(9, 'bold', mono=True))
        self.val.pack(side=tk.RIGHT)

        self.cv = tk.Canvas(self, height=18, bg=T.SURFACE, highlightthickness=0,
                            bd=0)
        self.cv.pack(fill=tk.X)
        self.cv.bind('<Configure>', lambda e: self._draw())
        self.cv.bind('<Button-1>', self._jump)
        self.cv.bind('<B1-Motion>', self._jump)
        self.cv.bind('<ButtonRelease-1>', lambda e: setattr(self, '_drag', False))
        if hint:
            tk.Label(self, text=hint, bg=T.SURFACE, fg=T.TEXT_MUTE,
                     font=T.f(7)).pack(anchor='w')
        try:
            self.var.trace_add('write', lambda *_: self._draw())
        except Exception:
            pass

    def _frac(self):
        span = (self.hi - self.lo) or 1.0
        return max(0.0, min(1.0, (float(self.var.get()) - self.lo) / span))

    def _draw(self):
        w = self.cv.winfo_width()
        if w <= 1:
            return
        self.cv.delete('all')
        y, pad = 9, 8
        x1, x2 = pad, w - pad
        T.round_rect(self.cv, x1, y - 2, x2, y + 2, 2, fill=T.SUNKEN, outline='')
        fx = x1 + (x2 - x1) * self._frac()
        if fx > x1 + 1:
            T.round_rect(self.cv, x1, y - 2, fx, y + 2, 2, fill=self.accent,
                         outline='')
        self.cv.create_oval(fx - 6, y - 6, fx + 6, y + 6, fill=T.TEXT,
                            outline=self.accent, width=2)
        self.val.config(text=self.fmt.format(self.var.get()))

    def _jump(self, ev):
        w = self.cv.winfo_width()
        pad = 8
        t = (ev.x - pad) / max(1, (w - 2 * pad))
        t = max(0.0, min(1.0, t))
        self.var.set(self.lo + t * (self.hi - self.lo))
        self._draw()


# ============================================================
# BADGE — chip di stato
# ============================================================
class Badge(tk.Canvas):
    def __init__(self, parent, text='', color=None, bg=None):
        self._bgc = bg or T.SURFACE
        super().__init__(parent, height=20, bg=self._bgc, highlightthickness=0,
                         bd=0, width=10)
        self._text = text
        self._color = color or T.TEXT_MUTE
        self.bind('<Configure>', lambda e: self._draw())
        self._resize()

    def _resize(self):
        self.config(width=max(34, 7 * len(self._text) + 18))

    def _draw(self):
        self.delete('all')
        w, h = self.winfo_width(), self.winfo_height()
        if w <= 1:
            return
        T.round_rect(self, 1, 2, w - 1, h - 2, (h - 4) / 2,
                     fill=T.mix(self._bgc, self._color, 0.18),
                     outline=T.mix(self._bgc, self._color, 0.45))
        self.create_text(w / 2, h / 2, text=self._text, fill=self._color,
                         font=T.f(8, 'bold'))

    def set(self, text=None, color=None):
        if text is not None:
            self._text = text
            self._resize()
        if color is not None:
            self._color = color
        self._draw()


# ============================================================
# STAT TILE — numero grande + etichetta
# ============================================================
class StatTile(tk.Frame):
    def __init__(self, parent, label, value='0', unit='', color=None):
        super().__init__(parent, bg=T.SURFACE)
        self.color = color or T.TEXT
        row = tk.Frame(self, bg=T.SURFACE)
        row.pack(anchor='w')
        self.v = tk.Label(row, text=value, bg=T.SURFACE, fg=self.color,
                          font=T.f(20, 'bold', mono=True))
        self.v.pack(side=tk.LEFT)
        if unit:
            tk.Label(row, text=unit, bg=T.SURFACE, fg=T.TEXT_MUTE,
                     font=T.f(8)).pack(side=tk.LEFT, padx=(2, 0), pady=(7, 0))
        tk.Label(self, text=label.upper(), bg=T.SURFACE, fg=T.TEXT_MUTE,
                 font=T.f(7, 'bold')).pack(anchor='w')

    def set(self, value, color=None):
        self.v.config(text=str(value))
        if color:
            self.v.config(fg=color)


# ============================================================
# SPARKLINE — grafico live (storico FPS)
# ============================================================
class Sparkline(tk.Canvas):
    def __init__(self, parent, height=40, color=None, fill=True, maxlen=120):
        super().__init__(parent, height=height, bg=T.SUNKEN,
                         highlightthickness=1, highlightbackground=T.BORDER_SOFT,
                         bd=0)
        self.color = color or T.ACCENT
        self.maxlen = maxlen
        self.do_fill = fill
        self.series = []
        self.bind('<Configure>', lambda e: self.redraw())

    def push(self, v):
        self.series.append(float(v))
        if len(self.series) > self.maxlen:
            self.series.pop(0)
        self.redraw()

    def set_series(self, values):
        self.series = [float(v) for v in values][-self.maxlen:]
        self.redraw()

    def redraw(self):
        self.delete('all')
        w, h = self.winfo_width(), self.winfo_height()
        if w <= 1 or len(self.series) < 2:
            return
        top = max(self.series + [1.0]) * 1.15
        n = len(self.series)
        step = w / max(1, n - 1)
        pts = []
        for i, v in enumerate(self.series):
            pts.extend([i * step, h - 2 - (v / top) * (h - 6)])
        if self.do_fill:
            self.create_polygon(pts + [w, h, 0, h], fill=T.mix(T.SUNKEN,
                                                               self.color, 0.22),
                                outline='')
        self.create_line(pts, fill=self.color, width=2, smooth=True)
        # ultimo punto evidenziato
        self.create_oval(pts[-2] - 3, pts[-1] - 3, pts[-2] + 3, pts[-1] + 3,
                         fill=self.color, outline='')


# ============================================================
# SEGMENTED — selettore a segmenti (sostituisce i Radiobutton)
# ============================================================
class Segmented(tk.Canvas):
    def __init__(self, parent, options, variable, command=None, h=30, accent=None):
        super().__init__(parent, height=h, bg=T.SURFACE, highlightthickness=0,
                         bd=0)
        self.options = list(options)     # [(label, value), ...]
        self.var = variable
        self.cmd = command
        self.accent = accent or T.ACCENT
        self.bind('<Configure>', lambda e: self._draw())
        self.bind('<Button-1>', self._pick)
        try:
            self.var.trace_add('write', lambda *_: self._draw())
        except Exception:
            pass

    def _draw(self):
        self.delete('all')
        w, h = self.winfo_width(), self.winfo_height()
        if w <= 1:
            return
        T.round_rect(self, 0, 0, w, h, 9, fill=T.SUNKEN, outline=T.BORDER_SOFT)
        n = len(self.options)
        seg = w / n
        cur = self.var.get()
        for i, (label, value) in enumerate(self.options):
            x1, x2 = i * seg, (i + 1) * seg
            on = (value == cur)
            if on:
                T.round_rect(self, x1 + 2, 2, x2 - 2, h - 2, 7,
                             fill=T.mix(T.SUNKEN, self.accent, 0.85), outline='')
            self.create_text((x1 + x2) / 2, h / 2, text=label,
                             fill=T.BG if on else T.TEXT_DIM,
                             font=T.f(9, 'bold' if on else 'normal'))

    def _pick(self, ev):
        w = self.winfo_width()
        n = len(self.options)
        idx = max(0, min(n - 1, int(ev.x / (w / n))))
        self.var.set(self.options[idx][1])
        self._draw()
        if self.cmd:
            self.cmd()
