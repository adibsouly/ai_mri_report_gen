"""Generate AI MRI Analyzer raster icon assets from source artwork."""

from __future__ import annotations

from pathlib import Path

from PIL import Image


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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
