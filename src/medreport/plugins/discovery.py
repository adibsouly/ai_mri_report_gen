"""Plugin discovery via Python entry points."""

from __future__ import annotations

from importlib.metadata import entry_points

from medreport.plugins.sdk import MedReportPlugin


def discover_plugins(group: str = "medreport.plugins") -> list[MedReportPlugin]:
    """Discover installed MedReport plugins without core code changes."""

    discovered: list[MedReportPlugin] = []
    for entry_point in entry_points(group=group):
        plugin = entry_point.load()()
        discovered.append(plugin)
    return discovered
