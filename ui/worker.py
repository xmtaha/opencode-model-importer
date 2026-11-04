from PySide6.QtCore import QThread, Signal


class Worker(QThread):
    """Runs one blocking job off the UI thread."""

    done = Signal(object)
    failed = Signal(str)

    def __init__(self, job):
        super().__init__()
        self.job = job

    def run(self):
        try:
            self.done.emit(self.job())
        except Exception as error:  # every error reaches the user as text; nothing is logged
            self.failed.emit(str(error) or error.__class__.__name__)
