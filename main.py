"""Запуск главного окна с постоянным хранением задач."""

from live_app import LiveApp
from ui_scale import ScaleController, install_scaling


def main():
    install_scaling()
    app = LiveApp()
    app.scale_controller = ScaleController(app)
    app.mainloop()


if __name__ == "__main__":
    main()