"""为 VoxCaps 的 Tk 窗口统一设置品牌图标。"""

from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path
from typing import Any, Optional


def _icon_candidates(explicit_path: Optional[str | Path] = None):
    if explicit_path:
        yield Path(explicit_path)
    if getattr(sys, 'frozen', False):
        yield Path(sys.executable).resolve().parent / 'assets' / 'icon.ico'
    yield Path(__file__).resolve().parents[2] / 'assets' / 'icon.ico'
    yield Path.cwd() / 'assets' / 'icon.ico'


def apply_window_icon(window: Any, icon_path: Optional[str | Path] = None) -> bool:
    """设置窗口图标；缺失或当前平台不支持时静默回退。"""
    seen: set[Path] = set()
    for candidate in _icon_candidates(icon_path):
        candidate = candidate.resolve()
        if candidate in seen or not candidate.is_file():
            continue
        seen.add(candidate)
        try:
            window.iconbitmap(default=str(candidate))
            return True
        except (AttributeError, OSError, RuntimeError, tk.TclError):
            continue
    return False
