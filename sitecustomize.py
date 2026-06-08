"""Process-wide Python startup tweaks for local Windows runs.

Python imports this module automatically when the project root is on
``sys.path``. Several agents print status glyphs during import; on Windows
terminals using cp1252 those writes can raise ``UnicodeEncodeError`` before
the pipeline even starts. Force UTF-8 text streams when possible.
"""

from __future__ import annotations

import os
import sys

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ.setdefault("PYTHONUTF8", "1")

for _stream_name in ("stdout", "stderr"):
    _stream = getattr(sys, _stream_name, None)
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
