"""Выбор дня, времени и интервала без дополнительных библиотек."""

import calendar
import tkinter as tk
from datetime import date, datetime, timedelta
from tkinter import messagebox

from gui import BG, MUTED, WHITE, NeonButton, RoundedEntry
from input_widgets import edit_menu


MONTH_NAMES = (
    "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
)


class ScheduleChoice:
    """Логика выбора времени без графического окна."""

    def __init__(self, original=None, now=None):
        self.original = datetime.fromisoformat(original) if original else None
        self.mode = "fixed" if original else "now"
        self.selected = (
            self.original
            or (now or datetime.now()).replace(microsecond=0)
        )

    def current(self, now=None):
        if self.mode == "now":
            return (now or datetime.now()).replace(microsecond=0)
        return self.selected

    def signature(self):
        if self.mode == "now":
            return ("now",)
        return ("fixed", self.selected)

    def set_now(self):
        self.mode = "now"

    def set_offset(self, minutes, now=None):
        if type(minutes) is not int or not 1 <= minutes <= 525600:
            raise ValueError("Укажи от 1 до 525600 минут.")

        self.selected = (
            (now or datetime.now()).replace(microsecond=0)
            + timedelta(minutes=minutes)
        )
        self.mode = "fixed"

    def set_date(self, chosen, now=None):
        current = self.current(now)
        if chosen != current.date():
            self.selected = current.replace(
                year=chosen.year,
                month=chosen.month,
                day=chosen.day,
                second=0,
            )
            self.mode = "fixed"

    def set_time(self, hour, minute, now=None):
        if not 0 <= hour <= 23 or not 0 <= minute <= 59:
            raise ValueError("Часы: 0–23. Минуты: 0–59.")

        current = self.current(now)
        if (hour, minute) != (current.hour, current.minute):
            self.selected = current.replace(
                hour=hour, minute=minute, second=0,
            )
            self.mode = "fixed"

    def resolve(self, now=None):
        now = now or datetime.now()
        chosen = self.current(now)

        if (
            self.mode != "now"
            and chosen != self.original
            and chosen <= now
        ):
            raise ValueError(
                "Выбранное время уже прошло. "
                "Нажми «Сейчас» или выбери будущее время."
            )

        return chosen.isoformat(timespec="seconds")


def move_month(year, month, offset):
    index = (year-1)*12 + month-1 + offset
    if not 0 <= index < 9999*12:
        return year, month
    return index//12 + 1, index % 12 + 1


def caption(parent, text, size=16, color=WHITE):
    return tk.Label(
        parent, text=text, bg=BG, fg=color,
        font=("Segoe UI", -size), anchor="w", justify="left",
    )


class PickerDialog(tk.Toplevel):
    def __init__(self, parent, title):
        super().__init__(parent)
        self.title(title)
        self.configure(bg=BG, padx=12, pady=10)
        self.resizable(False, False)
        self.transient(parent.winfo_toplevel())
        self.bind("<Escape>", lambda event: self.destroy())
        self.grab_set()

    def button(
        self, parent, text, command,
        width=100, style="teal", size=15,
    ):
        return NeonButton(
            parent, text, command, width=width, height=38,
            style=style, font_size=size,
        )

    def field(self, parent, variable, width):
        field = RoundedEntry(parent, variable, "")
        field.configure(width=width)
        edit_menu(field.entry)

        def popup(event):
            field.activate()
            return field.entry.show_edit_menu(event)

        field.bind("<Button-3>", popup)
        return field


