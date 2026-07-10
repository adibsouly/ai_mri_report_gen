"""Protocols for future AI model providers."""

from __future__ import annotations

from typing import Protocol

from medreport.models import ImageVolume


class SegmentationModel(Protocol):
    """Model capable of returning segmentation masks."""

    name: str

    def segment(self, volume: ImageVolume) -> object:
        """Run segmentation on an image volume."""


class ClassificationModel(Protocol):
    """Model capable of classifying image findings."""

    name: str

    def classify(self, volume: ImageVolume) -> dict[str, float]:
        """Return class confidence scores."""


class DetectionModel(Protocol):
    """Model capable of detecting localized findings."""

    name: str

    def detect(self, volume: ImageVolume) -> list[dict[str, object]]:
        """Return detected findings."""


class ReportGenerationModel(Protocol):
    """Model capable of generating report text."""

    name: str

    def generate_report(self, prompt: str, context: dict[str, object]) -> str:
        """Generate a report from findings context."""
