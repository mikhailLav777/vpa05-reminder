"""Главный экран учебного прототипа со сглаженными элементами."""

import math
import tkinter as tk
from datetime import datetime
from functools import lru_cache
from tkinter import font as tkfont
from tkinter import messagebox

from PIL import Image, ImageDraw, ImageFilter, ImageTk


BG = "#280A46"
PANEL = "#35114F"
WHITE = "#FFFFFF"
MUTED = "#D9C9E7"
CYAN = "#25F5ED"

STYLES = {
    "cyan": ("#50FFF3", "#00D9DA", "#89FFF9"),
    "teal": ("#148D85", "#003D43", "#24FFF1"),
    "blue": ("#146CAE", "#073052", "#51DFFF"),
    "red": ("#B94155", "#561324", "#FF8B95"),
    "orange": ("#BB6517", "#5B2A0B", "#FFAB54"),
    "green": ("#10AC57", "#034729", "#51FF9C"),
    "violet": ("#78419C", "#351843", "#D4A9F0"),
    "purple": ("#56316D", "#281039", "#CDA9E6"),
    "gold": ("#957510", "#41300A", "#FFE55C"),
    "gray": ("#5E6073", "#282A3A", "#C1C3D0"),
    "input": ("#311344", "#311344", "#CDA9E6"),
}

MONTHS = (
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
)


def blend(first, second, amount):
    a = tuple(int(first[i:i + 2], 16) for i in (1, 3, 5))
    b = tuple(int(second[i:i + 2], 16) for i in (1, 3, 5))
    return "#" + "".join(
        f"{round(x + (y - x) * amount):02x}"
        for x, y in zip(a, b)
    )


def _place_image(canvas, image, x, y, tag):
    """Сохранить ссылки на изображения, используемые Tkinter."""
    references = getattr(canvas, "_smooth_images", {})
    canvas._smooth_images = {
        item: picture
        for item, picture in references.items()
        if canvas.type(item)
    }

    picture = ImageTk.PhotoImage(image, master=canvas)
    item = canvas.create_image(
        x, y, image=picture, anchor="nw", tags=tag,
    )
    canvas._smooth_images[item] = picture


@lru_cache(maxsize=64)
def _surface(width, height, radius, style, border_color, border_width):
    """Рисуем крупнее, затем уменьшаем со сглаживанием."""
    scale, padding = 4, 5
    size = (
        (width + padding * 2) * scale,
        (height + padding * 2) * scale,
    )

    result = Image.new("RGBA", size, (0, 0, 0, 0))
    box = (
        padding * scale,
        padding * scale,
        (padding + width - 1) * scale,
        (padding + height - 1) * scale,
    )
    radius = max(
        1, min(radius, (width - 1) / 2, (height - 1) / 2)
    ) * scale

    if style is not None:
        top, bottom, edge = STYLES[style]

        mask = Image.new("L", size, 0)
        ImageDraw.Draw(mask).rounded_rectangle(
            box, radius=radius, fill=255,
        )

        if style != "input":
            glow = mask.filter(
                ImageFilter.GaussianBlur(1.2 * scale)
            )
            glow = glow.point(lambda value: round(value * 0.3))
            halo = Image.new("RGBA", size, edge)
            halo.putalpha(glow)
            result.alpha_composite(halo)

        gradient = Image.new("RGBA", size, top)
        draw = ImageDraw.Draw(gradient)

        for y in range(size[1]):
            fraction = max(
                0,
                min(
                    1,
                    (y - padding * scale) / max(1, height * scale),
                ),
            )
            color = blend(top, bottom, min(1, fraction * 1.55))

            if style != "input":
                if fraction < 0.17:
                    color = blend(
                        color, WHITE, (0.17 - fraction) * 1.7,
                    )
                if fraction > 0.84:
                    color = blend(
                        color, edge, (fraction - 0.84) * 1.1,
                    )

            draw.line((0, y, size[0], y), fill=color)

        gradient.putalpha(mask)
        result.alpha_composite(gradient)
        border_color = edge

    ImageDraw.Draw(result).rounded_rectangle(
        box,
        radius=radius,
        outline=border_color,
        width=max(1, round(border_width * scale)),
    )

    return result.resize(
        (width + padding * 2, height + padding * 2),
        Image.Resampling.LANCZOS,
    )


