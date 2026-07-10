# Architecture

MedReport uses Clean Architecture to protect medical imaging workflows from UI and
infrastructure churn.

```mermaid
flowchart TD
    UI["Presentation: PySide6 widgets"]
    APP["Application: use cases and services"]
    DOMAIN["Domain: studies, series, images, volumes"]
    INFRA["Infrastructure: pydicom, SimpleITK, SQLite, plugins"]
    UI --> APP
    APP --> DOMAIN
    INFRA --> APP
```

The presentation layer never manipulates DICOM files directly. It invokes application
services, which depend on repository protocols. Infrastructure adapters implement those
protocols with pydicom and SimpleITK.
