"""Скруглённые поля с переносом текста, вставкой мышью и микрофоном."""

import tkinter as tk
from tkinter import font as tkfont
from gui import WHITE, MUTED, CYAN, NeonButton, NeonScrollbar, glass
from gui import _beam_image, _place_image


def edit_menu(widget):
    """Меню мыши и сочетания клавиш, включая русскую раскладку Windows."""
    is_text = isinstance(widget, tk.Text)

    def selected():
        if is_text:
            return bool(widget.tag_ranges("sel"))
        return widget.selection_present()

    def action(kind):
        widget.focus_set()
        if kind == "all":
            if is_text:
                widget.tag_add("sel", "1.0", "end-1c")
            else:
                widget.selection_range(0, "end")
        elif kind == "paste":
            try:
                text = widget.clipboard_get()
            except tk.TclError:
                return "break"
            if selected():
                widget.delete("sel.first", "sel.last")
            widget.insert("insert", text)
            if is_text:
                widget.see("insert")
        elif kind in ("copy", "cut") and selected():
            text = (
                widget.get("sel.first", "sel.last")
                if is_text else
                widget.get()[widget.index("sel.first"):widget.index("sel.last")]
            )
            widget.clipboard_clear()
            widget.clipboard_append(text)
            if kind == "cut":
                widget.delete("sel.first", "sel.last")
        return "break"

    menu = tk.Menu(widget, tearoff=False)
    for label, kind in (
        ("Вставить", "paste"),
        ("Копировать", "copy"),
        ("Вырезать", "cut"),
        ("Выделить всё", "all"),
    ):
        menu.add_command(label=label, command=lambda value=kind: action(value))

    def popup(event):
        widget.focus_set()
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
        return "break"

    def keys(event):
        kind = {
            "v": "paste", "c": "copy", "x": "cut", "a": "all"
        }.get(event.keysym.lower())
        if widget.tk.call("tk", "windowingsystem") == "win32":
            kind = {
                86: "paste", 67: "copy", 88: "cut", 65: "all"
            }.get(event.keycode, kind)
        return action(kind) if kind else None

    widget.bind("<Button-3>", popup)
    widget.bind("<Control-KeyPress>", keys)
    widget.bind("<<Paste>>", lambda event: action("paste"))
    widget.bind("<<Copy>>", lambda event: action("copy"))
    widget.bind("<<Cut>>", lambda event: action("cut"))
    widget.show_edit_menu = popup
    return action


class ChoiceButton(NeonButton):
    """Закруглённый вариант приоритета с круглой отметкой выбора."""

    def __init__(self, parent, variable, value, text, style):
        self.variable, self.value, self.caption = variable, value, text
        super().__init__(
            parent, text, lambda: variable.set(value),
            style=style, height=45, font_size=15, bold=False,
        )
        self.trace = variable.trace_add("write", self.update_choice)
        self.bind("<Destroy>", self.cleanup, add="+")
        self.update_choice()

    def update_choice(self, *args):
        self.selected = self.variable.get() == self.value
        self.text = ("●  " if self.selected else "○  ") + self.caption
        self._draw()

    def cleanup(self, event):
        if event.widget == self:
            self.variable.trace_remove("write", self.trace)