def rounded_outline(canvas, box, radius, color, width=1, tag="art"):
    x1, y1, x2, y2 = box
    w, h = round(x2 - x1) + 1, round(y2 - y1) + 1

    if w < 4 or h < 4:
        return

    image = _surface(w, h, radius, None, color, width)
    _place_image(canvas, image, x1 - 5, y1 - 5, tag)


def glass(canvas, box, style="purple", radius=12, tag="art"):
    x1, y1, x2, y2 = box
    w, h = round(x2 - x1) + 1, round(y2 - y1) + 1

    if w < 4 or h < 4:
        return

    image = _surface(
        w, h, radius, style, STYLES[style][2], 1.2,
    )
    _place_image(canvas, image, x1 - 5, y1 - 5, tag)


@lru_cache(maxsize=96)
def _icon_image(kind, color, size):
    scale, padding = 4, 4
    side = (size + padding * 2) * scale
    image = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    c, r = side / 2, size * scale / 2

    def line(points):
        draw.line(
            [(c + x * scale, c + y * scale) for x, y in points],
            fill=color,
            width=2 * scale,
            joint="curve",
        )

    def box(coords):
        return tuple(c + value * scale for value in coords)

    if kind in ("clock", "cancel", "check"):
        draw.ellipse(
            (c - r, c - r, c + r, c + r),
            outline=color,
            width=2 * scale,
        )
        if kind == "clock":
            line([(0, -size / 2 + 4), (0, 0), (5, 2)])
        elif kind == "cancel":
            line([
                (-size / 2 + 3, -size / 2 + 3),
                (size / 2 - 3, size / 2 - 3),
            ])
        else:
            line([(-5, 0), (-1, 4), (6, -5)])

    elif kind == "calendar":
        draw.rounded_rectangle(
            (c - r, c - r + 3 * scale, c + r, c + r),
            radius=2 * scale,
            outline=color,
            width=2 * scale,
        )
        line([
            (-size / 2, -size / 2 + 8),
            (size / 2, -size / 2 + 8),
        ])
        for x in (-size / 4, size / 4):
            line([(x, -size / 2), (x, -size / 2 + 5)])

    elif kind == "mic":
        draw.rounded_rectangle(
            box((-3, -size / 2, 3, 3)),
            radius=3 * scale,
            fill=color,
        )
        draw.arc(
            box((-7, -4, 7, 8)),
            0, 180, fill=color, width=2 * scale,
        )
        line([(0, 7), (0, 11)])
        line([(-5, 11), (5, 11)])

    elif kind == "search":
        draw.ellipse(
            box((-size / 2, -size / 2, 4, 4)),
            outline=color,
            width=2 * scale,
        )
        line([(3, 3), (size / 2, size / 2)])

    elif kind == "warning":
        line([
            (0, -size / 2),
            (-size / 2 - 1, size / 2),
            (size / 2 + 1, size / 2),
            (0, -size / 2),
        ])
        line([(0, -4), (0, 3)])
        draw.ellipse(box((-1, 6, 1, 8)), fill=color)

    elif kind == "arrow":
        line([(-8, 0), (8, 0)])
        line([(2, -6), (8, 0), (2, 6)])

    elif kind == "star":
        points = []
        for i in range(11):
            angle = math.radians(-90 + i * 36)
            length = size / 2 if i % 2 == 0 else size * 0.215
            points.append((
                length * math.cos(angle),
                length * math.sin(angle),
            ))
        line(points)

    return image.resize(
        (size + padding * 2, size + padding * 2),
        Image.Resampling.LANCZOS,
    )


def icon(canvas, kind, x, y, color=WHITE, size=18, tag="art"):
    smooth_icons = (
        "clock", "cancel", "calendar", "mic", "search",
        "check", "warning", "star", "arrow",
    )

    if kind in smooth_icons:
        image = _icon_image(kind, color, size)
        _place_image(
            canvas, image,
            x - image.width / 2,
            y - image.height / 2,
            tag,
        )
    else:
        symbols = {
            "gear": "⚙",
            "phone": "☎",
            "box": "◇",
            "bell": "♧",
        }
        canvas.create_text(
            x, y,
            text=symbols.get(kind, ""),
            fill=color,
            font=("Segoe UI Symbol", -size - 4),
            tags=tag,
        )


