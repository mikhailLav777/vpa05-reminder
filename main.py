"""Запуск напоминалки с постоянным хранением задач."""

import argparse


def main():
    parser = argparse.ArgumentParser(description="Мои напоминания")
    parser.add_argument("--classic", action="store_true", help="Открыть прежнее главное окно")
    args = parser.parse_args()

    if args.classic:
        from live_app import LiveApp
        from ui_scale import ScaleController, install_scaling

        install_scaling()
        app = LiveApp()
        app.scale_controller = ScaleController(app)
    else:
        from standard_app import StandardApp

        app = StandardApp()
    app.mainloop()


if __name__ == "__main__":
    main()
