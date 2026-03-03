"""GDI App - Desktop Application Layer.

This module provides desktop interfaces (CLI and GUI) for GDI.
The core business logic lives in gdi_core.
"""

__version__ = "1.0.0"

from .cli import app as cli_app

__all__ = ["cli_app"]