class NeonButton(tk.Canvas):
    """Скруглённая кнопка с наведением и нажатием."""

    def __init__(
        self, parent, text, command, style="teal", icon_name=None,
        height=42, width=180, font_size=18, bold=True,
    ):
        super().__init__(
            parent,
            bg=parent.cget("bg"),
            height=height,
            width=width,
            highlightthickness=0,
            bd=0,
            cursor="hand2",
            takefocus=1,
        )
        self.text, self.command, self.style = text, command, style
        self.icon_name = icon_name
        self.font = (
            "Segoe UI", -font_size,
            "bold" if bold else "normal",
        )
        self.hover = self.pressed = False

        self.bind("<Configure>", self._draw)
        self.bind("<Enter>", lambda event: self._state(hover=True))
        self.bind(
            "<Leave>",
            lambda event: self._state(hover=False, pressed=False),
        )
        self.bind("<ButtonPress-1>", self._press)
        self.bind("<ButtonRelease-1>", self._release)
        self.bind("<FocusIn>", self._draw)
        self.bind("<FocusOut>", self._draw)
        self.bind("<Return>", lambda event: self.command())
        self.bind("<space>", lambda event: self.command())

    def _state(self, **values):
        for key, value in values.items():
            setattr(self, key, value)
        self._draw()

    def _press(self, event):
        self.focus_set()
        self._state(pressed=True)

    def _release(self, event):
        was_pressed = self.pressed
        self._state(pressed=False)

        if (
            was_pressed
            and 0 <= event.x <= self.winfo_width()
            and 0 <= event.y <= self.winfo_height()
        ):
            self.command()

    def _draw(self, event=None):
        self.delete("art")
        w, h = self.winfo_width(), self.winfo_height()

        if w < 12 or h < 12:
            return

        glass(self, (4, 4, w - 5, h - 5), self.style, 11)

        if self.hover or self.focus_get() == self:
            rounded_outline(
                self, (4, 4, w - 5, h - 5), 11, WHITE, 1.4,
            )

        if self.pressed:
            rounded_outline(
                self, (6, 6, w - 7, h - 7), 9, "#17333D", 2,
            )

        color = "#092C35" if self.style == "cyan" else WHITE
        shift = 1 if self.pressed else 0
        text_width = tkfont.Font(font=self.font).measure(self.text)
        extra = 30 if self.icon_name else 0
        left = (w - text_width - extra) / 2

        if self.icon_name:
            icon(
                self, self.icon_name,
                left + 9, h / 2 + shift, color,
            )

        self.create_text(
            left + extra, h / 2 + shift,
            text=self.text,
            anchor="w",
            fill=color,
            font=self.font,
            tags="art",
        )


class RoundedEntry(tk.Canvas):
    """Однотонное поле ввода со сглаженной рамкой."""

    def __init__(self, parent, variable, placeholder, icon_name=None):
        super().__init__(
            parent,
            bg=parent.cget("bg"),
            height=42,
            width=100,
            highlightthickness=0,
            bd=0,
        )
        self.icon_name = icon_name

        self.entry = tk.Entry(
            self,
            textvariable=variable,
            bg="#311344",
            fg=WHITE,
            insertbackground=CYAN,
            relief="flat",
            bd=0,
            font=("Segoe UI", -18),
        )
        self.placeholder = tk.Label(
            self,
            text=placeholder,
            bg="#311344",
            fg=MUTED,
            font=("Segoe UI", -17),
            anchor="w",
        )
        self.placeholder.bind(
            "<Button-1>",
            lambda event: self.entry.focus_set(),
        )

        x = 42 if icon_name else 16
        self.entry_id = self.create_window(
            x, 21, anchor="w", window=self.entry,
        )
        self.placeholder_id = self.create_window(
            x, 21, anchor="w", window=self.placeholder,
        )

        def toggle_placeholder(*args):
            visible = (
                not variable.get()
                and self.focus_get() != self.entry
            )
            self.itemconfigure(
                self.placeholder_id,
                state="normal" if visible else "hidden",
            )

        variable.trace_add("write", toggle_placeholder)
        self.entry.bind("<FocusIn>", toggle_placeholder)
        self.entry.bind("<FocusOut>", toggle_placeholder)
        self.bind("<Configure>", self._draw)

    def _draw(self, event=None):
        self.delete("art")
        w, h = self.winfo_width(), self.winfo_height()
        glass(self, (4, 4, w - 5, h - 5), "input", 10)

        if self.icon_name:
            icon(self, self.icon_name, 24, h / 2, CYAN)

        x = 42 if self.icon_name else 16
        self.coords(self.entry_id, x, h / 2)
        self.coords(self.placeholder_id, x, h / 2)
        self.itemconfigure(
            self.entry_id, width=max(10, w - x - 15),
        )
        self.itemconfigure(
            self.placeholder_id, width=max(10, w - x - 15),
        )
        self.tag_raise(self.entry_id)
        self.tag_raise(self.placeholder_id)


