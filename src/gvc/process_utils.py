from __future__ import annotations

import contextlib
import subprocess
import sys
from pathlib import Path


def hidden_subprocess_kwargs() -> dict[str, object]:
    if sys.platform != "win32":
        return {}
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    return {
        "creationflags": subprocess.CREATE_NO_WINDOW,
        "startupinfo": startupinfo,
    }


def temp_output_path(final_output: Path) -> Path:
    return final_output.with_name(f"{final_output.stem}.part{final_output.suffix}")


def cleanup_temp_output(path: Path) -> None:
    with contextlib.suppress(FileNotFoundError):
        path.unlink()
