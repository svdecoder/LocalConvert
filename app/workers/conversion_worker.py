"""Background execution of conversion jobs.

Uses Qt's QThreadPool/QRunnable rather than raw Python threads so that
progress and completion can be delivered back to the GUI thread safely
via Qt signals (Qt signal/slot delivery across threads is queued
automatically when connected to objects living on the main thread).

The GUI never calls a converter directly — it always goes through
:class:`ConversionQueueManager`, which owns the thread pool, enforces the
"max simultaneous conversions" setting, and supports safe cancellation.
"""

from __future__ import annotations

import threading
from typing import Optional

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

from app.converters.base import registry
from app.models import ConversionJob, ConversionResult, JobStatus
from app.utils.logging_setup import get_logger

logger = get_logger("workers.conversion")


class _JobSignals(QObject):
    progress = Signal(str, float, str)  # job_id, fraction, message
    finished = Signal(str, object)      # job_id, ConversionResult
    started = Signal(str)               # job_id


class _JobRunnable(QRunnable):
    def __init__(self, job: ConversionJob):
        super().__init__()
        self.job = job
        self.signals = _JobSignals()
        self._cancel_event = threading.Event()
        self.setAutoDelete(True)

    def cancel(self) -> None:
        self._cancel_event.set()

    @Slot()
    def run(self) -> None:
        self.signals.started.emit(self.job.job_id)
        found = registry.find_capability(self.job.input_format, self.job.output_format)
        if not found:
            result = ConversionResult(
                job_id=self.job.job_id,
                success=False,
                output_path=None,
                error_message=(
                    f"No converter supports {self.job.input_format.upper()} -> "
                    f"{self.job.output_format.upper()}."
                ),
            )
            self.signals.finished.emit(self.job.job_id, result)
            return

        converter, _capability = found

        def progress_cb(fraction: float, message: str) -> None:
            self.signals.progress.emit(self.job.job_id, fraction, message)

        try:
            result = converter.convert(
                self.job, progress_cb=progress_cb, cancel_check=self._cancel_event.is_set
            )
        except Exception as exc:  # noqa: BLE001 - the GUI must never crash from a worker
            logger.exception("Unhandled exception in converter for job %s", self.job.job_id)
            result = ConversionResult(
                job_id=self.job.job_id, success=False, output_path=None,
                error_message=f"Unexpected error: {exc}",
            )

        if self._cancel_event.is_set() and not result.success:
            result.error_message = result.error_message or "Cancelled by user."

        self.signals.finished.emit(self.job.job_id, result)


class ConversionQueueManager(QObject):
    """Owns the QThreadPool and exposes Qt signals the GUI can bind to.

    All signals are emitted on the GUI thread's event loop (Qt handles the
    cross-thread marshalling), so slots connected to these can safely
    touch widgets directly.
    """

    job_started = Signal(str)
    job_progress = Signal(str, float, str)
    job_finished = Signal(str, object)  # job_id, ConversionResult
    queue_idle = Signal()

    def __init__(self, max_concurrent: int = 2, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._pool = QThreadPool()
        self.set_max_concurrent(max_concurrent)
        self._active_runnables: dict[str, _JobRunnable] = {}
        self._lock = threading.Lock()

    def set_max_concurrent(self, n: int) -> None:
        self._pool.setMaxThreadCount(max(1, int(n)))

    def submit(self, job: ConversionJob) -> None:
        runnable = _JobRunnable(job)
        runnable.signals.started.connect(self._on_started)
        runnable.signals.progress.connect(self._on_progress)
        runnable.signals.finished.connect(self._on_finished)
        with self._lock:
            self._active_runnables[job.job_id] = runnable
        self._pool.start(runnable)

    def cancel(self, job_id: str) -> None:
        with self._lock:
            runnable = self._active_runnables.get(job_id)
        if runnable:
            runnable.cancel()

    def cancel_all(self) -> None:
        with self._lock:
            runnables = list(self._active_runnables.values())
        for r in runnables:
            r.cancel()

    def _on_started(self, job_id: str) -> None:
        self.job_started.emit(job_id)

    def _on_progress(self, job_id: str, fraction: float, message: str) -> None:
        self.job_progress.emit(job_id, fraction, message)

    def _on_finished(self, job_id: str, result: ConversionResult) -> None:
        with self._lock:
            self._active_runnables.pop(job_id, None)
            remaining = len(self._active_runnables)
        self.job_finished.emit(job_id, result)
        if remaining == 0:
            self.queue_idle.emit()

    def active_count(self) -> int:
        with self._lock:
            return len(self._active_runnables)

    def wait_for_all(self, timeout_ms: int = -1) -> bool:
        return self._pool.waitForDone(timeout_ms)
