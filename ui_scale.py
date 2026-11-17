"""Масштаб интерфейса: шрифты, поля, изображения и координаты кнопок."""

import copy
import math
import re
from functools import lru_cache
import tkinter as tk
from tkinter import font as tkfont
from PIL import Image, ImageTk


MIN_SCALE, MAX_SCALE = 0.35, 1.25
MIN_WIDTH, MIN_HEIGHT = 460, 340
_installed = False
_canvas_create = tk.Canvas._create
_canvas_coords = tk.Canvas.coords
_canvas_itemconfigure = tk.Canvas.itemconfigure
_native_width = tk.Misc.winfo_width
_native_height = tk.Misc.winfo_height


def bounded(value):
    return round(max(MIN_SCALE, min(MAX_SCALE, float(value))), 4)


def fitting(width, height):
    return bounded(min(width / 1120, height / 780, 1.0))


def needs_scroll(text, first, last):
    return bool(text) and (float(first) > 0.00001 or float(last) < 0.99999)


def field_layout(width, scrolling):
    return (width-75, max(20, width-102)) if scrolling else (width-55, max(20, width-82))


def fast_surfaces(original):
    """Растягивать прямую середину плашки, сохраняя её сглаженные углы."""
    @lru_cache(maxsize=96)
    def surface(width, height, radius, style, border_color, border_width):
        cap = math.ceil(min(radius, (height-1)/2, (width-1)/2)) + 12
        narrow = min(width, max(48, 2*cap-8))
        image = original(narrow, height, radius, style, border_color, border_width)
        if width == narrow:
            return image
        result = Image.new("RGBA", (width+10, height+10))
        result.paste(image.crop((0, 0, cap, image.height)), (0, 0))
        middle = image.crop((cap, 0, image.width-cap, image.height))
        result.paste(middle.resize((result.width-2*cap, image.height), Image.Resampling.LANCZOS), (cap, 0))
        result.paste(image.crop((image.width-cap, 0, image.width, image.height)), (result.width-cap, 0))
        return result
    return surface


def cached_draw(method):
    """Повторный вызов с тем же состоянием не создаёт те же изображения."""
    def wrapped(self, event=None):
        attrs = ("text", "style", "font", "hover", "pressed", "selected", "title",
                 "when", "status", "priority", "priority_style", "focused",
                 "voice_state", "placeholder", "icon_name", "first", "last", "_scroll_visible")
        key = (_native_width(self), _native_height(self), factor(self), self.focus_get(),
               *(getattr(self, name, None) for name in attrs))
        if hasattr(self, "entry") and isinstance(self.entry, tk.Text):
            key += (self.get(), self.entry.cget("font"))
        elif hasattr(self, "variable"):
            key += (self.variable.get(),)
        if getattr(self, "_last_draw", None) == key:
            return
        method(self, event)
        self._last_draw = key
    return wrapped


def factor(widget):
    parent = widget
    while parent is not None:
        if getattr(parent, "_scale_fixed", False):
            return 1.0
        parent = getattr(parent, "master", None)
    manager = getattr(widget._root(), "_ui_scale", None)
    return manager.value if manager is not None else 1.0


def zoom_geometry(value):
    """Оставить место для читаемой панели масштаба даже при 35%."""
    return (max(MIN_WIDTH, round(1120*value + max(0, 146-220*value))),
            max(MIN_HEIGHT, round(780*value)))


def relative_scale(width, height, reference):
    base_width, base_height, scale = reference
    return bounded(scale * min(width/base_width, height/base_height))


def distance(widget, value, scale):
    """Перевести один отступ или пару отступов в физические пиксели."""
    if isinstance(value, (tuple, list)):
        return tuple(distance(widget, part, scale) for part in value)
    if isinstance(value, str):
        parts = widget.tk.splitlist(value)
        if len(parts) > 1:
            return tuple(distance(widget, part, scale) for part in parts)
        value = parts[0] if parts else "0"
    try:
        pixels = float(str(value))
    except ValueError:
        pixels = widget.winfo_fpixels(value)
    return round(pixels * scale)


