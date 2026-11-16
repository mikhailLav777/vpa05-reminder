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
        """Создать таблицу; добавить срочность в старую базу без потери записей."""
        columns = {
            row["name"] for row in self.connection.execute(
                "PRAGMA table_info(reminders)"
            )
        }
        needs_update = bool(columns) and "urgent" not in columns
        if needs_update:
            self._backup_before_update()

        with self.connection:
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
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            if needs_update:
                self.connection.execute(
                    "ALTER TABLE reminders ADD COLUMN urgent "
                    "INTEGER NOT NULL DEFAULT 0 CHECK (urgent IN (0, 1))"
                )

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
    def _prepare_fields(cls, title, due_time, description, important, urgent):
        if not isinstance(title, str) or not title.strip():
            raise ValueError("Укажи заголовок напоминания.")
        if not isinstance(description, str):
            raise ValueError("Описание должно быть текстом.")
        if not isinstance(important, bool) or not isinstance(urgent, bool):
            raise ValueError("Важность и срочность должны быть True или False.")
        parsed = cls._parse_time(due_time)
        return (title.strip(), description.strip(),
                parsed.isoformat(timespec="seconds"), int(important), int(urgent))

    def add_reminder(self, title, due_time, description="", important=False, urgent=False):
        """Добавить напоминание и вернуть его номер."""
        fields = self._prepare_fields(title, due_time, description, important, urgent)
        with self.connection:
            cursor = self.connection.execute(
                "INSERT INTO reminders "
                "(title, description, due_time, important, urgent) VALUES (?, ?, ?, ?, ?)",
                fields,
            )
        return cursor.lastrowid

    def update_reminder(self, reminder_id, title, due_time,
                        description="", important=False, urgent=False):
        """Сохранить поля задачи, оставив её номер и статус прежними."""
        self._check_id(reminder_id)
        fields = self._prepare_fields(title, due_time, description, important, urgent)
        with self.connection:
            cursor = self.connection.execute(
                "UPDATE reminders SET title = ?, description = ?, due_time = ?, "
                "important = ?, urgent = ? WHERE id = ?",
                (*fields, reminder_id),
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

    def get_due_reminders(self):
        """Получить ожидающие напоминания, время которых наступило."""
        current = datetime.now().isoformat(timespec="seconds")
        return self.connection.execute(
            "SELECT * FROM reminders WHERE status = ? AND due_time <= ? "
            "ORDER BY due_time, id", ("Ожидает", current),
        ).fetchall()

    def mark_overdue(self):
        """Пометить ожидающие задачи, просроченные более чем на минуту."""
        cutoff = (datetime.now() - timedelta(minutes=1)).isoformat(timespec="seconds")
        with self.connection:
            cursor = self.connection.execute(
                "UPDATE reminders SET status = ? WHERE status = ? AND due_time < ?",
                ("Просрочено", "Ожидает", cutoff),
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
                "UPDATE reminders SET due_time = ?, status = ? "
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