"""Проверка расписания и показ напоминаний в открытом приложении."""

import logging
import sqlite3
import tkinter as tk
from datetime import datetime
from time import monotonic

from gui import BG, CYAN, MUTED, WHITE


LOGGER = logging.getLogger(__name__)


class ReminderPopup(tk.Toplevel):
    def __init__(self, app, title, description, when, on_close):
        super().__init__(app)
        self.withdraw()
        self.on_close = on_close
        self.close_timer = None
        self.title("Мои напоминания")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.configure(bg=BG, padx=22, pady=16)
        # Окно без transient показывается и при свёрнутом главном окне.
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.bind("<Escape>", lambda event: self.close())
        self.label("Пора напомнить", CYAN, 16)
        self.label(title, WHITE, 22)
        self.label(when, MUTED, 15)
        if description.strip():
            body = tk.Text(self, width=48, height=4, wrap="word", bg=BG, fg=WHITE,
                           font=("Segoe UI", -15), borderwidth=0, highlightthickness=0)
            body.insert("1.0", description)
            body.configure(state="disabled")
            body.pack(fill="x", pady=(8, 0))
        self.close_button = tk.Button(self, text="Закрыть", command=self.close,
                                      bg=CYAN, fg=BG, activebackground=WHITE,
                                      activeforeground=BG, padx=16, pady=4)
        self.close_button.pack(anchor="e", pady=(12, 0))

    def label(self, text, color, size):
        tk.Label(self, text=text, bg=BG, fg=color, font=("Segoe UI", -size),
                 wraplength=430, justify="left").pack(anchor="w", pady=2)

    def show(self):
        self.deiconify()
        self.lift()
        self.close_button.focus_set()
        self.close_timer = self.after(30_000, self.close)

    def close(self):
        if self.close_timer is not None:
            self.after_cancel(self.close_timer)
        self.destroy()
        self.on_close()


class NotificationManager:
    def __init__(self, app, database, on_change):
        self.app = app
        self.database = database
        self.on_change = on_change
        self.timer = None
        self.popup = None
        self.next_overdue_check = 0
        self.poll_failed = False

    def start(self):
        if self.timer is None:
            self.timer = self.app.after(1000, self.check)

    def stop(self):
        if self.timer is not None:
            self.app.after_cancel(self.timer)
            self.timer = None
        if self.popup is not None:
            self.popup.close()

    def check(self):
        self.timer = None
        try:
            changed = self.show_next() if self.popup is None else False
            current = monotonic()
            if current >= self.next_overdue_check:
                changed = bool(self.database.mark_overdue(only_notified=True)) or changed
                self.next_overdue_check = current + 5
            if changed:
                self.on_change()
            self.poll_failed = False
        except sqlite3.Error:
            if not self.poll_failed:
                LOGGER.exception("Не удалось проверить расписание напоминаний")
                self.poll_failed = True
        finally:
            self.start()

    def show_next(self):
        now = datetime.now()
        due = self.database.get_due_reminders(only_unnotified=True, now=now)
        if not due:
            return False
        row = due[0]
        when = datetime.fromisoformat(row["due_time"]).strftime("%d.%m.%Y, %H:%M")
        if row["repeat_daily"]:
            when += " · Ежедневно"
        popup = ReminderPopup(self.app, row["title"], row["description"], when, self.clear_popup)
        recorded = False
        try:
            recorded = self.database.record_notification(row, now)
        finally:
            if not recorded:
                popup.destroy()
        if recorded:
            self.popup = popup
            popup.show()
        return bool(recorded and row["repeat_daily"])

    def show_preview(self):
        if self.popup is None:
            self.popup = ReminderPopup(self.app, "Проверка уведомлений",
                                       "Так выглядит напоминание, когда наступает выбранное время.",
                                       datetime.now().strftime("%d.%m.%Y, %H:%M"), self.clear_popup)
            self.popup.show()
        else:
            self.popup.lift()

    def clear_popup(self):
        self.popup = None