class CalendarDialog(PickerDialog):
    def __init__(self, parent, selected, callback):
        super().__init__(parent, "Выбрать дату")
        self.selected, self.callback = selected, callback
        self.year, self.month = selected.year, selected.month

        top = tk.Frame(self, bg=BG)
        top.pack(fill="x")
        self.button(
            top, "‹", lambda: self.move(-1), 42,
        ).pack(side="left")
        self.heading = caption(top, "", 20)
        self.heading.pack(side="left", expand=True, padx=8)
        self.button(
            top, "›", lambda: self.move(1), 42,
        ).pack(side="right")

        years = tk.Frame(self, bg=BG)
        years.pack(fill="x", pady=5)
        self.button(
            years, "На год назад", lambda: self.move(-12), 160,
        ).pack(side="left")
        self.button(
            years, "На год вперёд", lambda: self.move(12), 160,
        ).pack(side="right")

        self.days = tk.Frame(self, bg=BG)
        self.days.pack()

        bottom = tk.Frame(self, bg=BG)
        bottom.pack(fill="x", pady=(6, 0))
        self.button(
            bottom, "Сегодня",
            lambda: self.choose(date.today()), 150,
        ).pack(side="left")
        self.button(
            bottom, "Отмена", self.destroy, 150, "purple",
        ).pack(side="right")
        self.render()

    def move(self, offset):
        self.year, self.month = move_month(
            self.year, self.month, offset,
        )
        self.render()

    def render(self):
        self.heading.configure(
            text=f"{MONTH_NAMES[self.month-1]} {self.year}",
        )

        for child in self.days.winfo_children():
            child.destroy()

        for col, text in enumerate(
            ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")
        ):
            caption(self.days, text, 14, MUTED).grid(
                row=0, column=col, padx=8, pady=4,
            )

        weeks = calendar.Calendar(
            firstweekday=0
        ).monthdayscalendar(self.year, self.month)
        weeks += [[0]*7 for _ in range(6-len(weeks))]

        for row, week in enumerate(weeks, 1):
            for col, day in enumerate(week):
                if not day:
                    tk.Frame(
                        self.days, bg=BG, width=44, height=38,
                    ).grid(row=row, column=col)
                    continue

                chosen = date(self.year, self.month, day)
                style = (
                    "cyan" if chosen == self.selected
                    else "gold" if chosen == date.today()
                    else "purple"
                )
                self.button(
                    self.days,
                    str(day),
                    lambda value=chosen: self.choose(value),
                    44,
                    style,
                ).grid(row=row, column=col)

    def choose(self, chosen):
        self.callback(chosen)
        self.destroy()


