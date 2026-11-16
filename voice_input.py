"""Запись по кнопке; русский текст распознаётся после остановки записи."""

from queue import Queue, Empty
from threading import Event, Thread
from time import monotonic
from tkinter import messagebox


def record_and_recognize(events, stop, discard, speech_module=None):
    """Рабочий поток не обращается к Tkinter и не сохраняет аудио на диск."""
    try:
        if speech_module is None:
            import speech_recognition as speech_module
        sr = speech_module
        frames = []

        with sr.Microphone() as source:
            events.put(("recording", None))
            deadline = monotonic() + 45
            while not stop.is_set() and monotonic() < deadline:
                frames.append(source.stream.read(source.CHUNK))
            rate, width = source.SAMPLE_RATE, source.SAMPLE_WIDTH

        if discard.is_set() or not frames:
            return

        events.put(("processing", None))
        recognizer = sr.Recognizer()
        recognizer.operation_timeout = 15
        audio = sr.AudioData(b"".join(frames), rate, width)

        if discard.is_set():
            return

        try:
            text = recognizer.recognize_google(
                audio, language="ru-RU",
                endpoint="https://www.google.com/speech-api/v2/recognize",
            )
        except sr.UnknownValueError:
            events.put((
                "error",
                "Не удалось разобрать речь. Попробуй ещё раз, "
                "говоря ближе к микрофону.",
            ))
        except sr.RequestError as error:
            events.put((
                "error",
                "Сервис распознавания недоступен. Проверь интернет.\n"
                + str(error),
            ))
        else:
            if not discard.is_set() and text.strip():
                events.put(("text", text.strip()))

    except (ImportError, AttributeError):
        events.put((
            "error",
            "Для диктовки установи зависимости из requirements.txt "
            "и перезапусти приложение.",
        ))
    except Exception as error:
        events.put((
            "error",
            "Не удалось выполнить диктовку. Проверь микрофон "
            "и доступ к нему в Windows.\n" + str(error),
        ))
    finally:
        events.put(("finished", None))


class VoiceInput:
    def __init__(self, app, status):
        self.app, self.status = app, status
        self.target, self.session = None, None
        self.timer = self.app.after(80, self.poll)
        self.closed = False

    @property
    def busy(self):
        return self.session is not None

    def toggle(self, field):
        if self.session is not None:
            if self.target is field:
                self.session[1].set()
                field.set_voice_state("processing")
                self.status(
                    "Останавливаю запись. Затем появится распознанный текст…"
                )
            else:
                messagebox.showinfo(
                    "Диктовка", "Сначала заверши текущую диктовку.",
                    parent=field.winfo_toplevel(),
                )
            return

        field.activate()
        field.entry.mark_set("dictation", "insert")
        field.entry.mark_gravity("dictation", "right")
        self.target = field
        events, stop, discard = Queue(), Event(), Event()
        self.session = (events, stop, discard)
        field.set_voice_state("preparing")
        self.status("Подключаю микрофон…")
        Thread(
            target=record_and_recognize,
            args=self.session,
            daemon=True,
        ).start()

    def cancel(self, field):
        if self.target is field and self.session is not None:
            self.session[2].set()
            self.session[1].set()
            self.target = None
            if field.winfo_exists():
                field.set_voice_state("idle")

    def poll(self):
        self.timer = None
        if self.closed:
            return

        if self.session is not None:
            events, stop, discard = self.session
            while True:
                try:
                    kind, value = events.get_nowait()
                except Empty:
                    break

                field = self.target
                valid = (
                    field is not None and field.winfo_exists()
                    and not discard.is_set()
                )

                if kind == "finished":
                    if valid:
                        field.set_voice_state("idle")
                    self.target, self.session = None, None
                    self.status(
                        "Диктовка завершена. Изменения задачи нужно сохранить."
                    )
                    break

                if not valid:
                    continue

                if kind == "recording" and not stop.is_set():
                    field.set_voice_state("recording")
                    self.app.bell()
                    self.status(
                        "Микрофон включён: говори. Нажми его ещё раз "
                        "для остановки. До 45 секунд."
                    )
                elif kind == "processing":
                    field.set_voice_state("processing")
                    self.app.bell()
                    self.status(
                        "Запись остановлена. Распознаю речь через интернет…"
                    )
                elif kind == "text":
                    field.insert_voice(value)
                elif kind == "error":
                    messagebox.showerror(
                        "Диктовка", value, parent=field.winfo_toplevel(),
                    )

        self.timer = self.app.after(80, self.poll)

    def close(self):
        self.closed = True
        if self.session is not None:
            self.session[2].set()
            self.session[1].set()
        if self.timer is not None:
            self.app.after_cancel(self.timer)
            self.timer = None


# КОНЕЦ ФАЙЛА voice_input.py