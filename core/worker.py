"""
Background-thread worker infrastructure built on QThreadPool + QRunnable.

Usage
-----
    worker = Worker(my_function, arg1, arg2, kwarg=value)
    worker.signals.progress.connect(on_progress)
    worker.signals.result.connect(on_result)
    worker.signals.error.connect(on_error)
    worker.signals.finished.connect(on_finished)
    QThreadPool.globalInstance().start(worker)
"""

import traceback
from typing import Any, Callable

from PyQt6.QtCore import QObject, QRunnable, pyqtSignal, pyqtSlot


class WorkerSignals(QObject):
    """Signals emitted by a Worker during its lifecycle."""

    # (int) 0-100 progress percentage
    progress = pyqtSignal(int)
    # (str) human-readable status message
    status = pyqtSignal(str)
    # result value returned by the callable
    result = pyqtSignal(object)
    # (str) error message on exception
    error = pyqtSignal(str)
    # emitted when the callable finishes (success or error)
    finished = pyqtSignal()


class Worker(QRunnable):
    """
    Wraps any callable so it runs off the main thread.

    The callable may optionally accept keyword arguments ``progress_callback``
    and ``status_callback`` which are connected to the corresponding signals.
    """

    def __init__(self, fn: Callable, *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()
        self.setAutoDelete(True)

        # Inject callbacks if the function accepts them
        self.kwargs["progress_callback"] = self.signals.progress.emit
        self.kwargs["status_callback"] = self.signals.status.emit

    @pyqtSlot()
    def run(self) -> None:
        try:
            result = self.fn(*self.args, **self.kwargs)
            self.signals.result.emit(result)
        except Exception:
            self.signals.error.emit(traceback.format_exc())
        finally:
            self.signals.finished.emit()
