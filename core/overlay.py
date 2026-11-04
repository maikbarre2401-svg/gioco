"""Transparent click-through overlay with glow-capable drawing."""

from __future__ import annotations

import ctypes
import logging
import tkinter as tk
from typing import List, Tuple, Union

logger = logging.getLogger(__name__)

WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOPMOST = 0x00000008
GWL_EXSTYLE = -20

DrawItem = Union[
    Tuple[str, int, int, int, int, str, int],
    Tuple[str, int, int, int, str],
    Tuple[str, int, int, int, int, str],
    Tuple[str, int, int, str, str, int],
]


class Overlay:
    """Transparent click-through overlay drawn on a Tk Canvas."""

    def __init__(self, width: int, height: int) -> None:
        self._width = width
        self._height = height
        self._root: tk.Tk | None = None
        self._canvas: tk.Canvas | None = None
        self._visible = True
        self._transparent_color = "#010203"

    def create(self, root: tk.Tk) -> None:
        """Build the overlay as a Toplevel of the given root."""
        self._root = root
        top = tk.Toplevel(root)
        top.title("Overlay")
        top.geometry(f"{self._width}x{self._height}+0+0")
        top.overrideredirect(True)
        top.attributes("-topmost", True)
        top.attributes("-transparentcolor", self._transparent_color)
        top.config(bg=self._transparent_color)

        self._canvas = tk.Canvas(
            top,
            width=self._width,
            height=self._height,
            bg=self._transparent_color,
            highlightthickness=0,
            bd=0,
        )
        self._canvas.pack()

        top.update_idletasks()
        self._set_click_through(top)
        self._top = top

    def _set_click_through(self, window: tk.Toplevel) -> None:
        """Set extended window styles for layered + transparent (click-through)."""
        try:
            hwnd = ctypes.windll.user32.FindWindowW(None, "Overlay")
            if hwnd:
                style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                style |= WS_EX_LAYERED | WS_EX_TRANSPARENT
                ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
        except Exception:
            logger.warning("Failed to set click-through style", exc_info=True)

    def frame(self, items: List[DrawItem]) -> None:
        """Clear and redraw all items. Types: line, dot, box, circle, cross, text."""
        if self._canvas is None:
            return
        self._canvas.delete("all")
        for item in items:
            kind = item[0]
            try:
                if kind == "line":
                    _, x1, y1, x2, y2, color, width = item
                    self._canvas.create_line(
                        x1, y1, x2, y2,
                        fill=color, width=width,
                        smooth=True, capstyle="round",
                    )
                elif kind == "dot":
                    _, x, y, r, color = item
                    self._canvas.create_oval(
                        x - r, y - r, x + r, y + r,
                        fill=color, outline="",
                    )
                elif kind == "box":
                    _, x1, y1, x2, y2, color = item
                    self._canvas.create_rectangle(
                        x1, y1, x2, y2, outline=color, width=2, dash=(6, 3),
                    )
                elif kind == "circle":
                    _, x, y, r, color = item
                    self._canvas.create_oval(
                        x - r, y - r, x + r, y + r,
                        outline=color, width=2,
                    )
                elif kind == "cross":
                    _, x, y, s, color = item
                    self._canvas.create_line(
                        x - s, y, x + s, y,
                        fill=color, width=2, capstyle="round",
                    )
                    self._canvas.create_line(
                        x, y - s, x, y + s,
                        fill=color, width=2, capstyle="round",
                    )
                elif kind == "text":
                    _, x, y, text_str, color, size = item
                    self._canvas.create_text(
                        x, y, text=text_str, fill=color,
                        font=("Consolas", size), anchor="nw",
                    )
            except Exception:
                pass
        canvas.update_idletasks()

    def show(self) -> None:
        """Show the overlay window."""
        if hasattr(self, "_top"):
            self._top.deiconify()
            self._visible = True

    def hide(self) -> None:
        """Hide the overlay window."""
        if hasattr(self, "_top"):
            self._top.withdraw()
            self._visible = False

    def destroy(self) -> None:
        """Destroy the overlay window."""
        if hasattr(self, "_top"):
            try:
                self._top.destroy()
            except Exception:
                pass
