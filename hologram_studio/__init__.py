"""Holograms for objects, buildings and entities: declarative scenes compiled to deterministic,
audited geometry and an animated WebGL preview (see ../README.md). Also the v0.1 construction
sheets below.

Public API:
    validate(sheet) -> list[str]
    compile_sheet(sheet) -> dict
    template(kind, title=None) -> dict
    read_sheet(path) -> dict
"""

from .hologram import (
    validate,
    compile_sheet,
    template,
    read_sheet,
    SheetError,
)

__all__ = [
    "validate",
    "compile_sheet",
    "template",
    "read_sheet",
    "SheetError",
]

from .product import VERSION as __version__  # noqa: E402
