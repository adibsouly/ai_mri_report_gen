"""Tests for cancellable AI background workers."""

from __future__ import annotations

from typing import Any

from medreport.ui.workers import AIChatWorker


class StubChatService:
    """Return a fixed answer for worker lifecycle testing."""

    def __init__(self) -> None:
        self.cancelled = False

    def chat_about_report(self, **_kwargs: Any) -> str:
        """Return a response that should be suppressed after cancellation."""

        return "Late answer"

    def cancel_active_request(self) -> None:
        """Record the worker's provider cancellation signal."""

        self.cancelled = True


def test_cancelled_chat_worker_suppresses_late_result(qtbot: Any) -> None:
    service = StubChatService()
    worker = AIChatWorker(
        service=service,  # type: ignore[arg-type]
        report="Draft report",
        question="What does this mean?",
        conversation=[],
    )
    answers: list[str] = []
    worker.signals.finished.connect(answers.append)

    worker.cancel()
    worker.run()
    qtbot.wait(1)

    assert answers == []
    assert service.cancelled
