"""Локальное хранение напоминаний и безопасное обновление таблицы."""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path


class ReminderDatabase:
    STATUSES = ("Ожидает", "Готово", "Просрочено", "Отменено")

    def __init__(self, db_path=None):
        if db_path is None:
            db_path = Path(__file__).resolve().with_name("reminders.db")
        self.backup_path = None
        self.connection = sqlite3.connect(db_path)
        self.connection.row_factory = sqlite3.Row
        try:
            self.initdatabase()
        except Exception:
            self.connection.close()
            raise

    def initdatabase(self):
        """Создать таблицу или дополнить поля в существующей базе."""
        new_columns = {
            "urgent": "INTEGER NOT NULL DEFAULT 0 CHECK (urgent IN (0, 1))",
            "repeat_daily": "INTEGER NOT NULL DEFAULT 0 CHECK (repeat_daily IN (0, 1))",
            "notified_due_time": "TEXT",
        }
        columns = {
            row["name"] for row in self.connection.execute(
                "PRAGMA table_info(reminders)"
            )
        }
        if columns and new_columns.keys() - columns:
            self._backup_before_update()

        with self.connection:
            self.connection.execute("BEGIN IMMEDIATE")
            self.connection.execute("""
                CREATE TABLE IF NOT EXISTS reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL CHECK (length(trim(title)) > 0),
                    description TEXT NOT NULL DEFAULT '',
                    due_time TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'Ожидает'
                        CHECK (status IN (
                            'Ожидает', 'Готово', 'Просрочено', 'Отменено'
                        )),
                    important INTEGER NOT NULL DEFAULT 0
                        CHECK (important IN (0, 1)),
                    urgent INTEGER NOT NULL DEFAULT 0
                        CHECK (urgent IN (0, 1)),
                    repeat_daily INTEGER NOT NULL DEFAULT 0
                        CHECK (repeat_daily IN (0, 1)),
                    notified_due_time TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            columns = {row["name"] for row in self.connection.execute("PRAGMA table_info(reminders)")}
            for name, definition in new_columns.items():
                if name not in columns:
                    self.connection.execute(f"ALTER TABLE reminders ADD COLUMN {name} {definition}")

    def _backup_before_update(self):
        """Скопировать файловую базу средствами SQLite до изменения таблицы."""
        filename = self.connection.execute("PRAGMA database_list").fetchone()[2]
        if not filename:
            return  # База :memory: не хранится на диске.
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        destination = Path(filename).with_name(
            Path(filename).name + "-backup-" + stamp
        )
        backup = sqlite3.connect(destination)
        try:
            self.connection.backup(backup)
        finally:
            backup.close()
        self.backup_path = destination

    @staticmethod
    def _check_id(reminder_id):
        if type(reminder_id) is not int or reminder_id <= 0:
            raise ValueError("Номер напоминания должен быть целым числом больше нуля.")

    @classmethod
    def _check_status(cls, status):
        if status not in cls.STATUSES:
            raise ValueError("Неизвестный статус напоминания.")

    @staticmethod
    def _parse_time(value):
        try:
            return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S")
        except (ValueError, TypeError):
            raise ValueError(
                "Укажи дату и время в формате 2026-11-16T10:00:00."
            ) from None

    @classmethod
    def _prepare_fields(cls, title, due_time, description, important, urgent, repeat_daily):
        if not isinstance(title, str) or not title.strip():
            raise ValueError("Укажи заголовок напоминания.")
        if not isinstance(description, str):
            raise ValueError("Описание должно быть текстом.")
        if not isinstance(important, bool) or not isinstance(urgent, bool):
            raise ValueError("Важность и срочность должны быть True или False.")
        if not isinstance(repeat_daily, bool):
            raise ValueError("Выбери, нужно ли повторять напоминание ежедневно.")
        parsed = cls._parse_time(due_time)
        return (title.strip(), description.strip(),
                parsed.isoformat(timespec="seconds"), int(important), int(urgent), int(repeat_daily))

    def add_reminder(self, title, due_time, description="", important=False, urgent=False,
                     repeat_daily=False):
        """Добавить напоминание и вернуть его номер."""
        fields = self._prepare_fields(title, due_time, description, important, urgent, repeat_daily)
        with self.connection:
            cursor = self.connection.execute(
                "INSERT INTO reminders "
                "(title, description, due_time, important, urgent, repeat_daily) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                fields,
            )
        return cursor.lastrowid

    def update_reminder(self, reminder_id, title, due_time,
                        description="", important=False, urgent=False, repeat_daily=None,
                        *, expected_due_time=None):
        """Сохранить поля задачи, оставив её номер и статус прежними."""
        self._check_id(reminder_id)
        title, description, due, important, urgent, repeat = self._prepare_fields(
            title, due_time, description, important, urgent,
            False if repeat_daily is None else repeat_daily,
        )
        with self.connection:
            cursor = self.connection.execute(
                """
                UPDATE reminders
                SET title = :title, description = :description, due_time = :due,
                    important = :important, urgent = :urgent,
                    repeat_daily = COALESCE(:repeat, repeat_daily),
                    notified_due_time = CASE
                        WHEN due_time = :due AND repeat_daily = COALESCE(:repeat, repeat_daily)
                        THEN notified_due_time
                    END
                WHERE id = :id AND (:expected_due IS NULL OR due_time = :expected_due)
                """,
                {"title": title, "description": description, "due": due,
                 "important": important, "urgent": urgent,
                 "repeat": None if repeat_daily is None else repeat,
                 "id": reminder_id, "expected_due": expected_due_time},
            )
        return cursor.rowcount == 1

    def get_all_reminders(self, status=None):
        """Получить все напоминания или записи с выбранным статусом."""
        if status is None:
            cursor = self.connection.execute(
                "SELECT * FROM reminders ORDER BY due_time, id"
            )
        else:
            self._check_status(status)
            cursor = self.connection.execute(
                "SELECT * FROM reminders WHERE status = ? ORDER BY due_time, id",
                (status,),
            )
        return cursor.fetchall()

    def get_reminder_by_id(self, reminder_id):
        """Найти напоминание по номеру или вернуть None."""
        self._check_id(reminder_id)
        return self.connection.execute(
            "SELECT * FROM reminders WHERE id = ?", (reminder_id,),
        ).fetchone()

    def update_status(self, reminder_id, status):
        """Изменить статус. Вернуть False, если запись не найдена."""
        self._check_id(reminder_id)
        self._check_status(status)
        with self.connection:
            cursor = self.connection.execute(
                "UPDATE reminders SET status = ? WHERE id = ?", (status, reminder_id),
            )
        return cursor.rowcount == 1

    def delete_reminder(self, reminder_id):
        """Удалить напоминание по номеру."""
        self._check_id(reminder_id)
        with self.connection:
            cursor = self.connection.execute(
                "DELETE FROM reminders WHERE id = ?", (reminder_id,),
            )
        return cursor.rowcount == 1

    def get_reminders_count(self):
        """Получить общее количество напоминаний."""
        return self.connection.execute("SELECT COUNT(*) FROM reminders").fetchone()[0]

    def get_due_reminders(self, *, only_unnotified=False, now=None):
        """Получить ожидающие напоминания, время которых наступило."""
        current = (now or datetime.now()).isoformat(timespec="seconds")
        return self.connection.execute(
            "SELECT * FROM reminders WHERE status = ? AND due_time <= ? "
            "AND (NOT ? OR notified_due_time IS NOT due_time) "
            "ORDER BY due_time, id", ("Ожидает", current, only_unnotified),
        ).fetchall()

    def record_notification(self, row, now):
        """Отметить показ или перенести ежедневное напоминание на ближайший день."""
        due_time = row["due_time"]
        current = now.isoformat(timespec="seconds")
        if due_time > current:
            return False
        next_due = due_time
        if row["repeat_daily"]:
            due = self._parse_time(due_time)
            next_run = datetime.combine(now.date(), due.time())
            if next_run <= now:
                next_run += timedelta(days=1)
            next_due = next_run.isoformat(timespec="seconds")
        with self.connection:
            cursor = self.connection.execute(
                "UPDATE reminders SET notified_due_time = ?, due_time = ? "
                "WHERE id = ? AND due_time = ? AND repeat_daily = ? AND status = ? "
                "AND notified_due_time IS NOT due_time",
                (due_time, next_due, row["id"], due_time, row["repeat_daily"], "Ожидает"),
            )
        return cursor.rowcount == 1

    def mark_overdue(self, *, only_notified=False):
        """Пометить ожидающие задачи, просроченные более чем на минуту."""
        cutoff = (datetime.now() - timedelta(minutes=1)).isoformat(timespec="seconds")
        with self.connection:
            cursor = self.connection.execute(
                "UPDATE reminders SET status = ? WHERE status = ? AND due_time < ? "
                "AND (NOT ? OR (repeat_daily = 0 AND notified_due_time = due_time))",
                ("Просрочено", "Ожидает", cutoff, only_notified),
            )
        return cursor.rowcount

    def sort_by_due_time(self):
        """Получить все напоминания от раннего времени к позднему."""
        return self.get_all_reminders()

    def reschedule_reminder(self, reminder_id, new_due_time):
        """Назначить новое будущее время активному напоминанию."""
        self._check_id(reminder_id)
        parsed = self._parse_time(new_due_time)
        if parsed <= datetime.now():
            raise ValueError("Новое время напоминания должно быть в будущем.")
        with self.connection:
            cursor = self.connection.execute(
                "UPDATE reminders SET due_time = ?, status = ?, notified_due_time = NULL "
                "WHERE id = ? AND status IN (?, ?)",
                (parsed.isoformat(timespec="seconds"), "Ожидает", reminder_id,
                 "Ожидает", "Просрочено"),
            )
        return cursor.rowcount == 1

    def close(self):
        """Закрыть соединение с базой."""
        self.connection.close()


if __name__ == "__main__":
    database = ReminderDatabase()
    try:
        print("База reminders.db и таблица reminders готовы.")
        if database.backup_path:
            print("Резервная копия:", database.backup_path)
    finally:
        database.close()
