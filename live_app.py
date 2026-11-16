"""Подключение существующего оформления к постоянной базе SQLite."""

import sqlite3
import tkinter as tk
from datetime import datetime, timedelta
from tkinter import messagebox

from database import ReminderDatabase
from demo_completion import CompletionCard
from gui import BG, MUTED, NeonButton, NeonScrollbar, filter_demo_tasks
from input_widgets import ChoiceButton, VoiceField
from voice_input import VoiceInput
from schedule_picker import SchedulePicker
from mockup_navigation import NavigationApp


PRIORITIES = (
    ("★ ◷ Важная и срочная", True, True, "orange", "#9A4A0E"),
    ("☆ Важная, не срочная", True, False, "gold", "#705600"),
    ("◷ Неважная, но срочная", False, True, "blue", "#14528A"),
    ("— Неважная и не срочная", False, False, "gray", "#505266"),
)


def priority_index(important, urgent):
    return next(
        i for i, item in enumerate(PRIORITIES)
        if item[1:3] == (bool(important), bool(urgent))
    )


class StoredTask:
    """Переводит строку базы в данные карточки."""

    def __init__(self, row):
        self.reminder_id = row["id"]
        self.description = row["description"]
        priority = PRIORITIES[
            priority_index(row["important"], row["urgent"])
        ]
        styles = {
            "Ожидает": "blue", "Просрочено": "purple",
            "Готово": "green", "Отменено": "violet",
        }
        due = datetime.fromisoformat(row["due_time"])
        self.card = [
            " ".join(row["title"].split()),
            due.strftime("%d.%m.%Y, %H:%M"),
            row["status"], priority[0],
            styles[row["status"]], priority[3],
        ]


class StoredCard(CompletionCard):
    def __init__(self, parent, app, task):
        super().__init__(parent, app, task)
        self.details.command = lambda: app.open_editor(task.reminder_id)