class TimeDialog(PickerDialog):
    def __init__(self, parent, selected, callback):
        super().__init__(parent, "Выбрать время")
        self.callback = callback
        self.hour = tk.StringVar(self, f"{selected.hour:02}")
        self.minute = tk.StringVar(self, f"{selected.minute:02}")

        fields = tk.Frame(self, bg=BG)
        fields.pack(fill="x")

        for col, (label, variable) in enumerate((
            ("Часы: 00–23", self.hour),
            ("Минуты: 00–59", self.minute),
        )):
            caption(fields, label).grid(
                row=0, column=col, sticky="w", padx=4,
            )
            field = self.field(fields, variable, 165)
            field.grid(row=1, column=col, padx=4)

        caption(self, "Часы", 15, MUTED).pack(
            anchor="w", pady=(8, 2),
        )
        hours = tk.Frame(self, bg=BG)
        hours.pack()

        for value in range(24):
            self.button(
                hours, f"{value:02}",
                lambda v=value: self.hour.set(f"{v:02}"),
                56, "purple",
            ).grid(row=value//6, column=value%6)

        caption(
            self,
            "Минуты: выбери или впиши любое число выше",
            13, MUTED,
        ).pack(anchor="w", pady=(8, 2))

        minutes = tk.Frame(self, bg=BG)
        minutes.pack()
        for index, value in enumerate(range(0, 60, 5)):
            self.button(
                minutes, f"{value:02}",
                lambda v=value: self.minute.set(f"{v:02}"),
                56, "purple",
            ).grid(row=index//6, column=index%6)

        bottom = tk.Frame(self, bg=BG)
        bottom.pack(fill="x", pady=(8, 0))
        self.button(
            bottom, "Выбрать", self.apply, 165, "cyan",
        ).pack(side="left")
        self.button(
            bottom, "Отмена", self.destroy, 165, "purple",
        ).pack(side="right")

    def apply(self):
        try:
            hour = int(self.hour.get())
            minute = int(self.minute.get())
            if not 0 <= hour <= 23 or not 0 <= minute <= 59:
                raise ValueError()
        except ValueError:
            messagebox.showerror(
                "Проверь время",
                "Часы: от 0 до 23. Минуты: от 0 до 59.",
                parent=self,
            )
            return

        self.callback(hour, minute)
        self.destroy()


class OffsetDialog(PickerDialog):
    def __init__(self, parent, callback):
        super().__init__(parent, "Другое время от текущего момента")
        self.callback = callback
        caption(self, "Через сколько минут?", 20).pack(anchor="w")
        self.minutes = tk.StringVar(self, "60")
        field = self.field(self, self.minutes, 350)
        field.pack(fill="x", pady=8)

        caption(
            self, "Например: 90 минут — через полтора часа.",
            14, MUTED,
        ).pack(anchor="w")

        bottom = tk.Frame(self, bg=BG)
        bottom.pack(fill="x", pady=(8, 0))
        self.button(
            bottom, "Выбрать", self.apply, 165, "cyan",
        ).pack(side="left")
        self.button(
            bottom, "Отмена", self.destroy, 165, "purple",
        ).pack(side="right")
        field.activate()

    def apply(self):
        try:
            value = int(self.minutes.get())
            if not 1 <= value <= 525600:
                raise ValueError()
        except ValueError:
            messagebox.showerror(
                "Проверь интервал",
                "Укажи от 1 до 525600 минут.",
                parent=self,
            )
            return

        self.callback(value)
        self.destroy()


class SchedulePicker(tk.Frame):
    def __init__(self, parent, original=None):
        super().__init__(parent, bg=BG)
        self.choice = ScheduleChoice(original)
        self.timer = None
        self.dialog = None

        for col in range(4):
            self.grid_columnconfigure(
                col, weight=1, uniform="quick",
            )

        caption(self, "Когда напомнить", 20).grid(
            row=0, column=0, columnspan=4,
            sticky="w", padx=4, pady=4,
        )
        caption(self, "Дата напоминания", 15, MUTED).grid(
            row=1, column=0, columnspan=2, sticky="w", padx=4,
        )
        caption(self, "Время напоминания", 15, MUTED).grid(
            row=1, column=2, columnspan=2, sticky="w", padx=4,
        )

        self.day_button = NeonButton(
            self, "", self.pick_date,
            icon_name="calendar", font_size=18,
        )
        self.day_button.grid(
            row=2, column=0, columnspan=2, sticky="ew", padx=2,
        )
        self.time_button = NeonButton(
            self, "", self.pick_time,
            icon_name="clock", font_size=18,
        )
        self.time_button.grid(
            row=2, column=2, columnspan=2, sticky="ew", padx=2,
        )

        caption(
            self, "Быстрый выбор — от текущего момента:",
            14, MUTED,
        ).grid(
            row=3, column=0, columnspan=4,
            sticky="w", padx=4, pady=(7, 2),
        )

        options = (
            ("Сейчас", self.set_now),
            ("Через 15 минут", lambda: self.offset(15)),
            ("Через 30 минут", lambda: self.offset(30)),
            ("Другое…", self.pick_offset),
        )
        for col, (text, command) in enumerate(options):
            NeonButton(
                self, text, command, style="purple",
                font_size=14, height=36,
            ).grid(
                row=4, column=col, sticky="ew", padx=2,
            )

        self.summary = caption(self, "", 14, MUTED)
        self.summary.configure(wraplength=700)
        self.summary.grid(
            row=5, column=0, columnspan=4,
            sticky="ew", padx=4, pady=5,
        )
        self.bind("<Destroy>", self.cleanup)
        self.tick()

    def refresh(self):
        due = self.choice.current()
        for button, text in (
            (self.day_button, due.strftime("%d.%m.%Y")),
            (self.time_button, due.strftime("%H:%M")),
        ):
            if button.text != text:
                button.text = text
                button._draw()

        if self.choice.mode == "now":
            text = (
                "Выбрано: сейчас — время будет записано "
                "в момент сохранения задачи."
            )
        else:
            verb = (
                "Перенести время на"
                if self.choice.original
                and self.choice.selected != self.choice.original
                else "Выбрано"
            )
            text = (
                f"{verb}: {due:%d.%m.%Y, %H:%M}. "
                "Применится после сохранения."
            )
        self.summary.configure(text=text)

    def tick(self):
        self.refresh()
        self.timer = self.after(1000, self.tick)

    def show(self, dialog_class, *args):
        if self.dialog is not None and self.dialog.winfo_exists():
            self.dialog.lift()
            return
        self.dialog = dialog_class(self, *args)

    def pick_date(self):
        self.show(
            CalendarDialog,
            self.choice.current().date(),
            self.set_date,
        )

    def pick_time(self):
        self.show(
            TimeDialog, self.choice.current(), self.set_time,
        )

    def pick_offset(self):
        self.show(OffsetDialog, self.offset)

    def set_date(self, chosen):
        self.choice.set_date(chosen)
        self.refresh()

    def set_time(self, hour, minute):
        self.choice.set_time(hour, minute)
        self.refresh()

    def offset(self, minutes):
        self.choice.set_offset(minutes)
        self.refresh()

    def set_now(self):
        self.choice.set_now()
        self.refresh()

    def cleanup(self, event):
        if event.widget == self and self.timer is not None:
            self.after_cancel(self.timer)
            self.timer = None


# КОНЕЦ ФАЙЛА schedule_picker.py