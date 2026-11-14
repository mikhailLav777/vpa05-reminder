import sqlite3
from pathlib import Path
from datetime import datetime


class ReminderDatabase:
    """Работа с локальной базой напоминаний."""

    def __init__(self, db_path=None):
        if db_path is None:
            db_path = Path(__file__).resolve().with_name("reminders.db")

        self.connection = sqlite3.connect(db_path)
        self.connection.row_factory = sqlite3.Row

        try:
            self.initdatabase()
        except Exception:
            self.connection.close()
            raise

    def initdatabase(self):
        """Создать таблицу, если её ещё нет."""
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
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)

    def add_reminder(self, title, due_time, description="", important=False):
        """Добавить напоминание и вернуть его номер."""
        if not isinstance(title, str) or not title.strip():
            raise ValueError("Укажи заголовок напоминания.")

        if not isinstance(description, str):
            raise ValueError("Описание должно быть текстом.")

        if not isinstance(important, bool):
            raise ValueError("Важность должна быть True или False.")

        try:
            parsed_time = datetime.strptime(due_time, "%Y-%m-%dT%H:%M:%S")
        except (ValueError, TypeError):
            raise ValueError(
                "Укажи дату и время в формате 2026-11-16T10:00:00."
            ) from None

        with self.connection:
            cursor = self.connection.execute(
                """
                INSERT INTO reminders
                    (title, description, due_time, important)
                VALUES (?, ?, ?, ?)
                """,
                (
                    title.strip(),
                    description.strip(),
                    parsed_time.isoformat(timespec="seconds"),
                    int(important),
                ),
            )

        return cursor.lastrowid

    def close(self):
        """Закрыть соединение с базой."""
        self.connection.close()


if __name__ == "__main__":
    database = ReminderDatabase()
    try:
        print("База reminders.db и таблица reminders готовы.")
    finally:
        database.close()