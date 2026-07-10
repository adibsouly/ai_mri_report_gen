"""Application-specific exception hierarchy."""


class MedReportError(Exception):
    """Base class for all expected MedReport failures."""


class DicomImportError(MedReportError):
    """Raised when DICOM import cannot complete."""


class VolumeLoadError(MedReportError):
    """Raised when image volume loading fails."""


class PluginError(MedReportError):
    """Raised when plugin discovery or execution fails."""
