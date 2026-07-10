"""Generate MedReport raster icon assets."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


def main() -> int:
    """Create the app icon PNG used by Qt and packaging."""

    root = Path(__file__).resolve().parents[1]
    out_dir = root / "assets" / "icons"
    out_dir.mkdir(parents=True, exist_ok=True)
    size = 1024
    image = Image.new("RGBA", (size, size), (8, 12, 18, 255))
    draw = ImageDraw.Draw(image)

    for radius, alpha in [(410, 32), (330, 48), (250, 64)]:
        bbox = (size // 2 - radius, size // 2 - radius, size // 2 + radius, size // 2 + radius)
        draw.ellipse(bbox, fill=(20, 184, 166, alpha))

    tile = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    tile_draw = ImageDraw.Draw(tile)
    tile_draw.rounded_rectangle((146, 146, 878, 878), radius=160, fill=(18, 24, 34, 255))
    tile_draw.rounded_rectangle(
        (146, 146, 878, 878),
        radius=160,
        outline=(59, 130, 246, 255),
        width=18,
    )
    image.alpha_composite(tile)

    scan = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    scan_draw = ImageDraw.Draw(scan)
    scan_draw.ellipse((270, 220, 754, 804), outline=(226, 232, 240, 255), width=28)
    scan_draw.arc((335, 275, 690, 735), start=75, end=285, fill=(20, 184, 166, 255), width=26)
    scan_draw.arc((410, 310, 610, 710), start=250, end=110, fill=(147, 197, 253, 255), width=20)
    scan_draw.line((512, 244, 512, 790), fill=(71, 85, 105, 160), width=6)
    scan_draw.line((290, 512, 734, 512), fill=(71, 85, 105, 130), width=6)

    for point in [(662, 318), (724, 512), (640, 690), (382, 382), (364, 626)]:
        scan_draw.ellipse(
            (point[0] - 28, point[1] - 28, point[0] + 28, point[1] + 28),
            fill=(59, 130, 246, 255),
        )
    scan_draw.line((662, 318, 724, 512, 640, 690), fill=(59, 130, 246, 180), width=12)
    scan_draw.line((382, 382, 512, 512, 364, 626), fill=(20, 184, 166, 180), width=10)

    glow = scan.filter(ImageFilter.GaussianBlur(10))
    image.alpha_composite(glow)
    image.alpha_composite(scan)

    image.save(out_dir / "medreport_icon.png")
    image.resize((256, 256), Image.Resampling.LANCZOS).save(out_dir / "medreport_icon_256.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
