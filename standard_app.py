"""Главное окно с гибкой раскладкой Tkinter и рабочей базой задач."""

import sqlite3
import tkinter as tk
from datetime import datetime
from tkinter import font as tkfont, messagebox, ttk

from gui import BG, CYAN, MUTED, PANEL, STYLES, WHITE, blend, filter_demo_tasks
from input_widgets import edit_menu
from live_app import LiveApp, StoredTask, priority_index


SURFACE = "#462266"
TEXT_FIELD = "#311344"
SECTION_ALL = "Все задачи"
PRIORITY_LABELS = ("★ Важная и срочн.", "☆ Важная", "◷ Срочная", "Обычная")
STATUS_TONES = {
    "Ожидает": "blue",
    "Просрочено": "red",
    "Готово": "green",
    "Отменено": "violet",
}


class StandardVoiceField(ttk.Frame):
    """Обычное поле Tk и кнопка, совместимые с существующей диктовкой."""

    def __init__(self, parent, app, variable, font, height=1, animate=False):
        super().__init__(parent, style="Reminder.TFrame")
        self.columnconfigure(0, weight=1)
        self.variable = variable
        self.syncing = False
        self.entry = tk.Text(self, height=height, width=1, wrap="word", undo=True,
                             font=font, background=TEXT_FIELD, foreground=WHITE,
                             insertbackground=WHITE, selectbackground="#624A89",
                             relief="flat", highlightthickness=1, highlightcolor=CYAN,
                             highlightbackground=SURFACE, padx=8, pady=6)
        self.entry.grid(row=0, column=0, sticky="ew")
        self.mic = ttk.Button(self, text="Диктовать", style="cyan.Reminder.TButton",
                              command=lambda: app.voice.toggle(self))
        self.mic.grid(row=0, column=1, sticky="nsew", padx=(7, 0))
        edit_menu(self.entry)
        self.entry.bind("<<Modified>>", self.changed)
        self.trace = variable.trace_add("write", self.from_variable)
        self.bind("<Destroy>", self.cleanup, add="+")

        # Одна короткая полоска движется поверх пустого поля без создания картинок.
        self.beam = tk.Frame(self.entry, width=3, background="#397B86") if animate else None
        self.animation_allowed = False
        self.timer = None
        self.phase = 0
        if animate:
            self.entry.bind("<FocusIn>", self.update_shimmer, add="+")
            self.entry.bind("<FocusOut>", self.update_shimmer, add="+")
            self.bind("<Map>", self.update_shimmer, add="+")
            self.bind("<Unmap>", self.update_shimmer, add="+")
        self.from_variable()

    def get(self):
        return self.entry.get("1.0", "end-1c")

    def activate(self):
        self.entry.focus_set()

    def set_voice_state(self, state):
        label = {"idle": "Диктовать", "preparing": "Остановить",
                 "recording": "Остановить", "processing": "Распознаю…"}[state]
        tone = {"idle": "cyan", "preparing": "red", "recording": "red", "processing": "gold"}[state]
        self.mic.configure(text=label, style=f"{tone}.Reminder.TButton")

    def insert_voice(self, text):
        self.entry.edit_separator()
        position = self.entry.index("dictation")
        before = self.entry.get(f"{position}-1c", position)
        after = self.entry.get(position, f"{position}+1c")
        prefix = " " if before and not before.isspace() else ""
        suffix = " " if after and not after.isspace() else ""
        self.entry.insert(position, prefix + text + suffix)
        self.entry.mark_set("insert", "dictation")
        self.entry.see("insert")
        self.entry.edit_separator()
        self.changed()

    def changed(self, event=None):
        if not self.entry.edit_modified():
            return
        self.entry.edit_modified(False)
        if not self.syncing and self.variable.get() != self.get():
            self.variable.set(self.get())
        self.update_shimmer()

    def from_variable(self, *_):
        text = self.variable.get()
        if self.get() == text:
            return
        self.syncing = True
        try:
            self.entry.delete("1.0", "end")
            self.entry.insert("1.0", text)
            self.entry.edit_modified(False)
        finally:
            self.syncing = False
        self.update_shimmer()

    def set_shimmer(self, enabled):
        self.animation_allowed = enabled
        self.update_shimmer()

    def update_shimmer(self, event=None):
        if self.beam is None:
            return
        active = (self.animation_allowed and self.winfo_viewable() and not self.get()
                  and self.focus_get() is not self.entry)
        if active:
            if self.timer is None:
                self.timer = self.after(55, self.move_beam)
        else:
            self.beam.place_forget()
            if self.timer is not None:
                self.after_cancel(self.timer)
                self.timer = None

    def move_beam(self):
        self.timer = None
        self.update_shimmer()
        if self.timer is not None:
            self.phase = (self.phase + 2) % 100
            self.beam.place(relx=self.phase / 100, y=2, relheight=1, height=-4)

    def cleanup(self, event):
        if event.widget is self:
            self.variable.trace_remove("write", self.trace)
            if self.timer is not None:
                self.after_cancel(self.timer)