def font_at(widget, value, scale):
    if scale == 1:
        return value
    if isinstance(value, tkfont.Font):
        font = value
    else:
        parts = widget.tk.splitlist(value) if isinstance(value, str) else value
        if isinstance(parts, (tuple, list)) and len(parts) >= 2:
            try:
                size = int(parts[1])
                size = (-1 if size < 0 else 1) * max(6, round(abs(size)*scale))
                return (parts[0], size, *parts[2:])
            except (TypeError, ValueError):
                pass
        font = tkfont.Font(root=widget, font=value)
    size = int(font.cget("size"))
    size = (-1 if size < 0 else 1) * max(6, round(abs(size)*scale))
    actual = font.actual()
    styles = [actual["weight"], actual["slant"]]
    if actual["underline"]:
        styles.append("underline")
    if actual["overstrike"]:
        styles.append("overstrike")
    return (actual["family"], size, " ".join(styles))


def item_options(widget, options, scale):
    result = dict(options)
    for key in ("width", "height", "activewidth", "disabledwidth"):
        if key in result and result[key] is not None:
            result[key] = float(result[key]) * scale
    if "font" in result:
        result["font"] = font_at(widget, result["font"], scale)
    if "dash" in result and isinstance(result["dash"], (tuple, list)):
        result["dash"] = tuple(max(1, round(float(x)*scale)) for x in result["dash"])
    return result


