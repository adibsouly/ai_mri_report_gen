"""Interactive 2D image viewer widget."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint, QRectF, Qt
from PySide6.QtGui import QImage, QPageSize, QPainter, QPdfWriter, QPixmap, QTransform, QWheelEvent
from PySide6.QtWidgets import QGraphicsPixmapItem, QGraphicsScene, QGraphicsView

from medreport.models import ImageVolume
from medreport.viewer.windowing import normalize_to_uint8


class ImageViewer(QGraphicsView):
    """Qt graphics-view based DICOM slice viewer."""

    def __init__(self) -> None:
        super().__init__()
        self._scene = QGraphicsScene(self)
        self._pixmap_item = QGraphicsPixmapItem()
        self._scene.addItem(self._pixmap_item)
        self.setScene(self._scene)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self._volume: ImageVolume | None = None
        self._slice_index = 0
        self._zoom = 1.0
        self._invert = False
        self._rotation = 0
        self._flip_horizontal = False
        self._flip_vertical = False

    @property
    def slice_index(self) -> int:
        """Return the current slice index."""

        return self._slice_index

    @property
    def has_image(self) -> bool:
        """Return whether the viewer currently has an image."""

        return self._volume is not None and not self._pixmap_item.pixmap().isNull()

    def set_volume(self, volume: ImageVolume) -> None:
        """Display a newly loaded image volume."""

        self._volume = volume
        self._slice_index = 0
        self.reset_view()
        self._render_slice()

    def set_slice_index(self, index: int) -> None:
        """Jump to a specific slice index."""

        if self._volume is None:
            return
        self._slice_index = max(0, min(self._volume.slice_count - 1, index))
        self._render_slice()

    def previous_slice(self) -> None:
        """Move to the previous slice."""

        self.set_slice_index(self._slice_index - 1)

    def next_slice(self) -> None:
        """Move to the next slice."""

        self.set_slice_index(self._slice_index + 1)

    def reset_view(self) -> None:
        """Reset transform and image adjustments."""

        self._zoom = 1.0
        self._rotation = 0
        self._flip_horizontal = False
        self._flip_vertical = False
        self.setTransform(QTransform())
        self.fitInView(self._pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)

    def zoom_in(self) -> None:
        """Zoom into the current image."""

        self._scale_view(1.2)

    def zoom_out(self) -> None:
        """Zoom out of the current image."""

        self._scale_view(1 / 1.2)

    def fit_to_window(self) -> None:
        """Fit the current image to the viewport."""

        self.setTransform(QTransform())
        self.fitInView(self._pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)

    def set_pan_enabled(self, enabled: bool) -> None:
        """Enable or disable hand-drag panning."""

        mode = (
            QGraphicsView.DragMode.ScrollHandDrag
            if enabled
            else QGraphicsView.DragMode.NoDrag
        )
        self.setDragMode(mode)

    def export_jpeg(self, path: Path) -> bool:
        """Export the current rendered image as a JPEG file."""

        image = self.current_image()
        if image is None:
            return False
        return bool(image.save(str(path), b"JPEG", 95))

    def export_pdf(self, path: Path) -> bool:
        """Export the current rendered image as a single-page PDF."""

        image = self.current_image()
        if image is None:
            return False
        writer = QPdfWriter(str(path))
        writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        writer.setResolution(300)
        painter = QPainter(writer)
        page_rect = QRectF(writer.pageLayout().paintRectPixels(writer.resolution()))
        image_size = image.size()
        scale = min(
            page_rect.width() / image_size.width(),
            page_rect.height() / image_size.height(),
        )
        scaled_rect = QRectF(
            0,
            0,
            image_size.width() * scale,
            image_size.height() * scale,
        )
        scaled_rect.moveCenter(page_rect.center())
        painter.drawImage(scaled_rect, image)
        painter.end()
        return True

    def current_image(self) -> QImage | None:
        """Return the currently rendered image, including view adjustments."""

        if not self.has_image:
            return None
        scene_rect = self._scene.itemsBoundingRect()
        width = max(1, int(scene_rect.width()))
        height = max(1, int(scene_rect.height()))
        image = QImage(width, height, QImage.Format.Format_RGB32)
        image.fill(Qt.GlobalColor.black)
        painter = QPainter(image)
        self._scene.render(painter, QRectF(image.rect()), scene_rect)
        painter.end()
        return image

    def set_inverted(self, enabled: bool) -> None:
        """Enable or disable grayscale inversion."""

        self._invert = enabled
        self._render_slice()

    def rotate_right(self) -> None:
        """Rotate the current view clockwise."""

        self._rotation = (self._rotation + 90) % 360
        self._apply_transform()

    def flip_horizontal(self) -> None:
        """Flip the current view horizontally."""

        self._flip_horizontal = not self._flip_horizontal
        self._apply_transform()

    def flip_vertical(self) -> None:
        """Flip the current view vertically."""

        self._flip_vertical = not self._flip_vertical
        self._apply_transform()

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Scroll slices with the wheel; hold Ctrl to zoom."""

        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
            self._scale_view(factor)
            return

        if self._volume is None:
            return
        direction = -1 if event.angleDelta().y() > 0 else 1
        self._slice_index = max(0, min(self._volume.slice_count - 1, self._slice_index + direction))
        self._render_slice()

    def mouseDoubleClickEvent(self, event: object) -> None:
        """Reset the view on double click."""

        self.reset_view()

    def _render_slice(self) -> None:
        if self._volume is None:
            self._pixmap_item.setPixmap(QPixmap())
            return

        pixels = normalize_to_uint8(self._volume.slice_at(self._slice_index), invert=self._invert)
        height, width = pixels.shape
        image = QImage(pixels.data, width, height, width, QImage.Format.Format_Grayscale8).copy()
        self._pixmap_item.setPixmap(QPixmap.fromImage(image))
        self._scene.setSceneRect(self._pixmap_item.boundingRect())
        self._apply_transform()

    def _apply_transform(self) -> None:
        transform = QTransform()
        transform.rotate(self._rotation)
        transform.scale(-1 if self._flip_horizontal else 1, -1 if self._flip_vertical else 1)
        self._pixmap_item.setTransform(transform)
        self._scene.setSceneRect(self._scene.itemsBoundingRect())

    def _scale_view(self, factor: float) -> None:
        self._zoom *= factor
        self.scale(factor, factor)

    def mousePressEvent(self, event: object) -> None:
        """Keep typed event signature local to PySide overloads."""

        super().mousePressEvent(event)  # type: ignore[arg-type]

    def mouseMoveEvent(self, event: object) -> None:
        """Keep typed event signature local to PySide overloads."""

        super().mouseMoveEvent(event)  # type: ignore[arg-type]

    def mapToImage(self, point: QPoint) -> QPoint:
        """Map a viewport position to image scene coordinates."""

        return self.mapToScene(point).toPoint()