class NeonScrollbar(tk.Canvas):
    """Бирюзовый бегунок прокрутки."""

    def __init__(self, parent, target):
        super().__init__(
            parent,
            width=23,
            bg=parent.cget("bg"),
            highlightthickness=0,
            bd=0,
            takefocus=1,
        )
        self.target = target
        self.first, self.last, self.drag_offset = 0, 1, 0

        self.bind("<Configure>", self._draw)
        self.bind("<Button-1>", self._press)
        self.bind("<B1-Motion>", self._drag)
        self.bind(
            "<Up>",
            lambda event: target.yview_scroll(-1, "units"),
        )
        self.bind(
            "<Down>",
            lambda event: target.yview_scroll(1, "units"),
        )

    def set(self, first, last):
        self.first, self.last = float(first), float(last)
        self._draw()

    def _geometry(self):
        track = max(1, self.winfo_height() - 42)
        length = min(
            track, max(28, track * (self.last - self.first)),
        )
        travel = track - length
        ratio = self.first / max(
            0.0001, 1 - (self.last - self.first),
        )
        return 21 + travel * ratio, length, travel

    def _draw(self, event=None):
        self.delete("art")
        h = self.winfo_height()

        if h < 48:
            return

        rounded_outline(
            self, (2, 2, 21, h - 2), 9, "#C6A5DC",
        )
        self.create_line(
            7, 13, 12, 8, 17, 13,
            fill=WHITE, width=2, tags="art",
        )
        self.create_line(
            7, h - 13, 12, h - 8, 17, h - 13,
            fill=WHITE, width=2, tags="art",
        )

        top, length, _ = self._geometry()
        glass(self, (6, top, 17, top + length), "cyan", 5)

    def _press(self, event):
        self.focus_set()

        if event.y < 21:
            self.target.yview_scroll(-1, "units")
        elif event.y > self.winfo_height() - 21:
            self.target.yview_scroll(1, "units")
        else:
            top, length, _ = self._geometry()
            self.drag_offset = (
                event.y - top
                if top <= event.y <= top + length
                else length / 2
            )
            self._drag(event)

    def _drag(self, event):
        _, _, travel = self._geometry()
        position = max(
            0,
            min(
                1,
                (event.y - 21 - self.drag_offset) / max(1, travel),
            ),
        )
        self.target.yview_moveto(
            position * (1 - (self.last - self.first)),
        )