def install_scaling():
    """Подключить перевод координат до создания главного окна."""
    global _installed
    if _installed:
        return
    import gui
    import input_widgets
    from demo_completion import CompletionCard
    _installed = True
    gui._surface = fast_surfaces(gui._surface)

    for cls in (gui.NeonButton, gui.RoundedEntry, gui.NeonScrollbar,
                gui.TaskCard, input_widgets.VoiceField):
        cls._scaled_canvas = True

    def virtual_width(self):
        width = _native_width(self)
        return max(1, round(width/factor(self))) if getattr(self, "_scaled_canvas", False) else width

    def virtual_height(self):
        height = _native_height(self)
        return max(1, round(height/factor(self))) if getattr(self, "_scaled_canvas", False) else height

    def create(self, kind, args, options):
        if not getattr(self, "_scaled_canvas", False):
            return _canvas_create(self, kind, args, options)
        scale = factor(self)
        values = tk._flatten(args)
        if values and isinstance(values[-1], dict):
            options = {**values[-1], **options}
            values = values[:-1]
        return _canvas_create(self, kind, tuple(float(x)*scale for x in values),
                              item_options(self, options, scale))

    def coords(self, *args):
        if not getattr(self, "_scaled_canvas", False) or not args:
            return _canvas_coords(self, *args)
        scale = factor(self)
        values = tk._flatten(args[1:])
        if values:
            return _canvas_coords(self, args[0], *(float(x)*scale for x in values))
        return [x/scale for x in _canvas_coords(self, *args)]

    def configure_item(self, item, cnf=None, **kw):
        if getattr(self, "_scaled_canvas", False) and (isinstance(cnf, dict) or kw):
            options = {**(cnf or {}), **kw}
            return _canvas_itemconfigure(self, item, **item_options(self, options, factor(self)))
        return _canvas_itemconfigure(self, item, cnf, **kw)

    tk.Canvas.winfo_width = virtual_width
    tk.Canvas.winfo_height = virtual_height
    tk.Canvas._create = create
    tk.Canvas.coords = coords
    tk.Canvas.itemconfigure = configure_item
    tk.Canvas.itemconfig = configure_item

    original_image = gui._place_image
    # Плашки рисуем сразу в конечном размере. Раньше каждую сначала
    # создавали большой, затем ещё раз уменьшали при каждом движении окна.
    def draw_surface(canvas, box, radius, style, color, line, tag):
        x1, y1, x2, y2 = box
        scale = factor(canvas) if getattr(canvas, "_scaled_canvas", False) else 1
        width, height = round((x2-x1+1)*scale), round((y2-y1+1)*scale)
        if width < 4 or height < 4:
            return
        image = gui._surface(width, height, radius*scale, style, color, line*scale)
        original_image(canvas, image, x1-5/scale, y1-5/scale, tag)

    def glass(canvas, box, style="purple", radius=12, tag="art"):
        draw_surface(canvas, box, radius, style, gui.STYLES[style][2], 1.2, tag)

    def outline(canvas, box, radius, color, width=1, tag="art"):
        draw_surface(canvas, box, radius, None, color, width, tag)

    gui.glass = input_widgets.glass = glass
    gui.rounded_outline = outline

    def place_image(canvas, image, x, y, tag):
        scale = factor(canvas) if getattr(canvas, "_scaled_canvas", False) else 1
        if scale != 1:
            image = image.resize((max(1, round(image.width*scale)),
                                  max(1, round(image.height*scale))), Image.Resampling.LANCZOS)
        original_image(canvas, image, x, y, tag)
    gui._place_image = place_image
    input_widgets._place_image = place_image

    def logical_pointer(method):
        def wrapped(self, event):
            if not getattr(event, "_logical_pointer", False):
                event = copy.copy(event)
                event.x, event.y = event.x/factor(self), event.y/factor(self)
                event._logical_pointer = True
            return method(self, event)
        return wrapped

    for cls, name in ((gui.NeonButton, "_release"),
                      (gui.NeonScrollbar, "_press"), (gui.NeonScrollbar, "_drag"),
                      (CompletionCard, "_inside_checkbox")):
        setattr(cls, name, logical_pointer(getattr(cls, name)))

    def resize_lines(self):
        self.pending = None
        lines = self.entry.count("1.0", "end-1c", "displaylines")
        count = min(self.max_lines, max(1, (lines[0] if lines else 0)+1))
        line = tkfont.Font(root=self, font=self.entry.cget("font")).metrics("linespace")
        height = max(round(self.minimum_height*factor(self)), round(28*factor(self))+count*line)
        if int(self.cget("height")) != height:
            self.configure(height=height)
    input_widgets.VoiceField.resize_lines = resize_lines

    original_field_init = input_widgets.VoiceField.__init__
    original_field_draw = input_widgets.VoiceField.draw

    def field_init(self, *args, **kwargs):
        self._scroll_visible = False
        self._scroll_redraw = None
        original_field_init(self, *args, **kwargs)
        def scroll_changed(first, last):
            self.scroll.set(first, last)
            show = needs_scroll(self.get(), first, last)
            if self._scroll_visible != show:
                self._scroll_visible = show
                if self._scroll_redraw is None:
                    def refresh_field():
                        self._scroll_redraw = None
                        if self.winfo_exists():
                            self.draw()
                    self._scroll_redraw = self.after_idle(refresh_field)
        def destroy_field(event):
            if event.widget == self and self._scroll_redraw is not None:
                self.after_cancel(self._scroll_redraw)
                self._scroll_redraw = None
        self.entry.configure(yscrollcommand=scroll_changed)
        self.bind("<Destroy>", destroy_field, add="+")

    def field_draw(self, event=None):
        original_field_draw(self, event)
        width = self.winfo_width()
        if width < 30:
            return
        mic_x, text_width = field_layout(width, self._scroll_visible)
        self.coords(self.mic_id, mic_x, 9)
        self.itemconfigure(self.text_id, width=text_width)
        self.itemconfigure(self.scroll_id, state="normal" if self._scroll_visible else "hidden")
        self.itemconfigure("placeholder", width=max(20, text_width-6))

    input_widgets.VoiceField.__init__ = field_init
    input_widgets.VoiceField.draw = cached_draw(field_draw)
    for cls in (gui.NeonButton, gui.RoundedEntry, gui.NeonScrollbar, gui.TaskCard):
        cls._draw = cached_draw(cls._draw)

    original_geometry = tk.Wm.geometry
    original_toplevel_init = tk.Toplevel.__init__

    def tracked_geometry(self, newGeometry=None):
        if newGeometry:
            self._scale_requested_geometry = newGeometry
        return original_geometry(self, newGeometry)

    def toplevel_init(self, *args, **kwargs):
        original_toplevel_init(self, *args, **kwargs)
        if self.__class__.__name__ != "ReminderEditor":
            return
        # Собираем форму скрытой: первый видимый кадр уже в нужном масштабе.
        self.withdraw()
        def reveal():
            self._scale_reveal_timer = None
            if not self.winfo_exists():
                return
            manager = getattr(self._root(), "_ui_scale", None)
            if manager is not None:
                if getattr(manager, "zoom_timer", None) is not None or getattr(manager, "resize_timer", None) is not None:
                    self._scale_reveal_timer = self.after(16, reveal)
                    return
                manager.prepare_window(self)
            self.update_idletasks()
            self.deiconify()
            self.lift()
            field = getattr(self, "name_field", None)
            if field is not None:
                field.activate()
        def cancel_reveal(event):
            if event.widget == self and self._scale_reveal_timer is not None:
                self.after_cancel(self._scale_reveal_timer)
                self._scale_reveal_timer = None
        self._scale_reveal_timer = self.after_idle(reveal)
        self.bind("<Destroy>", cancel_reveal, add="+")

    tk.Wm.geometry = tracked_geometry
    tk.Wm.wm_geometry = tracked_geometry
    tk.Toplevel.__init__ = toplevel_init


