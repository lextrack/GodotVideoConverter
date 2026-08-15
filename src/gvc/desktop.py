from __future__ import annotations

import sys
import os
from pathlib import Path
from shutil import which
from subprocess import Popen

from gvc.process_utils import external_subprocess_env


def _linux_file_manager() -> str | None:
    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").casefold()
    candidates = (
        ("cinnamon", "nemo"),
        ("mate", "caja"),
        ("kde", "dolphin"),
        ("plasma", "dolphin"),
        ("xfce", "thunar"),
        ("lxqt", "pcmanfm-qt"),
        ("lxde", "pcmanfm"),
        ("gnome", "nautilus"),
        ("unity", "nautilus"),
        ("budgie", "nautilus"),
        ("pantheon", "nautilus"),
    )
    for name, command in candidates:
        if name in desktop and which(command):
            return command
    return None


def open_directory(path: Path) -> bool:
    """Open *path* with the desktop's file manager when possible."""
    resolved_path = str(path.resolve())

    # Qt can route local URLs through the browser on Linux, particularly from
    # self-contained builds where desktop integration is incomplete. Prefer
    # the file manager for the active desktop, then defer to the GLib launcher.
    if sys.platform.startswith("linux"):
        try:
            command = _linux_file_manager() or "gio"
            args = [command, resolved_path] if command != "gio" else [command, "open", resolved_path]
            Popen(args, env=external_subprocess_env())
            return True
        except OSError:
            pass

    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QDesktopServices
    return QDesktopServices.openUrl(QUrl.fromLocalFile(resolved_path))
