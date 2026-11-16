"""Запуск главного окна с постоянным хранением задач."""

from live_app import LiveApp


def main():
    app = LiveApp()
    app.mainloop()


if __name__ == "__main__":
    main()