"""Просмотр утверждённых макетов внутри приложения."""

from pathlib import Path
import tkinter as tk
from tkinter import messagebox

from PIL import Image, ImageOps, ImageTk

from gui import BG, MUTED, WHITE, NeonButton
from demo_completion import DemoApp


ASSETS = Path(__file__).resolve().parent / "assets"

ROUTES = {
    "Настройки": ("Настройки", "settings.png"),
    "План на неделю": ("План на неделю", "week.png"),
    "Пример уведомления": (
        "Пример уведомления",
        "notification.png",
    ),
}


def read_mockup(path):
    with Image.open(path) as source:
        return source.convert("RGBA")


class MockupViewer(tk.Toplevel):
    """Изображение с настоящими кнопками возврата и масштаба."""

    def __init__(self, app, title, image, task=None):
        super().__init__(app)

        self.app = app
        self.image = image
        self.photo = None
        self.timer = None
        self.fit_all = False

        self.title(f"{title} — макет")
        self.configure(bg=BG)
        self.geometry("1040x760")
        self.minsize(900, 560)
        self.transient(app)
        self.protocol("WM_DELETE_WINDOW", self.close)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        toolbar = tk.Frame(self, bg=BG)
        toolbar.grid(
            row=0, column=0, sticky="ew",
            padx=12, pady=10,
        )
        toolbar.grid_columnconfigure(1, weight=1)

        NeonButton(
            toolbar,
            "Назад на главную",
            self.close,
            icon_name="arrow",
            width=235,
            height=42,
            font_size=17,
        ).grid(row=0, column=0)

        tk.Label(
            toolbar,
            text=title,
            fg=WHITE,
            bg=BG,
            font=("Segoe UI", -22, "bold"),
        ).grid(row=0, column=1, padx=12)

        NeonButton(
            toolbar,
            "По ширине",
            lambda: self.set_mode(False),
            style="purple",
            width=125,
            height=36,
            font_size=15,
        ).grid(row=0, column=2)

        NeonButton(
            toolbar,
            "Вписать целиком",
            lambda: self.set_mode(True),
            style="purple",
            width=155,
            height=36,
            font_size=15,
        ).grid(row=0, column=3, padx=(5, 0))

        context = tk.Frame(self, bg=BG)
        context.grid(
            row=1, column=0, sticky="ew",
            padx=18, pady=(0, 8),
        )
        context.grid_columnconfigure(0, weight=1)

        if task is not None:
            text = (
                f"Выбрана задача: {task.card[0]}"
                f"  ·  Статус: {task.card[2]}"
            )

            self.context_title = tk.Label(
                context,
                text=text,
                fg=WHITE,
                bg=BG,
                font=("Segoe UI", -18, "bold"),
                anchor="w",
                justify="left",
            )
            self.context_title.grid(
                row=0, column=0, sticky="ew",
            )

            self.context_description = tk.Label(
                context,
                text=task.description,
                fg=MUTED,
                bg=BG,
                font=("Segoe UI", -15),
                anchor="w",
                justify="left",
            )
            self.context_description.grid(
                row=1, column=0, sticky="ew", pady=(4, 0),
            )

            context.bind(
                "<Configure>",
                lambda event: self._wrap_context(event.width),
            )

        tk.Label(
            context,
            text=(
                "Ниже — изображение макета с примером данных. "
                "Кнопки внутри изображения не работают."
            ),
            fg=MUTED,
            bg=BG,
            font=("Segoe UI", -13),
            anchor="w",
            justify="left",
            wraplength=710,
        ).grid(
            row=2, column=0, sticky="w", pady=(6, 0),
        )

        area = tk.Frame(self, bg=BG)
        area.grid(
            row=2, column=0, sticky="nsew",
            padx=12, pady=(0, 12),
        )
        area.grid_columnconfigure(0, weight=1)
        area.grid_rowconfigure(0, weight=1)

        self.canvas = tk.Canvas(
            area,
            bg=BG,
            bd=0,
            highlightthickness=0,
            width=500,
            height=400,
            yscrollincrement=32,
        )
        self.canvas.grid(
            row=0, column=0, sticky="nsew",
        )

        scrollbar = tk.Scrollbar(
            area,
            orient="vertical",
            command=self.canvas.yview,
        )
        scrollbar.grid(
            row=0, column=1, sticky="ns",
        )
        self.canvas.configure(
            yscrollcommand=scrollbar.set,
        )

        self.canvas.bind("<Configure>", self.schedule_render)
        self.canvas.bind("<MouseWheel>", self.mouse_wheel)
        self.canvas.bind(
            "<Button-4>",
            lambda event: self.canvas.yview_scroll(-1, "units"),
        )
        self.canvas.bind(
            "<Button-5>",
            lambda event: self.canvas.yview_scroll(1, "units"),
        )
        self.bind("<Escape>", lambda event: self.close())

        self.schedule_render()
        self.focus_set()

    def _wrap_context(self, width):
        self.context_title.configure(
            wraplength=max(200, width),
        )
        self.context_description.configure(
            wraplength=max(200, width),
        )

    def set_mode(self, fit_all):
        self.fit_all = fit_all
        self.canvas.yview_moveto(0)
        self.schedule_render()

    def schedule_render(self, event=None):
        if self.timer is not None:
            self.after_cancel(self.timer)
        self.timer = self.after(80, self.render)

    def render(self):
        self.timer = None

        width = max(1, self.canvas.winfo_width() - 16)
        height = max(1, self.canvas.winfo_height() - 16)

        if self.fit_all:
            target = (
                min(width, self.image.width),
                min(height, self.image.height),
            )
        else:
            ratio = min(1, width / self.image.width)
            target = (
                max(1, round(self.image.width * ratio)),
                max(1, round(self.image.height * ratio)),
            )

        resized = ImageOps.contain(
            self.image,
            target,
            Image.Resampling.LANCZOS,
        )
        self.photo = ImageTk.PhotoImage(
            resized, master=self,
        )

        first = self.canvas.yview()[0]
        self.canvas.delete("preview")

        x = max(
            8,
            (self.canvas.winfo_width() - resized.width) / 2,
        )
        self.canvas.create_image(
            x, 8,
            anchor="nw",
            image=self.photo,
            tags="preview",
        )
        self.canvas.configure(
            scrollregion=(
                0, 0,
                self.canvas.winfo_width(),
                resized.height + 16,
            ),
        )
        self.canvas.yview_moveto(first)

    def mouse_wheel(self, event):
        if event.delta:
            if abs(event.delta) >= 120:
                units = -int(event.delta / 120)
            else:
                units = -1 if event.delta > 0 else 1
            self.canvas.yview_scroll(units, "units")
        return "break"

    def close(self):
        if self.timer is not None:
            self.after_cancel(self.timer)
            self.timer = None

        self.destroy()
        self.app.lift()
        self.app.focus_set()


class NavigationApp(DemoApp):
    """Добавляет просмотр макетов к работающему главному экрану."""

    def __init__(self):
        self.mockup_window = None
        super().__init__()

    def stage_message(self, action):
        task = None

        if action.startswith("Подробности: "):
            name = action.removeprefix("Подробности: ")
            task = next(
                (
                    item
                    for item in self.demo_tasks
                    if item.card[0] == name
                ),
                None,
            )
            title = "Подробности задачи"
            filename = "details.png"

        elif action in ROUTES:
            title, filename = ROUTES[action]

        else:
            super().stage_message(action)
            return

        path = ASSETS / filename

        try:
            image = read_mockup(path)
        except (OSError, Image.DecompressionBombError) as error:
            messagebox.showerror(
                "Не удалось открыть макет",
                f"Проверь файл:\n{path}\n\n{error}",
                parent=self,
            )
            return

        if (
            self.mockup_window is not None
            and self.mockup_window.winfo_exists()
        ):
            self.mockup_window.close()

        self.mockup_window = MockupViewer(
            self, title, image, task,
        )


# КОНЕЦ ФАЙЛА mockup_navigation.py