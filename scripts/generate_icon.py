"""Generate DecodeMRI raster icon assets from source artwork."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw


def _center_square(image: Image.Image) -> Image.Image:
    width, height = image.size
    side = min(width, height)
    left = (width - side) // 2
    top = (height - side) // 2
    return image.crop((left, top, left + side, top + side))


def main() -> int:
    """Create the app icon PNG used by Qt and packaging."""

    root = Path(__file__).resolve().parents[1]
    out_dir = root / "assets" / "icons"
    source_path = out_dir / "ai_mri_analyzer_source.jpg"
    out_dir.mkdir(parents=True, exist_ok=True)
    if not source_path.exists():
        raise FileNotFoundError(f"Missing icon source artwork: {source_path}")

    image = Image.open(source_path).convert("RGBA")
    square = _center_square(image)
    square.resize((1024, 1024), Image.Resampling.LANCZOS).save(out_dir / "medreport_icon.png")
    square.resize((256, 256), Image.Resampling.LANCZOS).save(out_dir / "medreport_icon_256.png")
    _save_export_icon(out_dir / "export_jpeg_icon.png", "JPG", (14, 116, 144), (34, 211, 238))
    _save_export_icon(out_dir / "export_pdf_icon.png", "PDF", (153, 27, 27), (248, 113, 113))
    return 0


def _save_export_icon(
    path: Path,
    label: str,
    accent: tuple[int, int, int],
    text_color: tuple[int, int, int],
) -> None:
    image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((14, 6, 50, 58), radius=5, fill=(241, 245, 249, 255))
    draw.polygon([(39, 6), (50, 17), (39, 17)], fill=(203, 213, 225, 255))
    draw.rectangle((14, 38, 50, 55), fill=accent)
    draw.text((20, 40), label, fill=text_color)
    image.save(path)


if __name__ == "__main__":
    raise SystemExit(main())
