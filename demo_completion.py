"""Выполнение демонстрационных задач. Личная база не используется."""

from tkinter import messagebox

from gui import (
    MUTED,
    WHITE,
    DEMO_TASKS,
    ReminderApp,
    TaskCard,
    filter_demo_tasks,
)


class DemoTask:
    """Данные одной задачи и её статус до отметки выполнения."""

    def __init__(self, card, description):
        self.card = list(card)
        self.description = description

        self.previous_status = (
            "Ожидает" if card[2] == "Готово" else card[2]
        )
        self.previous_style = (
            "blue" if card[2] == "Готово" else card[4]
        )

    def toggle(self):
        """Изменить выполнение, сохраняя отменённые задачи."""
        if self.card[2] == "Отменено":
            return False

        if self.card[2] == "Готово":
            self.card[2] = self.previous_status
            self.card[4] = self.previous_style
        else:
            self.previous_status = self.card[2]
            self.previous_style = self.card[4]
            self.card[2] = "Готово"
            self.card[4] = "green"

        return True


class CompletionCard(TaskCard):
    """Готовая карточка из gui.py с нажимаемой галочкой."""

    def __init__(self, parent, app, task):
        self.task = task
        super().__init__(parent, app, *task.card)

        self.configure(takefocus=task.card[2] != "Отменено")

        self.bind("<Button-1>", self._click)
        self.bind("<Motion>", self._hover)
        self.bind(
            "<Leave>",
            lambda event: self.configure(cursor=""),
        )
        self.bind("<space>", self._keyboard)
        self.bind("<Return>", self._keyboard)
        self.bind("<FocusIn>", self._focus_in)
        self.bind(
            "<FocusOut>",
            lambda event: self.delete("keyboard_focus"),
        )

    def _inside_checkbox(self, event):
        return 12 <= event.x <= 49 and 29 <= event.y <= 69

    def _click(self, event):
        if self._inside_checkbox(event):
            self.app.toggle_completion(self.task)
            return "break"

    def _hover(self, event):
        clickable = (
            self._inside_checkbox(event)
            and self.task.card[2] != "Отменено"
        )
        self.configure(cursor="hand2" if clickable else "")

    def _keyboard(self, event):
        self.app.toggle_completion(self.task)
        return "break"

    def _focus_in(self, event):
        self.delete("keyboard_focus")
        self.create_rectangle(
            13, 31, 48, 66,
            outline=WHITE,
            dash=(2, 2),
            tags="keyboard_focus",
        )


class DemoApp(ReminderApp):
    """Использует готовое окно и изменяет статусы в памяти."""

    def __init__(self):
        self.demo_tasks = [
            DemoTask(card, description)
            for card, description in DEMO_TASKS
        ]
        super().__init__()

    def refresh_tasks(self):
        visible = [
            task
            for task in self.demo_tasks
            if filter_demo_tasks(
                ((task.card, task.description),),
                self.active_status,
                self.search_text.get(),
            )
        ]

        for child in self.cards.winfo_children():
            child.destroy()

        for task in visible:
            CompletionCard(
                self.cards, self, task,
            ).pack(fill="x", pady=(0, 3))

        if not visible:
            self.label(
                self.cards, "Задачи не найдены", 22, True,
            ).pack(
                anchor="w", padx=20, pady=(28, 6),
            )
            self.label(
                self.cards,
                "Измени запрос или выбери другой раздел.",
                15,
                color=MUTED,
            ).pack(
                anchor="w", padx=20, pady=(0, 20),
            )

        self.section_heading.configure(
            text=self.active_status or "Все задачи",
        )
        self.result_label.configure(
            text=(
                f"Показано: {len(visible)} "
                f"из {len(self.demo_tasks)}"
            ),
        )

        for status, button in self.filter_buttons.items():
            button.selected = status == self.active_status
            button._draw()

        self.cards.update_idletasks()
        self.tasks_canvas.configure(
            scrollregion=self.tasks_canvas.bbox("all"),
        )
        self.tasks_canvas.yview_moveto(0)

    def toggle_completion(self, task):
        if not task.toggle():
            messagebox.showinfo(
                "Задача отменена",
                "Эта задача отменена. "
                "Галочка выполнения не меняет её статус.",
                parent=self,
            )
            return

        self.refresh_tasks()
        self.filter_buttons[self.active_status].focus_set()


# КОНЕЦ ФАЙЛА demo_completion.py