class ScaleController:
    """Видимая панель масштаба; подгонка по окну всегда включена."""

    def __init__(self, app):
        self.app, self.value = app, 1.0
        self.snapshots = {}
        self.scan_timer = self.resize_timer = self.redraw_timer = self.zoom_timer = None
        self.zoom_goal = 1.0
        self.reference = (1120, 780, 1.0)
        self.last_window_size = None
        self.auto = tk.BooleanVar(app, True)
        app._ui_scale = self
        app.minsize(MIN_WIDTH, MIN_HEIGHT)
        self.build_panel()
        app.bind("<Configure>", self.window_changed, add="+")
        app.bind_all("<Map>", self.new_widget, add="+")
        app.bind("<Destroy>", self.cleanup, add="+")
        self.scan()
        self.schedule_fit()

    def build_panel(self):
        from gui import NeonButton, PANEL, WHITE, MUTED
        self.sidebar = self.app.filter_buttons[None].master
        self.panel = tk.Frame(self.sidebar, bg=PANEL)
        # Управление остаётся читаемым независимо от масштаба содержимого.
        self.panel._scale_fixed = True
        self.panel.grid(row=6, column=0, sticky="sew", padx=8, pady=(6, 0))
        self.panel.grid_columnconfigure(0, weight=1)
        tk.Label(self.panel, text="Масштаб", bg=PANEL, fg=WHITE,
                 font=("Segoe UI", -14, "bold"), anchor="w").grid(
                     row=0, column=0, sticky="ew", pady=(0, 3))
        controls = tk.Frame(self.panel, bg=PANEL)
        controls.grid(row=1, column=0, sticky="ew")
        controls.grid_columnconfigure(1, weight=1)
        NeonButton(controls, "−", lambda: self.nudge(-.1), width=30,
                   height=32, font_size=18).grid(row=0, column=0)
        self.percent_button = NeonButton(controls, "100% ▾", self.show_choices,
                                        width=68, height=32, font_size=13)
        self.percent_button.grid(row=0, column=1, sticky="ew")
        NeonButton(controls, "+", lambda: self.nudge(.1), width=30,
                   height=32, font_size=18).grid(row=0, column=2)
        NeonButton(self.panel, "Вернуть 100%", lambda: self.choose(1),
                   width=110, height=29, font_size=12, bold=False).grid(
                       row=2, column=0, sticky="ew", pady=(2, 0))
        self.zoom_hint = tk.Label(self.panel, text="По размеру окна", bg=PANEL,
                                  fg=MUTED, font=("Segoe UI", -10), anchor="w")
        self.zoom_hint.grid(row=3, column=0, sticky="ew", pady=(2, 0))
        self.choices = tk.Menu(self.panel, tearoff=False)
        for percent in (35, 50, 65, 75, 85, 100, 125):
            label = f"{percent}%" + (" — рекомендуется" if percent in (75, 100) else "")
            self.choices.add_command(label=label, command=lambda p=percent: self.choose(p/100))

    def show_choices(self):
        button = self.percent_button
        try:
            self.choices.tk_popup(button.winfo_rootx(), button.winfo_rooty()+_native_height(button))
        finally:
            self.choices.grab_release()

    def update_panel(self):
        self.percent_button.text = f"{round(self.value*100)}% ▾"
        self.percent_button._draw()
        self.zoom_hint.configure(text="Мелко · лучше 75–100%" if self.value < .65 else "По размеру окна",
                                 fg="#FFD48A" if self.value < .65 else "#D9C9E7")

    def walk(self, parent):
        for child in parent.winfo_children():
            if not isinstance(child, tk.Menu):
                yield child
                yield from self.walk(child)

    def remember(self, widget):
        if widget in self.snapshots:
            return False
        options = widget.configure()
        lengths = ("padx", "pady", "borderwidth", "highlightthickness",
                   "wraplength", "insertwidth", "yscrollincrement")
        if isinstance(widget, (tk.Canvas, tk.Frame, tk.Toplevel)):
            lengths += ("width", "height")
        values = {key: widget.cget(key) for key in lengths if key in options}
        if hasattr(widget, "minimum_height"):
            values["height"] = widget.minimum_height
        if "font" in options:
            values["font"] = widget.cget("font")
        layout = {}
        manager = widget.winfo_manager()
        if manager in ("grid", "pack"):
            info = widget.grid_info() if manager == "grid" else widget.pack_info()
            layout = {key: info[key] for key in ("padx", "pady", "ipadx", "ipady") if key in info}
        saved = {"values": values, "manager": manager, "layout": layout, "static": []}
        if isinstance(widget, tk.Toplevel):
            saved["minsize"] = widget.minsize()
            saved["geometry"] = getattr(widget, "_scale_requested_geometry", None) or widget.geometry()
        if isinstance(widget, tk.Canvas) and not getattr(widget, "_scaled_canvas", False):
            for item in widget.find_all():
                kind = widget.type(item)
                if kind == "window":
                    continue
                item_data = {"item": item, "coords": _canvas_coords(widget, item), "options": {}}
                if kind == "text":
                    item_data["options"]["font"] = widget.itemcget(item, "font")
                if kind == "image":
                    photo = getattr(widget, "_smooth_images", {}).get(item)
                    if photo is None:
                        continue
                    item_data["image"] = ImageTk.getimage(photo)
                saved["static"].append(item_data)
        self.snapshots[widget] = saved
        return True

    def apply(self, widget):
        saved = self.snapshots[widget]
        scale = factor(widget)
        options = {}
        for key, value in saved["values"].items():
            options[key] = font_at(widget, value, scale) if key == "font" else distance(widget, value, scale)
        if widget is self.sidebar:
            options["width"] = max(146, options.get("width", 146))
        changed = {key: value for key, value in options.items()
                   if saved.get("applied_values", {}).get(key) != value}
        if changed:
            widget.configure(**changed)
        saved["applied_values"] = options
        layout = {key: distance(widget, value, scale) for key, value in saved["layout"].items()}
        if layout and layout != saved.get("applied_layout"):
            if saved["manager"] == "grid":
                widget.grid_configure(**layout)
            elif saved["manager"] == "pack":
                widget.pack_configure(**layout)
            saved["applied_layout"] = layout
        if "minsize" in saved:
            minimum = tuple(max(1, round(x*scale)) for x in saved["minsize"])
            if minimum != saved.get("applied_minimum"):
                widget.minsize(*minimum)
                saved["applied_minimum"] = minimum
            match = re.match(r"(\d+)x(\d+)", saved["geometry"])
            if match:
                width, height = (max(1, round(int(x)*scale)) for x in match.groups())
                geometry = f"{width}x{height}"
                if geometry != saved.get("applied_geometry"):
                    widget.geometry(geometry)
                    saved["applied_geometry"] = geometry
        for data in saved["static"]:
            item = data["item"]
            if not widget.type(item):
                continue
            _canvas_coords(widget, item, *(x*scale for x in data["coords"]))
            if data["options"]:
                _canvas_itemconfigure(widget, item, **item_options(widget, data["options"], scale))
            if "image" in data:
                image = data["image"]
                size = (max(1, round(image.width*scale)), max(1, round(image.height*scale)))
                if size != data.get("render_size"):
                    photo = ImageTk.PhotoImage(image.resize(size, Image.Resampling.LANCZOS), master=widget)
                    data["photo"] = photo
                    data["render_size"] = size
                    _canvas_itemconfigure(widget, item, image=photo)

    def redraw(self):
        self.redraw_timer = None
        for widget in list(self.snapshots):
            if not widget.winfo_exists():
                del self.snapshots[widget]
                continue
            if getattr(widget, "_scaled_canvas", False):
                method = getattr(widget, "draw", None) or getattr(widget, "_draw", None)
                if method is not None:
                    method()

    def scan(self):
        self.scan_timer = None
        fresh = []
        for widget in self.walk(self.app):
            if self.remember(widget):
                self.apply(widget)
                fresh.append(widget)
        for widget in fresh:
            if getattr(widget, "_scaled_canvas", False):
                method = getattr(widget, "draw", None) or getattr(widget, "_draw", None)
                if method is not None:
                    method()
        for widget in list(self.snapshots):
            if not widget.winfo_exists():
                del self.snapshots[widget]

    def new_widget(self, event):
        if self.scan_timer is None:
            self.scan_timer = self.app.after_idle(self.scan)

    def prepare_window(self, window):
        for widget in (window, *self.walk(window)):
            if self.remember(widget):
                self.apply(widget)

    def set_scale(self, value):
        value = bounded(value)
        if value == self.value:
            return
        self.scan()
        self.value = value
        for widget in list(self.snapshots):
            if widget.winfo_exists():
                self.apply(widget)
        self.update_panel()
        if self.redraw_timer is not None:
            self.app.after_cancel(self.redraw_timer)
        self.redraw_timer = self.app.after_idle(self.redraw)

    def choose(self, value):
        # Выбор процента не отключает реакцию на растягивание окна.
        self.auto.set(True)
        self.stop_animation()
        value = bounded(value)
        width, height = zoom_geometry(value)
        if self.app.state() == "normal":
            self.reference = (width, height, value)
            self.last_window_size = (width, height)
            self.app.geometry(f"{width}x{height}")
        else:
            self.reference = (self.app.winfo_width(), self.app.winfo_height(), value)
        # Один согласованный переход вместо серии тяжёлых промежуточных кадров.
        self.set_scale(value)

    def nudge(self, amount):
        self.choose(self.value+amount)

    def stop_animation(self):
        if self.zoom_timer is not None:
            self.app.after_cancel(self.zoom_timer)
            self.zoom_timer = None

    def window_changed(self, event):
        if event.widget == self.app:
            size = (event.width, event.height)
            if size != self.last_window_size:
                self.last_window_size = size
                self.schedule_fit()

    def schedule_fit(self):
        if self.resize_timer is None:
            self.resize_timer = self.app.after(24, self.fit)

    def fit(self):
        self.resize_timer = None
        self.stop_animation()
        self.set_scale(relative_scale(self.app.winfo_width(), self.app.winfo_height(), self.reference))

    def cleanup(self, event):
        if event.widget == self.app:
            for timer in (self.scan_timer, self.resize_timer, self.redraw_timer, self.zoom_timer):
                if timer is not None:
                    self.app.after_cancel(timer)
            self.snapshots.clear()


# КОНЕЦ ФАЙЛА ui_scale.py
