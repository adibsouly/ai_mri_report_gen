"""PDF export for rendered Markdown report drafts."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QPageSize, QPdfWriter, QTextDocument


def save_markdown_pdf(markdown: str, path: Path) -> None:
    """Render a Markdown report into a paginated A4 PDF file."""

    document = QTextDocument()
    document.setDocumentMargin(48)
    document.setMarkdown(markdown)

    writer = QPdfWriter(str(path))
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    writer.setResolution(144)
    document.print_(writer)