class ReminderEditor(tk.Toplevel):
    """Форма добавления и подробностей одной задачи."""

    def __init__(self, app, row=None, title=""):
        super().__init__(app)
        self.app, self.row = app, row
        self.title("Подробности задачи" if row else "Новая задача")
        self.configure(bg=BG)
        self.geometry("860x760")
        self.minsize(760, 620)
        self.transient(app)
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.bind("<Escape>", lambda event: self.close())
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        top = tk.Frame(self, bg=BG)
        top.grid(row=0, column=0, sticky="ew", padx=16, pady=10)
        NeonButton(
            top, "Назад на главную", self.close,
            width=235, height=38, font_size=17,
        ).pack(side="left")
        app.label(top, self.title(), 23, True).pack(
            side="left", padx=16,
        )

        area = tk.Frame(self, bg=BG)
        area.grid(row=1, column=0, sticky="nsew", padx=16)
        area.grid_columnconfigure(0, weight=1)
        area.grid_rowconfigure(0, weight=1)

        self.body_canvas = tk.Canvas(
            area, bg=BG, bd=0, highlightthickness=0,
            yscrollincrement=24,
        )
        self.body_canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar = NeonScrollbar(area, self.body_canvas)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.body_canvas.configure(yscrollcommand=scrollbar.set)

        body = tk.Frame(self.body_canvas, bg=BG)
        window = self.body_canvas.create_window(
            0, 0, window=body, anchor="nw",
        )
        self.body_canvas.bind(
            "<Configure>",
            lambda event: self.body_canvas.itemconfigure(
                window, width=event.width,
            ),
        )
        body.bind(
            "<Configure>",
            lambda event: self.body_canvas.configure(
                scrollregion=self.body_canvas.bbox("all"),
            ),
        )
        self.bind("<MouseWheel>", self.scroll_body)
        body.grid_columnconfigure(0, weight=1)

        app.label(body, "Название", 18, True).grid(
            row=0, column=0, sticky="w", padx=4,
        )
        self.name = tk.StringVar(
            self, row["title"] if row else title,
        )
        self.name_field = VoiceField(
            body, app, self.name, "Название задачи", max_lines=3,
        )
        self.name_field.grid(
            row=1, column=0, sticky="ew", pady=(3, 7),
        )
        self.name_entry = self.name_field.entry

        app.label(body, "Описание", 18, True).grid(
            row=2, column=0, sticky="w", padx=4,
        )
        self.description_field = VoiceField(
            body, app, placeholder="Подробности задачи", height=160,
        )
        self.description_field.grid(
            row=3, column=0, sticky="ew", pady=4,
        )
        self.description = self.description_field.entry
        if row:
            self.description.insert("1.0", row["description"])

        self.when = SchedulePicker(
            body, row["due_time"] if row else None,
        )
        self.when.grid(row=4, column=0, sticky="ew", pady=8)

        priorities = tk.Frame(body, bg=BG)
        priorities.grid(row=5, column=0, sticky="ew", pady=4)
        app.label(priorities, "Приоритет задачи", 18, True).grid(
            row=0, column=0, columnspan=2,
            sticky="w", padx=4, pady=(0, 5),
        )
        selected = (
            priority_index(row["important"], row["urgent"])
            if row else 3
        )
        self.priority = tk.IntVar(self, selected)

        for i, (text, _, _, style, _) in enumerate(PRIORITIES):
            priorities.grid_columnconfigure(i % 2, weight=1)
            ChoiceButton(
                priorities, self.priority, i, text, style,
            ).grid(
                row=1+i//2, column=i%2,
                sticky="ew", padx=2, pady=2,
            )

        status = row["status"] if row else "Ожидает"
        app.label(
            body,
            f"Статус: {status}. Сохранение полей не меняет статус.",
            14, color=MUTED,
        ).grid(
            row=6, column=0, sticky="w", padx=4, pady=8,
        )

        footer = tk.Frame(self, bg=BG)
        footer.grid(
            row=2, column=0, sticky="ew", padx=16, pady=(6, 12),
        )
        for column in range(3):
            footer.grid_columnconfigure(column, weight=1)

        self.voice_label = app.label(
            footer,
            "Микрофон: нажми, говори, нажми ещё раз. "
            "Текст появится после остановки.",
            13, color=MUTED,
        )
        self.voice_label.configure(wraplength=760, justify="left")
        self.voice_label.grid(
            row=0, column=0, columnspan=3,
            sticky="ew", pady=(0, 4),
        )

        NeonButton(
            footer,
            "Сохранить изменения" if row else "Добавить задачу",
            self.save, style="cyan", font_size=21, height=46,
        ).grid(
            row=1, column=0, columnspan=3, sticky="ew", pady=3,
        )

        if row:
            if status != "Отменено":
                text = (
                    "Вернуть в работу"
                    if status == "Готово"
                    else "Задача выполнена"
                )
                NeonButton(
                    footer, text, self.complete,
                    style="green", font_size=15,
                ).grid(
                    row=2, column=0, sticky="ew",
                    padx=(0, 3), pady=3,
                )
                NeonButton(
                    footer, "Отменить задачу", self.cancel_task,
                    style="violet", font_size=15,
                ).grid(
                    row=2, column=1, sticky="ew",
                    padx=3, pady=3,
                )

            NeonButton(
                footer, "Удалить", self.delete_task,
                style="red", font_size=16,
            ).grid(
                row=2, column=2, sticky="ew",
                padx=(3, 0), pady=3,
            )

        self.original = self.snapshot()
        self.name_field.activate()

    def scroll_body(self, event):
        if event.delta:
            step = (
                -int(event.delta / 120)
                if abs(event.delta) >= 120
                else (-1 if event.delta > 0 else 1)
            )
            self.body_canvas.yview_scroll(step, "units")
        return "break"

    def snapshot(self):
        return (
            self.name.get(),
            self.description.get("1.0", "end-1c"),
            self.when.choice.signature(),
            self.priority.get(),
        )

    def may_leave(self):
        voice = self.app.voice
        if (
            voice.busy
            and voice.target in (
                self.name_field, self.description_field,
            )
        ):
            if not messagebox.askyesno(
                "Диктовка ещё не завершена",
                "Прервать диктовку без вставки результата?",
                parent=self,
            ):
                return False
            voice.cancel(voice.target)

        return self.snapshot() == self.original or messagebox.askyesno(
            "Несохранённые изменения",
            "Продолжить без сохранения изменений полей?",
            parent=self,
        )

    def close(self, force=False):
        if force or self.may_leave():
            self.app.voice.cancel(self.name_field)
            self.app.voice.cancel(self.description_field)
            self.destroy()
            self.app.editor = None
            self.app.lift()

    def save(self):
        if (
            self.app.voice.busy
            and self.app.voice.target in (
                self.name_field, self.description_field,
            )
        ):
            messagebox.showinfo(
                "Диктовка",
                "Останови микрофон и дождись появления текста "
                "перед сохранением.",
                parent=self,
            )
            return

        def write():
            iso = self.when.choice.resolve()
            _, important, urgent, _, _ = PRIORITIES[
                self.priority.get()
            ]
            args = (
                self.name.get(), iso,
                self.description.get("1.0", "end-1c"),
                important, urgent,
            )
            if self.row:
                return self.app.db.update_reminder(
                    self.row["id"], *args,
                )
            return self.app.db.add_reminder(*args)

        if self.app.change(write, self):
            if not self.row:
                self.app.new_title.set("")
            self.close(force=True)

    def complete(self):
        if (
            self.may_leave()
            and self.app.toggle_completion(StoredTask(self.row), self)
        ):
            self.close(force=True)

    def cancel_task(self):
        if self.may_leave() and self.app.change(
            lambda: self.app.db.update_status(
                self.row["id"], "Отменено",
            ),
            self,
        ):
            self.close(force=True)

    def delete_task(self):
        if messagebox.askyesno(
            "Удалить задачу?",
            f"Удалить «{self.row['title']}» из базы? "
            "Это действие нельзя отменить.",
            parent=self,
        ):
            if self.app.change(
                lambda: self.app.db.delete_reminder(self.row["id"]),
                self,
            ):
                self.close(force=True)


