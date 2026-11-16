import tkinter as tk


class ReminderApp(tk.Tk):
    """Главное окно учебного прототипа."""

    def __init__(self):
        super().__init__()

        self.title("Мои напоминания — учебный прототип")
        self.geometry("1100x720")
        self.minsize(900, 600)
        self.configure(bg="#2D0B53")

        heading = tk.Label(
            self,
            text="Мои напоминания",
            font=("Segoe UI", 24, "bold"),
            bg="#2D0B53",
            fg="#FFFFFF",
        )
        heading.pack(anchor="w", padx=24, pady=20)