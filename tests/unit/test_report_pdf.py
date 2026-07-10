from pathlib import Path

from medreport.reports.pdf import save_markdown_pdf


def test_save_markdown_pdf_renders_report(tmp_path: Path) -> None:
    output = tmp_path / "report.pdf"

    save_markdown_pdf("# MRI Report\n\n## Impression\nNo focal abnormality.", output)

    assert output.read_bytes().startswith(b"%PDF")