class VoiceField(tk.Canvas):
    """Многострочное поле. Справа внутри рамки — микрофон и прокрутка."""

    def __init__(
        self, parent, app, variable=None, placeholder="",
        height=56, max_lines=None, animate=False,
    ):
        super().__init__(
            parent, bg=parent.cget("bg"), width=120, height=height,
            bd=0, highlightthickness=0, takefocus=1,
        )
        self.app, self.variable, self.placeholder = app, variable, placeholder
        self.animate, self.animation_allowed = animate, animate
        self.focused, self.phase, self.timer = False, 0, None
        self.voice_state, self.syncing, self.pending = "idle", False, None
        self.minimum_height, self.max_lines = height, max_lines

        self.entry = tk.Text(
            self, wrap="word", undo=True, height=1, width=10,
            bg="#311344", fg=WHITE, insertbackground=CYAN,
            selectbackground="#146CAE", exportselection=False,
            font=("Segoe UI", -18), relief="flat", bd=0,
            highlightthickness=0, padx=0, pady=0,
        )
        self.text_id = self.create_window(
            16, 14, window=self.entry, anchor="nw",
        )
        self.mic = NeonButton(
            self, "", lambda: app.voice.toggle(self),
            icon_name="mic", style="cyan", width=44, height=40,
        )
        self.mic_id = self.create_window(
            0, 11, window=self.mic, anchor="nw",
        )
        self.scroll = NeonScrollbar(self, self.entry)
        self.scroll_id = self.create_window(
            0, 8, window=self.scroll, anchor="nw",
        )
        self.entry.configure(yscrollcommand=self.scroll.set)
        self.entry.bind("<<Modified>>", self.changed)
        self.entry.bind("<FocusIn>", lambda event: self.focus(True))
        self.entry.bind("<FocusOut>", lambda event: self.focus(False))
        self.entry.bind("<MouseWheel>", self.wheel)
        self.entry.bind("<Button-4>", lambda event: self.scroll_linux(-1))
        self.entry.bind("<Button-5>", lambda event: self.scroll_linux(1))
        edit_menu(self.entry)

        self.bind("<Button-1>", lambda event: self.activate())
        self.bind("<Button-3>", self.popup)
        self.bind("<FocusIn>", lambda event: self.activate())
        self.bind("<Configure>", self.draw)
        self.bind("<Map>", lambda event: self.draw())
        self.bind("<Unmap>", lambda event: self.schedule())
        self.bind("<Destroy>", self.cleanup)

        self.trace = None
        if variable is not None:
            self.entry.insert("1.0", variable.get())
            self.trace = variable.trace_add("write", self.from_variable)
        self.entry.edit_modified(False)

    def get(self):
        return self.entry.get("1.0", "end-1c")

    def activate(self):
        self.itemconfigure(self.text_id, state="normal")
        self.entry.focus_set()

    def popup(self, event):
        self.activate()
        return self.entry.show_edit_menu(event)

    def focus(self, value):
        self.focused = value
        self.draw()

    def changed(self, event=None):
        if not self.entry.edit_modified():
            return
        self.entry.edit_modified(False)
        if not self.syncing and self.variable is not None:
            self.syncing = True
            try:
                self.variable.set(self.get())
            finally:
                self.syncing = False
        self.draw()

    def from_variable(self, *args):
        if self.syncing or self.get() == self.variable.get():
            return
        self.syncing = True
        try:
            self.entry.delete("1.0", "end")
            self.entry.insert("1.0", self.variable.get())
            self.entry.edit_modified(False)
        finally:
            self.syncing = False
        self.draw()

    def set_voice_state(self, state):
        self.voice_state = state
        self.mic.style = (
            "red" if state == "recording"
            else "gold" if state != "idle"
            else "cyan"
        )
        self.mic.icon_name = (
            "mic" if state in ("idle", "recording") else "clock"
        )
        self.mic.selected = state != "idle"
        self.mic.pressed = state == "recording"
        self.mic._draw()
        self.schedule()

    def insert_voice(self, text):
        self.activate()
        self.entry.edit_separator()
        where = self.entry.index("dictation")
        before = self.entry.get(f"{where}-1c", where)
        after = self.entry.get(where, f"{where}+1c")
        prefix = " " if before and not before.isspace() else ""
        suffix = " " if after and not after.isspace() else ""
        self.entry.insert(where, prefix + text + suffix)
        self.entry.mark_set("insert", "dictation")
        self.entry.see("insert")
        self.entry.edit_separator()
        self.changed()

    def wheel(self, event):
        if event.delta:
            step = (
                -int(event.delta / 120)
                if abs(event.delta) >= 120
                else (-1 if event.delta > 0 else 1)
            )
            self.entry.yview_scroll(step, "units")
        return "break"

    def scroll_linux(self, step):
        self.entry.yview_scroll(step, "units")
        return "break"

    def draw(self, event=None):
        self.delete("art")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 30 or h < 25:
            return
        glass(self, (4, 4, w-5, h-5), "input", 12)
        self.coords(self.text_id, 16, 14)
        self.itemconfigure(
            self.text_id, width=max(20, w-94), height=max(20, h-28),
        )
        show = self.focused or bool(self.get()) or self.voice_state != "idle"
        self.itemconfigure(
            self.text_id, state="normal" if show else "hidden",
        )
        self.coords(self.mic_id, w-74, 9)
        self.coords(self.scroll_id, w-28, 7)
        self.itemconfigure(
            self.scroll_id, width=22, height=max(20, h-14),
        )
        if not show:
            self.create_text(
                16, 27, text=self.placeholder, fill=MUTED, anchor="w",
                width=max(20, w-100), font=("Segoe UI", -17),
                tags=("art", "placeholder"),
            )
        for item in (self.text_id, self.mic_id, self.scroll_id):
            self.tag_raise(item)
        if self.max_lines and self.pending is None:
            self.pending = self.after_idle(self.resize_lines)
        self.schedule()

    def resize_lines(self):
        self.pending = None
        lines = self.entry.count("1.0", "end-1c", "displaylines")
        count = min(
            self.max_lines, max(1, (lines[0] if lines else 0)+1),
        )
        line_height = tkfont.Font(
            font=self.entry.cget("font")
        ).metrics("linespace")
        height = max(self.minimum_height, 28 + count*line_height)
        if int(self.cget("height")) != height:
            self.configure(height=height)

    def set_shimmer(self, enabled):
        self.animation_allowed = bool(enabled)
        self.schedule()

    def schedule(self):
        running = (
            self.animate and self.animation_allowed and not self.focused
            and not self.get() and self.voice_state == "idle"
            and self.winfo_viewable()
        )
        if not running:
            if self.timer is not None:
                self.after_cancel(self.timer)
                self.timer = None
            self.delete("shimmer")
        elif self.timer is None:
            self.timer = self.after(50, self.tick)

    def tick(self):
        self.timer = None
        self.delete("shimmer")
        if (
            self.animate and self.animation_allowed and not self.focused
            and not self.get() and self.voice_state == "idle"
            and self.winfo_viewable()
        ):
            w, h = self.winfo_width(), self.winfo_height()
            self.phase = (self.phase + 0.012) % 1
            _place_image(
                self, _beam_image(w, h, (self.phase*1.4-0.2)*w),
                0, 0, "shimmer",
            )
            self.tag_raise("placeholder")
            self.tag_raise(self.mic_id)
            self.tag_raise(self.scroll_id)
            self.schedule()

    def cleanup(self, event):
        if event.widget != self:
            return
        for timer in (self.timer, self.pending):
            if timer is not None:
                self.after_cancel(timer)
        if self.trace is not None:
            self.variable.trace_remove("write", self.trace)


# КОНЕЦ ФАЙЛА input_widgets.py