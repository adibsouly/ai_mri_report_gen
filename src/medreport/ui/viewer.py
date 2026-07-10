"""Interactive 2D image viewer widget."""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QImage, QPainter, QPixmap, QTransform, QWheelEvent
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

    def set_volume(self, volume: ImageVolume) -> None:
        """Display a newly loaded image volume."""

        self._volume = volume
        self._slice_index = 0
        self.reset_view()
        self._render_slice()

    def reset_view(self) -> None:
        """Reset transform and image adjustments."""

        self._zoom = 1.0
        self._rotation = 0
        self._flip_horizontal = False
        self._flip_vertical = False
        self.setTransform(QTransform())
        self.fitInView(self._pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)

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
            self._zoom *= factor
            self.scale(factor, factor)
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

    def mousePressEvent(self, event: object) -> None:
        """Keep typed event signature local to PySide overloads."""

        super().mousePressEvent(event)  # type: ignore[arg-type]

    def mouseMoveEvent(self, event: object) -> None:
        """Keep typed event signature local to PySide overloads."""

        super().mouseMoveEvent(event)  # type: ignore[arg-type]

    def mapToImage(self, point: QPoint) -> QPoint:
        """Map a viewport position to image scene coordinates."""

        return self.mapToScene(point).toPoint()
