"""Plugin SDK contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class PluginMetadata:
    """Public metadata exposed by a plugin."""

    name: str
    version: str
    description: str
    capabilities: tuple[str, ...]


class MedReportPlugin(Protocol):
    """Protocol implemented by MedReport plugins."""

    metadata: PluginMetadata

    def activate(self) -> None:
        """Activate plugin resources."""

    def deactivate(self) -> None:
        """Release plugin resources."""
