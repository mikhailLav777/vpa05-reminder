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

    def get_all_reminders(self):
        """Получить все напоминания: ближайшие по времени первыми."""
        cursor = self.connection.execute(
            "SELECT * FROM reminders ORDER BY due_time, id"
        )
        return cursor.fetchall()

    def get_reminder_by_id(self, reminder_id):
        """Найти напоминание по номеру или вернуть None."""
        if type(reminder_id) is not int or reminder_id <= 0:
            raise ValueError("Номер напоминания должен быть целым числом больше нуля.")

        cursor = self.connection.execute(
            "SELECT * FROM reminders WHERE id = ?",
            (reminder_id,),
        )
        return cursor.fetchone()

    def update_status(self, reminder_id, status):
        """Изменить статус. Вернуть False, если запись не найдена."""
        if type(reminder_id) is not int or reminder_id <= 0:
            raise ValueError("Номер напоминания должен быть целым числом больше нуля.")

        allowed_statuses = ("Ожидает", "Готово", "Просрочено", "Отменено")
        if status not in allowed_statuses:
            raise ValueError("Неизвестный статус напоминания.")

        with self.connection:
            cursor = self.connection.execute(
                "UPDATE reminders SET status = ? WHERE id = ?",
                (status, reminder_id),
            )

        return cursor.rowcount == 1

    def delete_reminder(self, reminder_id):
        """Удалить напоминание по номеру."""
        if type(reminder_id) is not int or reminder_id <= 0:
            raise ValueError(
                "Номер напоминания должен быть целым числом больше нуля."
            )

        with self.connection:
            cursor = self.connection.execute(
                "DELETE FROM reminders WHERE id = ?",
                (reminder_id,),
            )

        return cursor.rowcount == 1
    def get_reminders_count(self):
        """Получить общее количество напоминаний."""
        cursor = self.connection.execute(
            "SELECT COUNT(*) FROM reminders"
        )
        return cursor.fetchone()[0]

    def get_due_reminders(self):
        """Получить ожидающие напоминания, время которых наступило."""
        current_time = datetime.now().isoformat(timespec="seconds")
        cursor = self.connection.execute(
            "SELECT * FROM reminders "
            "WHERE status = ? AND due_time <= ? "
            "ORDER BY due_time, id",
            ("Ожидает", current_time),
        )
        return cursor.fetchall()

    def close(self):
            """Закрыть соединение с базой."""
            self.connection.close()


if __name__ == "__main__":
    database = ReminderDatabase()
    try:
        print("База reminders.db и таблица reminders готовы.")
    finally:
        database.close()