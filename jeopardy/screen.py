"""Thin curses wrapper: colors, safe drawing, key input, menus and text entry."""
from __future__ import annotations

import curses
import textwrap
import time

# Color pair ids
BOARD, VALUE, CURSOR, GOOD, BAD, GOLD, ACCENT, GOOD_B, BAD_B, DIM_B = range(1, 11)

ENTER = {"\n", "\r", curses.KEY_ENTER}
BACKSPACE = {"\x7f", "\b", "\x08", curses.KEY_BACKSPACE}
ESC = "\x1b"
UP = {curses.KEY_UP, "k", "w"}
DOWN = {curses.KEY_DOWN, "j", "s"}
LEFT = {curses.KEY_LEFT, "h", "a"}
RIGHT = {curses.KEY_RIGHT, "l", "d"}

MIN_W, MIN_H = 70, 22


def money(n: int) -> str:
    return f"-${abs(n):,}" if n < 0 else f"${n:,}"


class Screen:
    def __init__(self, scr: "curses.window"):
        self.scr = scr
        scr.keypad(True)
        try:
            curses.curs_set(0)
        except curses.error:
            pass
        self.color = curses.has_colors()
        if self.color:
            curses.start_color()
            try:
                curses.use_default_colors()
                bg = -1
            except curses.error:
                bg = curses.COLOR_BLACK
            if curses.COLORS >= 256:
                # Fixed xterm-256 RGB colors, so terminal themes can't wash them out.
                navy, white, gold, black = 17, 231, 220, 16
                green, red, sky, cyan = 120, 210, 153, 117
            elif curses.COLORS >= 16:
                navy, white, gold, black = 4, 15, 11, 0
                green, red, sky, cyan = 10, 9, 14, 14
            else:
                C = curses
                navy, white, gold, black = C.COLOR_BLUE, C.COLOR_WHITE, C.COLOR_YELLOW, C.COLOR_BLACK
                green, red, sky, cyan = C.COLOR_GREEN, C.COLOR_RED, C.COLOR_CYAN, C.COLOR_CYAN
            pairs = {
                BOARD: (white, navy),
                VALUE: (gold, navy),
                CURSOR: (black, gold),
                GOOD: (green, bg),
                BAD: (red, bg),
                GOLD: (gold, bg),
                ACCENT: (cyan, bg),
                GOOD_B: (green, navy),
                BAD_B: (red, navy),
                DIM_B: (sky, navy),
            }
            for pid, (fg, b) in pairs.items():
                curses.init_pair(pid, fg, b)

    # ---- basics -------------------------------------------------------------
    def a(self, pair: int = 0, bold: bool = False) -> int:
        attr = curses.A_BOLD if bold else 0
        if self.color:
            return attr | curses.color_pair(pair)
        if pair == CURSOR:
            return attr | curses.A_REVERSE
        return attr

    @property
    def size(self) -> tuple[int, int]:
        return self.scr.getmaxyx()

    def fill(self, pair: int = 0) -> None:
        self.scr.bkgd(" ", self.a(pair))
        self.scr.erase()

    def put(self, y: int, x: int, text: str, attr: int = 0) -> None:
        h, w = self.size
        if y < 0 or y >= h or x >= w:
            return
        if x < 0:
            text, x = text[-x:], 0
        text = text[: max(0, w - x - (1 if y == h - 1 else 0))]
        try:
            self.scr.addstr(y, x, text, attr)
        except curses.error:
            pass

    def center(self, y: int, text: str, attr: int = 0) -> None:
        _, w = self.size
        self.put(y, max(0, (w - len(text)) // 2), text, attr)

    def refresh(self) -> None:
        self.scr.refresh()

    def too_small(self) -> bool:
        h, w = self.size
        if h >= MIN_H and w >= MIN_W:
            return False
        self.fill()
        self.center(h // 2, f"Please enlarge the terminal to at least {MIN_W}x{MIN_H}")
        self.center(h // 2 + 1, f"(currently {w}x{h})")
        self.refresh()
        return True

    # ---- input ----------------------------------------------------------------
    def read(self, timeout_ms: int = -1):
        """Return a key (str or int) or None on timeout/resize."""
        self.scr.timeout(timeout_ms)
        try:
            k = self.scr.get_wch()
        except curses.error:
            return None
        if k == curses.KEY_RESIZE:
            return None
        return k

    def flush(self) -> None:
        curses.flushinp()

    def wait_key(self, draw=None):
        while True:
            if draw and not self.too_small():
                draw()
                self.refresh()
            k = self.read(200)
            if k is not None:
                return k

    def hold(self, seconds: float, draw, skippable: bool = True) -> None:
        """Show `draw` for `seconds` (Enter/space skips)."""
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            if not self.too_small():
                draw()
                self.refresh()
            k = self.read(50)
            if skippable and (k in ENTER or k == " "):
                break
        self.flush()

    def text_input(self, draw, limit: float | None = None, numeric: bool = False,
                   maxlen: int = 40) -> tuple[str | None, bool]:
        """Collect a line of text. `draw(buf, frac_remaining)` renders the screen.

        Returns (text, timed_out). text is None if the user pressed Esc.
        """
        buf = ""
        start = time.monotonic()
        self.flush()
        while True:
            frac = None
            if limit is not None:
                remaining = limit - (time.monotonic() - start)
                if remaining <= 0:
                    return buf, True
                frac = remaining / limit
            if not self.too_small():
                draw(buf, frac)
                self.refresh()
            k = self.read(50)
            if k is None:
                continue
            if k in ENTER:
                return buf, False
            if k in BACKSPACE:
                buf = buf[:-1]
            elif k == ESC:
                return None, False
            elif isinstance(k, str) and k.isprintable() and len(buf) < maxlen:
                if numeric and not k.isdigit():
                    continue
                buf += k

    # ---- widgets ----------------------------------------------------------------
    def bar(self, y: int, frac: float, pair: int = VALUE, width: int = 50) -> None:
        _, w = self.size
        width = min(width, w - 10)
        filled = max(0, min(width, round(frac * width)))
        x = (w - width) // 2
        self.put(y, x, "█" * filled, self.a(pair, True))
        self.put(y, x + filled, "░" * (width - filled), self.a(pair))

    def wrapped(self, y: int, text: str, width: int, attr: int = 0, max_lines: int = 99) -> int:
        lines = textwrap.wrap(text, width)[:max_lines]
        for i, line in enumerate(lines):
            self.center(y + i, line, attr)
        return len(lines)

    def menu(self, title: str, options: list[tuple[str, str]], selected: int = 0,
             header=None, footer: str = "↑/↓ move · Enter select · Esc back") -> int | None:
        sel = selected
        top = 0
        while True:
            if not self.too_small():
                h, w = self.size
                self.fill()
                y = header(self) if header else 1
                self.center(y, title, self.a(GOLD, True))
                y += 2
                desc_h = 4
                rows = max(3, h - y - desc_h - 2)
                if sel < top:
                    top = sel
                elif sel >= top + rows:
                    top = sel - rows + 1
                width = max(len(lbl) for lbl, _ in options) + 6
                x = max(0, (w - width) // 2)
                for i, (label, _) in enumerate(options[top: top + rows]):
                    idx = top + i
                    if idx == sel:
                        self.put(y + i, x, f" ▶ {label} ".ljust(width), self.a(CURSOR, True))
                    else:
                        self.put(y + i, x, f"   {label}", self.a())
                if top > 0:
                    self.put(y - 1, x + width, "▲", self.a(ACCENT))
                if top + rows < len(options):
                    self.put(y + rows - 1, x + width, "▼", self.a(ACCENT))
                desc = options[sel][1]
                if desc:
                    self.wrapped(h - desc_h - 1, desc, min(70, w - 4), self.a(ACCENT), desc_h)
                self.center(h - 1, footer, curses.A_DIM)
                self.refresh()
            k = self.read(200)
            if k is None:
                continue
            if k in UP:
                sel = (sel - 1) % len(options)
            elif k in DOWN:
                sel = (sel + 1) % len(options)
            elif k in ENTER or k == " ":
                return sel
            elif k in (ESC, "q"):
                return None
            elif isinstance(k, str) and k.isdigit() and 1 <= int(k) <= len(options):
                return int(k) - 1
