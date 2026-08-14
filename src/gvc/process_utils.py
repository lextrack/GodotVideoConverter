from __future__ import annotations

import contextlib
import ctypes
import os
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


def external_subprocess_env() -> dict[str, str]:
    """Return an environment suitable for system programs started by the app.

    PyInstaller prepends its bundled library directory to LD_LIBRARY_PATH on
    Linux. That setting is needed by this application, but must not be passed
    to system programs such as ffmpeg and ffprobe: their system libraries can
    otherwise be replaced by incompatible bundled copies.
    """
    env = dict(os.environ)
    if sys.platform.startswith("linux") and getattr(sys, "frozen", False):
        original = env.get("LD_LIBRARY_PATH_ORIG")
        if original is None:
            env.pop("LD_LIBRARY_PATH", None)
        else:
            env["LD_LIBRARY_PATH"] = original
    return env


def attach_kill_on_close_job(process: subprocess.Popen) -> object | None:
    if sys.platform != "win32":
        return None

    kernel32 = ctypes.windll.kernel32

    class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_longlong),
            ("PerJobUserTimeLimit", ctypes.c_longlong),
            ("LimitFlags", ctypes.c_uint32),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", ctypes.c_uint32),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", ctypes.c_uint32),
            ("SchedulingClass", ctypes.c_uint32),
        ]

    class IO_COUNTERS(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_ulonglong),
            ("WriteOperationCount", ctypes.c_ulonglong),
            ("OtherOperationCount", ctypes.c_ulonglong),
            ("ReadTransferCount", ctypes.c_ulonglong),
            ("WriteTransferCount", ctypes.c_ulonglong),
            ("OtherTransferCount", ctypes.c_ulonglong),
        ]

    class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
            ("IoInfo", IO_COUNTERS),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        return None

    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
    JobObjectExtendedLimitInformation = 9
    info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
    info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE

    ok = kernel32.SetInformationJobObject(
        job,
        JobObjectExtendedLimitInformation,
        ctypes.byref(info),
        ctypes.sizeof(info),
    )
    if not ok:
        kernel32.CloseHandle(job)
        return None

    ok = kernel32.AssignProcessToJobObject(job, ctypes.c_void_p(process._handle))
    if not ok:
        kernel32.CloseHandle(job)
        return None

    return job


def close_windows_handle(handle: object | None) -> None:
    if sys.platform != "win32" or handle is None:
        return
    with contextlib.suppress(Exception):
        ctypes.windll.kernel32.CloseHandle(handle)


def stripped_metadata_args() -> list[str]:
    return ["-map_metadata", "-1", "-map_chapters", "-1"]


def temp_output_path(final_output: Path) -> Path:
    return final_output.with_name(f"{final_output.stem}.part{final_output.suffix}")


def cleanup_temp_output(path: Path) -> None:
    with contextlib.suppress(FileNotFoundError):
        path.unlink()
