"""Tema visivo: palette, font, helper di disegno e stili ttk.

Dipende solo da tkinter, così è testabile in isolamento (senza cv2/insightface).
"""
import tkinter as tk
from tkinter import font as tkfont

# ============================================================
# PALETTE — dark "cyber", accenti freddi, contrasto controllato
# ============================================================
BG = '#070b14'        # fondo finestra (near-black navy)
SURFACE = '#0d1420'   # pannelli
RAISED = '#131c2b'    # elementi in rilievo / hover
SUNKEN = '#060a11'    # incavi (track slider, console)
BORDER = '#1e2b40'    # bordi 1px
BORDER_SOFT = '#162133'

TEXT = '#e8eefc'      # testo primario
TEXT_DIM = '#8fa3c0'  # testo secondario
TEXT_MUTE = '#5b6e8c'  # etichette

CYAN = '#22d3ee'      # accento primario
VIOLET = '#a78bfa'    # accento secondario
GREEN = '#34d399'     # ok / attivo
AMBER = '#fbbf24'     # attenzione
ROSE = '#fb7185'      # errore / stop
BLUE = '#60a5fa'

# Mappatura semantica
ACCENT = CYAN
OK = GREEN
WARN = AMBER
BAD = ROSE


# ============================================================
# FONT — sceglie il primo family disponibile sul sistema
# ============================================================
_UI_STACK = ('Inter', 'SF Pro Display', 'Segoe UI Variable', 'Segoe UI',
             'Helvetica Neue', 'Ubuntu', 'DejaVu Sans', 'Arial')
_MONO_STACK = ('JetBrains Mono', 'SF Mono', 'Cascadia Mono', 'Consolas',
               'Ubuntu Mono', 'DejaVu Sans Mono', 'Courier New')

_resolved = {}


def _pick(stack, default):
    try:
        available = set(tkfont.families())
    except Exception:
        return default
    for name in stack:
        if name in available:
            return name
    return default


def ui_family():
    if 'ui' not in _resolved:
        _resolved['ui'] = _pick(_UI_STACK, 'TkDefaultFont')
    return _resolved['ui']


def mono_family():
    if 'mono' not in _resolved:
        _resolved['mono'] = _pick(_MONO_STACK, 'TkFixedFont')
    return _resolved['mono']


def f(size=10, weight='normal', mono=False):
    """Font tuple pronto per i widget."""
    return (mono_family() if mono else ui_family(), size, weight)


# ============================================================
# DISEGNO
# ============================================================
def round_rect(canvas, x1, y1, x2, y2, r=8, **kw):
    """Rettangolo con angoli arrotondati su un Canvas.

    Usa un polygon 'smooth': è il modo affidabile di avere angoli tondi in
    Tkinter, che non ha primitive per i corner radius.
    """
    r = max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    pts = [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]
    return canvas.create_polygon(pts, smooth=True, splinesteps=24, **kw)


def mix(c1, c2, t):
    """Interpola due colori #rrggbb (t=0 -> c1, t=1 -> c2)."""
    t = max(0.0, min(1.0, t))
    a = tuple(int(c1[i:i + 2], 16) for i in (1, 3, 5))
    b = tuple(int(c2[i:i + 2], 16) for i in (1, 3, 5))
    return '#%02x%02x%02x' % tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


# ============================================================
# STILI ttk (per i pochi widget ttk che restano: Combobox, Notebook)
# ============================================================
def apply_ttk(root):
    from tkinter import ttk
    st = ttk.Style(root)
    try:
        st.theme_use('clam')      # 'clam' è l'unico tema ttk davvero ri-colorabile
    except Exception:
        pass

    st.configure('.', background=SURFACE, foreground=TEXT,
                 fieldbackground=RAISED, font=f(9))

    st.configure('Neo.TCombobox',
                 fieldbackground=RAISED, background=RAISED, foreground=TEXT,
                 arrowcolor=TEXT_DIM, bordercolor=BORDER, lightcolor=RAISED,
                 darkcolor=RAISED, selectbackground=RAISED,
                 selectforeground=TEXT, padding=4)
    st.map('Neo.TCombobox',
           fieldbackground=[('readonly', RAISED)],
           bordercolor=[('focus', ACCENT), ('hover', BORDER)],
           arrowcolor=[('hover', ACCENT)])

    # lista a tendina del combobox (è una Listbox Tk, si stila via option db)
    root.option_add('*TCombobox*Listbox.background', RAISED)
    root.option_add('*TCombobox*Listbox.foreground', TEXT)
    root.option_add('*TCombobox*Listbox.selectBackground', ACCENT)
    root.option_add('*TCombobox*Listbox.selectForeground', BG)
    root.option_add('*TCombobox*Listbox.font', f(9))

    st.configure('Neo.Vertical.TScrollbar', background=RAISED, troughcolor=SUNKEN,
                 bordercolor=SURFACE, arrowcolor=TEXT_MUTE, darkcolor=RAISED,
                 lightcolor=RAISED)
    return st
