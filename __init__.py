"""Tessera hologram: declarative construction sheets compiled to deterministic geometry.

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

__version__ = "0.1.0"