class TaskCard(tk.Canvas):
    """Демонстрационная карточка задачи."""

    def __init__(
        self, parent, app, title, when, status,
        priority, style, priority_style,
    ):
        super().__init__(
            parent,
            bg=parent.cget("bg"),
            height=112,
            width=300,
            bd=0,
            highlightthickness=0,
        )
        self.app, self.title, self.when = app, title, when
        self.status, self.priority = status, priority
        self.style, self.priority_style = style, priority_style

        self.details = NeonButton(
            self,
            "Открыть подробности",
            lambda: app.stage_message(f"Подробности: {title}"),
            icon_name="arrow",
            height=32,
            width=250,
            font_size=15,
            bold=False,
        )
        self.details_id = self.create_window(
            0, 0, window=self.details, anchor="nw",
        )
        self.bind("<Configure>", self._draw)

    def _draw(self, event=None):
        self.delete("art")
        w = self.winfo_width()

        if w < 50:
            return

        glass(self, (4, 4, w - 6, 105), self.style, 12)
        glass(
            self,
            (18, 36, 43, 61),
            "green" if self.status == "Готово" else "purple",
            5,
        )

        if self.status == "Готово":
            self.create_line(
                23, 48, 28, 53, 38, 42,
                fill=WHITE, width=3, tags="art",
            )

        self.create_line(
            58, 17, 58, 93, fill="#A68AB8", tags="art",
        )

        badge_width = min(265, int(w * 0.42))
        badge_x = w - badge_width - 14
        title_font = tkfont.Font(
            family="Segoe UI", size=-21, weight="bold",
        )
        available = max(15, badge_x - 84)
        text = self.title

        while text and title_font.measure(text) > available:
            text = text[:-1]

        if text != self.title:
            text = text[:-1] + "…"

        self.create_text(
            74, 31, text=text, font=title_font,
            fill=WHITE, anchor="w", tags="art",
        )
        icon(self, "calendar", 84, 69, size=17)
        self.create_text(
            102, 69, text=self.when,
            font=("Segoe UI", -16),
            fill=WHITE, anchor="w", tags="art",
        )

        status_style = {
            "Ожидает": "blue",
            "Готово": "green",
            "Просрочено": "red",
            "Отменено": "violet",
        }[self.status]

        glass(
            self, (w - 166, 13, w - 17, 37),
            status_style, 8,
        )
        status_icon = {
            "Готово": "check",
            "Просрочено": "warning",
            "Отменено": "cancel",
        }.get(self.status, "clock")

        icon(self, status_icon, w - 149, 25, size=15)
        self.create_text(
            w - 132, 25, text=self.status,
            fill=WHITE, font=("Segoe UI", -15),
            anchor="w", tags="art",
        )

        glass(
            self, (badge_x, 42, w - 17, 66),
            self.priority_style, 8,
        )
        self.create_text(
            (badge_x + w - 17) / 2, 54,
            text=self.priority,
            fill=(
                "#FFF3AC"
                if self.priority_style == "gold"
                else WHITE
            ),
            font=("Segoe UI", -13, "bold"),
            tags="art",
        )

        self.coords(self.details_id, badge_x - 3, 71)
        self.itemconfigure(
            self.details_id,
            width=badge_width + 1,
            height=32,
        )
        self.tag_raise(self.details_id)