class LiveApp(NavigationApp):
    def __init__(self, db_path=None):
        self.db = ReminderDatabase(db_path)
        self.editor = None
        self.voice = None
        self.previous_statuses = {}
        try:
            super().__init__()
            self.voice = VoiceInput(self, self._voice_status)
            self.title("Мои напоминания")
            self.protocol("WM_DELETE_WINDOW", self.on_closing)
        except Exception:
            self.db.close()
            raise

    def _build_body(self):
        super()._build_body()
        for widget in self.grid_slaves(row=2, column=0):
            self.voice_status_label = widget
            widget.configure(
                text="SQLite: задачи сохраняются · "
                     "диктовка через интернет · уведомления пока макеты",
                wraplength=1000, justify="left",
            )

    def _build_content(self, body):
        super()._build_content(body)

        for field in (self.search_entry, self.title_entry):
            for modes, callback in field.variable.trace_info():
                if "write" in modes and callback.endswith("_changed"):
                    field.variable.trace_remove("write", callback)

        search_parent = self.search_entry.master
        self.search_entry.destroy()
        self.search_entry = VoiceField(
            search_parent, self, self.search_text,
            "Поиск по всем датам", max_lines=3,
        )
        self.search_entry.grid(row=0, column=0, sticky="ew")

        title_parent = self.title_entry.master
        for child in title_parent.winfo_children():
            child.destroy()
        self.title_entry = VoiceField(
            title_parent, self, self.new_title,
            "Что нужно сделать?", max_lines=5, animate=True,
        )
        self.title_entry.grid(
            row=0, column=0, columnspan=2, sticky="ew",
        )

    def _voice_status(self, text):
        self.voice_preview = self.voice.busy
        self.voice_status_label.configure(text=text)
        if self.editor is not None and self.editor.winfo_exists():
            self.editor.voice_label.configure(text=text)
        self._sync_shimmer()

    def button(
        self, parent, text, style="teal",
        icon_name=None, command=None, **kwargs,
    ):
        if command is None:
            if text == "+ Добавить задачу":
                command = self.open_editor
            elif text in (
                "Проверить остатки", "Связаться с поставщиком",
            ):
                command = lambda value=text: self.open_editor(title=value)

        return super().button(
            parent, text, style, icon_name, command, **kwargs,
        )

    def refresh_tasks(self):
        try:
            self.demo_tasks = [
                StoredTask(row) for row in self.db.get_all_reminders()
            ]
        except (sqlite3.Error, ValueError) as error:
            messagebox.showerror(
                "Не удалось прочитать базу", str(error), parent=self,
            )
            return

        visible = [
            task for task in self.demo_tasks
            if filter_demo_tasks(
                ((task.card, task.description),),
                self.active_status,
                self.search_text.get(),
            )
        ]

        for child in self.cards.winfo_children():
            child.destroy()
        for task in visible:
            StoredCard(self.cards, self, task).pack(
                fill="x", pady=(0, 3),
            )

        if not visible:
            self.label(
                self.cards, "Задачи не найдены", 22, True,
            ).pack(anchor="w", padx=20, pady=(28, 6))
            self.label(
                self.cards, "Добавь задачу или измени фильтр и поиск.",
                15, color=MUTED,
            ).pack(anchor="w", padx=20, pady=(0, 20))

        self.section_heading.configure(
            text=self.active_status or "Все задачи",
        )
        self.result_label.configure(
            text=f"Показано: {len(visible)} из {len(self.demo_tasks)}",
        )

        for status, button in self.filter_buttons.items():
            button.selected = status == self.active_status
            button._draw()

        self.cards.update_idletasks()
        self.tasks_canvas.configure(
            scrollregion=self.tasks_canvas.bbox("all"),
        )

    def change(self, action, parent=None):
        try:
            if not action():
                raise ValueError("Задача больше не найдена. Обнови список.")
        except (sqlite3.Error, ValueError) as error:
            messagebox.showerror(
                "Изменения не сохранены", str(error),
                parent=parent or self,
            )
            return False
        self.refresh_tasks()
        return True

    def open_editor(self, reminder_id=None, title=None):
        if self.voice.busy and self.voice.target is self.title_entry:
            messagebox.showinfo(
                "Диктовка",
                "Сначала останови диктовку названия и дождись текста.",
                parent=self,
            )
            return

        if self.editor is not None and self.editor.winfo_exists():
            self.editor.lift()
            self.editor.focus_set()
            return

        row = None
        if reminder_id is not None:
            try:
                row = self.db.get_reminder_by_id(reminder_id)
                if row is None:
                    raise ValueError("Задача больше не найдена.")
            except (sqlite3.Error, ValueError) as error:
                messagebox.showerror(
                    "Не удалось открыть задачу", str(error), parent=self,
                )
                return

        self.editor = ReminderEditor(
            self, row,
            self.new_title.get() if title is None else title,
        )

    def toggle_completion(self, task, parent=None):
        def write():
            row = self.db.get_reminder_by_id(task.reminder_id)
            if row is None:
                return False

            status = row["status"]
            if status == "Отменено":
                raise ValueError(
                    "Задача отменена. Галочка не меняет её статус."
                )

            if status == "Готово":
                overdue = (
                    datetime.fromisoformat(row["due_time"])
                    < datetime.now() - timedelta(minutes=1)
                )
                target = self.previous_statuses.get(
                    row["id"], "Просрочено" if overdue else "Ожидает",
                )
            else:
                self.previous_statuses[row["id"]] = status
                target = "Готово"

            return self.db.update_status(row["id"], target)

        return self.change(write, parent)

    def on_closing(self):
        if self.editor is not None and self.editor.winfo_exists():
            self.editor.close()
            if self.editor is not None:
                return

        if messagebox.askyesno(
            "Выход",
            "Закрыть приложение? Задачи сохранены в базе.",
            parent=self,
        ):
            self.voice.close()
            self.db.close()
            self.destroy()


# КОНЕЦ ФАЙЛА live_app.py