class StandardApp(LiveApp):
    """Существующая логика задач и диалогов с новым главным окном."""

    def __init__(self, db_path=None):
        self.listed_tasks = {}
        super().__init__(db_path)
        self.geometry("1040x700")
        self.minsize(760, 520)
        # Прокрутку уже обрабатывают стандартные Text и Treeview.
        for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.unbind(sequence)

    def _build_header(self):
        self.zoom = 100
        self.font_body = tkfont.Font(self, family="Segoe UI", size=-16)
        self.font_title = tkfont.Font(self, family="Segoe UI", size=-27, weight="bold")
        self.font_controls = tkfont.Font(self, family="Segoe UI", size=-14)
        self.style = ttk.Style(self)
        self.configure_styles()
        header = ttk.Frame(self, style="Reminder.TFrame", padding=(16, 12))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="Мои напоминания", style="Title.Reminder.TLabel").grid(
            row=0, column=0, sticky="w")
        self.clock_label = ttk.Label(header, style="Reminder.TLabel")
        self.clock_label.grid(row=0, column=1, sticky="e", padx=(8, 0))

    def configure_styles(self):
        self.style.theme_use("clam")
        self.style.configure("Reminder.TFrame", background=BG)
        self.style.configure("Sidebar.TFrame", background=PANEL)
        self.style.configure("Reminder.TLabel", background=BG, foreground=WHITE,
                             font=self.font_body)
        self.style.configure("Title.Reminder.TLabel", font=self.font_title)
        self.style.configure("Quiet.Reminder.TLabel", foreground=MUTED, font=self.font_controls)
        self.style.configure("Sidebar.TLabel", background=PANEL, foreground=WHITE,
                             font=self.font_controls)
        self.style.configure("Reminder.TButton", background=SURFACE, foreground=WHITE, font=self.font_body)
        self.style.map("Reminder.TButton", background=[("active", "#633187")],
                       foreground=[("disabled", "#BCA8CC")])
        self.style.configure("Reminder.TMenubutton", background=SURFACE, foreground=WHITE,
                             font=self.font_body, padding=(8, 5))
        self.style.map("Reminder.TMenubutton", background=[("active", "#633187")])
        self.style.configure("Zoom.Reminder.TButton", font=self.font_controls, padding=(6, 5))
        for tone in ("cyan", "teal", "blue", "red", "green", "gold"):
            top, bottom, edge = STYLES[tone]
            style_name = f"{tone}.Reminder.TButton"
            background = bottom if tone == "cyan" else blend(bottom, top, .52)
            hover = top if tone == "cyan" else blend(bottom, top, .72)
            self.style.configure(style_name, background=background,
                                 foreground="#162934" if tone == "cyan" else WHITE,
                                 bordercolor=edge)
            self.style.map(style_name, background=[("disabled", SURFACE), ("active", hover)],
                           foreground=[("disabled", MUTED)],
                           bordercolor=[("disabled", SURFACE), ("focus", edge)])
        self.style.configure("Reminder.TRadiobutton", background=PANEL, foreground=WHITE,
                             indicatorbackground=SURFACE, font=self.font_body)
        for tone in ("teal", *STATUS_TONES.values()):
            top, bottom, edge = STYLES[tone]
            style_name = f"{tone}.Reminder.TRadiobutton"
            self.style.configure(style_name, background=blend(bottom, top, .35),
                                 indicatorbackground=bottom, indicatorforeground=edge)
            self.style.map(style_name, background=[("selected", blend(bottom, top, .71)),
                                                    ("active", blend(bottom, top, .54))],
                           indicatorforeground=[("selected", WHITE)])
        self.style.configure("Reminder.Treeview", font=self.font_body, background=PANEL,
                             fieldbackground=PANEL, foreground=WHITE, borderwidth=0)
        self.style.configure("Reminder.Treeview.Heading", font=self.font_body,
                             background=SURFACE, foreground=WHITE)
        self.style.map("Reminder.Treeview", background=[("selected", "#5D4287")],
                       foreground=[("selected", WHITE)])

    def _update_clock(self):
        self.clock_label.configure(text=datetime.now().strftime("%d.%m.%Y · %H:%M:%S"))
        self.after(1000, self._update_clock)

    def _build_body(self):
        body = ttk.Frame(self, style="Reminder.TFrame", padding=(12, 0, 12, 9))
        body.grid(row=1, column=0, sticky="nsew")
        body.rowconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)
        self._build_sidebar(body)
        self._build_content(body)
        self.voice_status_label = ttk.Label(self, text="Задачи сохраняются в базе SQLite",
                                            style="Quiet.Reminder.TLabel")
        self.voice_status_label.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 8))
        self.apply_zoom(100)

    def _build_sidebar(self, body):
        sidebar = ttk.Frame(body, style="Sidebar.TFrame", padding=12)
        sidebar.grid(row=0, column=0, sticky="ns")
        sidebar.columnconfigure(0, weight=1)
        self.status_choice = tk.StringVar(self, SECTION_ALL)
        sections = {SECTION_ALL: "teal", **STATUS_TONES}
        sidebar.rowconfigure(len(sections), weight=1)
        for row, (status, tone) in enumerate(sections.items()):
            ttk.Radiobutton(sidebar, text=status, value=status, variable=self.status_choice,
                            style=f"{tone}.Reminder.TRadiobutton", command=self.change_filter).grid(
                                row=row, column=0, sticky="ew", pady=2)
        zoom = ttk.Frame(sidebar, style="Sidebar.TFrame")
        zoom.grid(row=6, column=0, pady=(8, 4))
        ttk.Label(zoom, text="Масштаб", style="Sidebar.TLabel").grid(row=0, columnspan=3, pady=(0, 4))
        self.zoom_out = ttk.Button(zoom, text="−", width=3, style="Zoom.Reminder.TButton",
                                   command=lambda: self.apply_zoom(self.zoom-5))
        self.zoom_out.grid(row=1, column=0)
        self.zoom_text = tk.StringVar(self)
        ttk.Label(zoom, textvariable=self.zoom_text, width=5, anchor="center",
                  style="Sidebar.TLabel").grid(row=1, column=1)
        self.zoom_in = ttk.Button(zoom, text="+", width=3, style="Zoom.Reminder.TButton",
                                  command=lambda: self.apply_zoom(self.zoom+5))
        self.zoom_in.grid(row=1, column=2)
        ttk.Button(zoom, text="Сбросить", style="Zoom.Reminder.TButton",
                   command=lambda: self.apply_zoom(100)).grid(
                       row=2, column=0, columnspan=3, sticky="ew", pady=(4, 0))
        self.action(sidebar, "Настройки", lambda: self.stage_message("Настройки")).grid(
            row=7, column=0, sticky="ew", pady=(5, 0))

    def action(self, parent, text, command, tone="teal"):
        style = f"{tone}.Reminder.TButton" if tone else "Reminder.TButton"
        return ttk.Button(parent, text=text, command=command, style=style)

    def _build_content(self, body):
        content = ttk.Frame(body, style="Reminder.TFrame", padding=(12, 0, 0, 0))
        content.grid(row=0, column=1, sticky="nsew")
        content.columnconfigure(0, weight=1)
        content.rowconfigure(4, weight=1)

        toolbar = ttk.Frame(content, style="Reminder.TFrame")
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        toolbar.columnconfigure(0, weight=1)
        self.section_heading = ttk.Label(toolbar, text=SECTION_ALL, style="Reminder.TLabel")
        self.section_heading.grid(row=0, column=0, sticky="w")
        self.action(toolbar, "План на неделю", lambda: self.stage_message("План на неделю")).grid(
            row=0, column=1, padx=(6, 0))

        search = ttk.Frame(content, style="Reminder.TFrame")
        search.grid(row=1, column=0, sticky="ew", pady=(0, 6))
        search.columnconfigure(1, weight=1)
        ttk.Label(search, text="Поиск", style="Reminder.TLabel").grid(row=0, column=0, padx=(0, 8))
        self.search_entry = StandardVoiceField(search, self, self.search_text, self.font_body)
        self.search_entry.grid(row=0, column=1, sticky="ew")

        draft = ttk.Frame(content, style="Reminder.TFrame")
        draft.grid(row=2, column=0, sticky="ew", pady=(0, 6))
        draft.columnconfigure(1, weight=1)
        ttk.Label(draft, text="Задача", style="Reminder.TLabel").grid(row=0, column=0, padx=(0, 8))
        self.title_entry = StandardVoiceField(draft, self, self.new_title, self.font_body, height=2, animate=True)
        self.title_entry.grid(row=0, column=1, sticky="ew")

        create = ttk.Frame(content, style="Reminder.TFrame")
        create.grid(row=3, column=0, sticky="ew", pady=(0, 6))
        self.action(create, "Добавить задачу", self.open_editor, tone="cyan").pack(side="left")
        templates = tk.Menu(create, tearoff=False)
        for text in ("Проверить остатки", "Связаться с поставщиком"):
            templates.add_command(label=text, command=lambda value=text: self.open_editor(title=value))
        ttk.Menubutton(create, text="Шаблоны", menu=templates, style="Reminder.TMenubutton").pack(
            side="left", padx=8)

        table = ttk.Frame(content, style="Reminder.TFrame")
        table.grid(row=4, column=0, sticky="nsew")
        table.columnconfigure(0, weight=1)
        table.rowconfigure(0, weight=1)
        columns = {"title": "Задача", "due": "Когда", "status": "Статус", "priority": "Приоритет"}
        self.table = ttk.Treeview(table, columns=tuple(columns), show="headings",
                                  selectmode="browse", style="Reminder.Treeview")
        for key, title in columns.items():
            self.table.heading(key, text=title)
            self.table.column(key, stretch=key == "title", minwidth=78)
        for status, tone in STATUS_TONES.items():
            _, background, text_color = STYLES[tone]
            self.table.tag_configure(status, background=background, foreground=text_color)
        self.table.grid(row=0, column=0, sticky="nsew")
        scroll_y = ttk.Scrollbar(table, orient="vertical", command=self.table.yview)
        scroll_y.grid(row=0, column=1, sticky="ns")
        scroll_x = ttk.Scrollbar(table, orient="horizontal", command=self.table.xview)
        scroll_x.grid(row=1, column=0, sticky="ew")
        self.table.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        self.table.bind("<<TreeviewSelect>>", self.update_actions)
        self.table.bind("<Double-1>", self.open_clicked)
        self.table.bind("<Return>", lambda event: self.open_selected())

        actions = ttk.Frame(content, style="Reminder.TFrame")
        actions.grid(row=5, column=0, sticky="ew", pady=(6, 0))
        self.details = self.action(actions, "Подробности", self.open_selected)
        self.details.pack(side="left")
        self.complete = self.action(actions, "Готово", self.toggle_selected, tone="green")
        self.complete.pack(side="left", padx=6)

        footer = ttk.Frame(content, style="Reminder.TFrame")
        footer.grid(row=6, column=0, sticky="ew", pady=(6, 0))
        footer.columnconfigure(0, weight=1)
        self.result_label = ttk.Label(footer, style="Quiet.Reminder.TLabel")
        self.result_label.grid(row=0, column=0, sticky="w")
        self.action(footer, "Пример уведомления", lambda: self.stage_message("Пример уведомления"),
                    tone=None).grid(row=0, column=1, padx=(6, 0))
        self.update_actions()

    def apply_zoom(self, percent):
        self.zoom = min(125, max(75, percent))
        self.zoom_text.set(f"{self.zoom}%")
        self.font_body.configure(size=-round(16*self.zoom/100))
        self.font_title.configure(size=-round(27*self.zoom/100))
        padding = (8, round(5*self.zoom/100))
        for style in ("Reminder.TButton", "Reminder.TRadiobutton"):
            self.style.configure(style, padding=padding)
        self.style.configure("Reminder.Treeview", rowheight=round(36*self.zoom/100))
        widths = {
            "due": self.font_body.measure("00.00.0000, 00:00") + 16,
            "status": max(map(self.font_body.measure, STATUS_TONES)) + 16,
            "priority": max(map(self.font_body.measure, PRIORITY_LABELS)) + 16,
        }
        for key, width in widths.items():
            self.table.column(key, width=width, minwidth=width)
        self.zoom_out.state(["disabled" if self.zoom == 75 else "!disabled"])
        self.zoom_in.state(["disabled" if self.zoom == 125 else "!disabled"])

    def change_filter(self):
        status = self.status_choice.get()
        self.select_status(None if status == SECTION_ALL else status)

    def refresh_tasks(self):
        try:
            rows = self.db.get_all_reminders()
            tasks = [StoredTask(row) for row in rows]
        except (sqlite3.Error, ValueError) as error:
            messagebox.showerror("Не удалось прочитать базу", str(error), parent=self)
            return
        selected = self.table.selection()
        view = self.table.yview()[0]
        self.demo_tasks = tasks
        self.listed_tasks = {}
        self.table.delete(*self.table.get_children())
        for row, task in zip(rows, tasks):
            if not filter_demo_tasks(((task.card, task.description),), self.active_status, self.search_text.get()):
                continue
            title, due, status = task.card[:3]
            if row["repeat_daily"]:
                title = f"Ежедневно · {title}"
            iid = str(task.reminder_id)
            priority = PRIORITY_LABELS[priority_index(row["important"], row["urgent"])]
            self.table.insert("", "end", iid=iid, values=(title, due, status, priority), tags=(status,))
            self.listed_tasks[iid] = task
        if selected and selected[0] in self.listed_tasks:
            self.table.selection_set(selected[0])
            self.table.focus(selected[0])
        self.table.yview_moveto(view)
        self.section_heading.configure(text=self.active_status or SECTION_ALL)
        count = len(self.listed_tasks)
        self.result_label.configure(text=f"Показано: {count} из {len(rows)}" if count else "Задачи не найдены")
        self.update_actions()

    def selected_task(self):
        selection = self.table.selection()
        return self.listed_tasks.get(selection[0]) if selection else None

    def update_actions(self, event=None):
        task = self.selected_task()
        self.details.state(["!disabled" if task else "disabled"])
        active = task is not None and task.card[2] != "Отменено"
        self.complete.state(["!disabled" if active else "disabled"])
        done = task is not None and task.card[2] == "Готово"
        self.complete.configure(text="Вернуть в работу" if done else "Готово",
                                style="blue.Reminder.TButton" if done else "green.Reminder.TButton")

    def open_selected(self):
        task = self.selected_task()
        if task:
            self.open_editor(task.reminder_id)
        return "break"

    def open_clicked(self, event):
        iid = self.table.identify_row(event.y)
        if iid:
            self.table.selection_set(iid)
            return self.open_selected()

    def toggle_selected(self):
        task = self.selected_task()
        if task:
            self.toggle_completion(task)