class ReminderApp(tk.Tk):
    """Главное окно прототипа; действия подключаются отдельно."""

    def __init__(self):
        super().__init__()
        self.title("Мои напоминания — учебный прототип")
        self.geometry("1120x780")
        self.minsize(980, 700)
        self.configure(bg=BG)

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._build_header()
        self._build_body()
        self._update_clock()

        self.bind("<MouseWheel>", self._mouse_wheel)
        self.bind(
            "<Button-4>",
            lambda event: self._linux_wheel(event, -1),
        )
        self.bind(
            "<Button-5>",
            lambda event: self._linux_wheel(event, 1),
        )

    def label(
        self, parent, text, size=18,
        bold=False, color=WHITE,
    ):
        return tk.Label(
            parent,
            text=text,
            bg=parent.cget("bg"),
            fg=color,
            font=(
                "Segoe UI", -size,
                "bold" if bold else "normal",
            ),
            anchor="w",
        )

    def button(
        self, parent, text, style="teal",
        icon_name=None, **kwargs,
    ):
        return NeonButton(
            parent, text,
            lambda: self.stage_message(text),
            style, icon_name, **kwargs,
        )

    def _build_header(self):
        header = tk.Frame(self, bg=BG)
        header.grid(
            row=0, column=0, sticky="ew",
            padx=18, pady=(14, 12),
        )
        header.grid_columnconfigure(1, weight=1)

        bell = tk.Canvas(
            header, width=38, height=38,
            bg=BG, highlightthickness=0,
        )
        bell.grid(row=0, column=0, padx=(0, 10))
        glass(bell, (4, 4, 34, 34), "green", 7)

        bell.create_polygon(
            13, 24, 15, 20, 15, 15, 17, 12, 22, 12,
            25, 16, 25, 20, 28, 24,
            fill=WHITE, outline=WHITE,
        )
        bell.create_oval(
            18, 25, 23, 29, fill=WHITE, outline=WHITE,
        )

        self.label(
            header, "Мои напоминания", 26, True,
        ).grid(row=0, column=1, sticky="w")

        self.clock = tk.Canvas(
            header, width=400, height=39,
            bg=BG, highlightthickness=0,
        )
        self.clock.grid(row=0, column=2, sticky="e")
        glass(self.clock, (4, 4, 395, 34), "purple", 10)

        self.clock_id = self.clock.create_text(
            200, 19, fill=WHITE,
            font=("Segoe UI", -17, "bold"),
        )

    def _update_clock(self):
        now = datetime.now()
        self.clock.itemconfigure(
            self.clock_id,
            text=(
                f"Сейчас: {now.day} {MONTHS[now.month - 1]} "
                f"{now.year} · {now:%H:%M:%S}"
            ),
        )
        self.after(1000, self._update_clock)

    def _build_body(self):
        body = tk.Frame(
            self, bg=BG,
            highlightthickness=1,
            highlightbackground=CYAN,
        )
        body.grid(
            row=1, column=0, sticky="nsew",
            padx=14, pady=(0, 8),
        )
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        self._build_sidebar(body)
        self._build_content(body)

        self.label(
            self,
            "Учебный прототип · примеры задач · "
            "действия пока демонстрационные",
            12, color=MUTED,
        ).grid(
            row=2, column=0, sticky="w",
            padx=20, pady=(0, 8),
        )

    def _build_sidebar(self, body):
        sidebar = tk.Frame(body, bg=PANEL, width=220)
        sidebar.grid(row=0, column=0, sticky="ns")
        sidebar.grid_propagate(False)
        sidebar.grid_columnconfigure(0, weight=1)
        sidebar.grid_rowconfigure(6, weight=1)

        self.label(
            sidebar, "Напоминания", 25, True,
        ).grid(
            row=0, column=0, sticky="w",
            padx=12, pady=(12, 10),
        )

        sections = (
            ("Все задачи", "teal", "calendar"),
            ("Ожидает", "blue", "clock"),
            ("Просрочено", "red", "warning"),
            ("Готово", "green", "check"),
            ("Отменено", "violet", "cancel"),
        )

        for row, (text, style, picture) in enumerate(sections, 1):
            self.button(
                sidebar, text, style, picture, font_size=19,
            ).grid(
                row=row, column=0, sticky="ew",
                padx=10, pady=3,
            )

        self.button(
            sidebar, "Настройки",
            icon_name="gear", font_size=19,
        ).grid(
            row=7, column=0, sticky="ew",
            padx=10, pady=12,
        )

    def _build_content(self, body):
        content = tk.Frame(body, bg=BG)
        content.grid(
            row=0, column=1, sticky="nsew",
            padx=10, pady=8,
        )
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(7, weight=1)

        toolbar = tk.Frame(content, bg=BG)
        toolbar.grid(
            row=0, column=0, sticky="ew", pady=(0, 4),
        )
        toolbar.grid_columnconfigure(0, weight=1)

        self.label(
            toolbar, "Все задачи", 28, True,
        ).grid(row=0, column=0, sticky="w")

        self.button(
            toolbar, "Все даты",
            icon_name="calendar", height=36, width=160,
        ).grid(row=0, column=1)

        self.search_text = tk.StringVar()
        search = tk.Frame(content, bg=BG)
        search.grid(
            row=1, column=0, sticky="ew", pady=(0, 6),
        )
        search.grid_columnconfigure(0, weight=1)

        RoundedEntry(
            search, self.search_text,
            "Поиск по всем датам", "search",
        ).grid(row=0, column=0, sticky="ew")

        self.button(
            search, "Найти", "cyan", height=42, width=150,
        ).grid(row=0, column=1, padx=(8, 0))

        self.button(
            content, "План на неделю",
            icon_name="calendar", height=44, font_size=21,
        ).grid(
            row=2, column=0, sticky="ew", pady=(0, 6),
        )

        self.label(
            content, "Новая задача", 22, True,
        ).grid(row=3, column=0, sticky="w")

        self.new_title = tk.StringVar()
        new_row = tk.Frame(content, bg=BG)
        new_row.grid(
            row=4, column=0, sticky="ew", pady=(3, 4),
        )
        new_row.grid_columnconfigure(0, weight=1)

        RoundedEntry(
            new_row, self.new_title, "Что нужно сделать?",
        ).grid(row=0, column=0, sticky="ew")

        self.button(
            new_row, "Продиктовать",
            "cyan", "mic", width=200,
        ).grid(row=0, column=1, padx=(8, 0))

        self.button(
            content, "+ Добавить задачу",
            "cyan", font_size=21, height=44,
        ).grid(
            row=5, column=0, sticky="ew", pady=(0, 5),
        )

        templates = tk.Frame(content, bg=BG)
        templates.grid(
            row=6, column=0, sticky="ew", pady=(0, 8),
        )
        templates.grid_columnconfigure(1, weight=1)
        templates.grid_columnconfigure(2, weight=1)

        self.label(
            templates, "Шаблоны", 18, True,
        ).grid(row=0, column=0, padx=(0, 6))

        self.button(
            templates, "Проверить остатки",
            "purple", "box",
            height=34, font_size=14, bold=False,
        ).grid(row=0, column=1, sticky="ew", padx=3)

        self.button(
            templates, "Связаться с поставщиком",
            "purple", "phone",
            height=34, font_size=14, bold=False,
        ).grid(row=0, column=2, sticky="ew", padx=3)

        self._build_list(content)

        footer = tk.Frame(content, bg=BG)
        footer.grid(
            row=8, column=0, sticky="ew", pady=(6, 0),
        )
        footer.grid_columnconfigure(0, weight=1)

        self.label(
            footer, "Галочка — задача выполнена",
            13, color=MUTED,
        ).grid(row=0, column=0, sticky="w")

        self.button(
            footer, "Пример уведомления", "purple",
            height=32, width=210, font_size=14, bold=False,
        ).grid(row=0, column=1)

    def _build_list(self, content):
        self.list_frame = tk.Frame(content, bg=BG)
        self.list_frame.grid(row=7, column=0, sticky="nsew")
        self.list_frame.grid_columnconfigure(0, weight=1)
        self.list_frame.grid_rowconfigure(0, weight=1)

        self.tasks_canvas = tk.Canvas(
            self.list_frame,
            bg=BG,
            width=100,
            height=200,
            bd=0,
            highlightthickness=0,
            yscrollincrement=24,
        )
        self.tasks_canvas.grid(
            row=0, column=0, sticky="nsew",
        )

        self.scrollbar = NeonScrollbar(
            self.list_frame, self.tasks_canvas,
        )
        self.scrollbar.grid(
            row=0, column=1, sticky="ns", padx=(3, 0),
        )
        self.tasks_canvas.configure(
            yscrollcommand=self.scrollbar.set,
        )

        cards = tk.Frame(self.tasks_canvas, bg=BG)
        window = self.tasks_canvas.create_window(
            (0, 0), window=cards, anchor="nw",
        )

        self.tasks_canvas.bind(
            "<Configure>",
            lambda event: self.tasks_canvas.itemconfigure(
                window, width=event.width,
            ),
        )
        cards.bind(
            "<Configure>",
            lambda event: self.tasks_canvas.configure(
                scrollregion=self.tasks_canvas.bbox("all"),
            ),
        )

        examples = (
            (
                "Проверить остатки", "16 ноября, 10:00",
                "Ожидает", "☆ Важная, не срочная",
                "blue", "gold",
            ),
            (
                "Связаться с поставщиком", "16 ноября, 11:00",
                "Ожидает", "◷ Неважная, но срочная",
                "purple", "blue",
            ),
            (
                "Сверить накладные", "16 ноября, 09:00",
                "Готово", "— Неважная и не срочная",
                "green", "gray",
            ),
            (
                "Подтвердить встречу", "16 ноября, 08:00",
                "Просрочено", "★ ◷ Важная и срочная",
                "purple", "orange",
            ),
            (
                "Проверить старый заказ", "15 ноября, 15:00",
                "Отменено", "— Неважная и не срочная",
                "violet", "gray",
            ),
        )

        for example in examples:
            TaskCard(
                cards, self, *example,
            ).pack(fill="x", pady=(0, 3))

    def _inside_list(self, widget):
        while widget is not None:
            if widget == self.list_frame:
                return True
            widget = getattr(widget, "master", None)
        return False

    def _mouse_wheel(self, event):
        widget = self.winfo_containing(
            event.x_root, event.y_root,
        )
        if self._inside_list(widget) and event.delta:
            if abs(event.delta) >= 120:
                units = -int(event.delta / 120)
            else:
                units = -1 if event.delta > 0 else 1
            self.tasks_canvas.yview_scroll(units, "units")
            return "break"

    def _linux_wheel(self, event, units):
        if self._inside_list(event.widget):
            self.tasks_canvas.yview_scroll(units, "units")
            return "break"

    def stage_message(self, action):
        messagebox.showinfo(
            "Учебный прототип — оформление",
            f"{action}\n\n"
            "Сейчас проверяем оформление главного экрана. "
            "Действия с задачами и переходы подключим "
            "следующим этапом.\n\n"
            "Карточки содержат демонстрационные данные.",
            parent=self,
        )


# КОНЕЦ ФАЙЛА gui.py