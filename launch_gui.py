#!/usr/bin/env python3
"""Launch GDI Desktop GUI.

Usage:
    python launch_gui.py
"""

import sys
from pathlib import Path

# Add gdi_core to path
sys.path.insert(0, str(Path(__file__).parent))

# Launch GUI
from gdi_app.gui.main_window import main

if __name__ == "__main__":
    main()
