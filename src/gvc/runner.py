from __future__ import annotations

import re
import queue
import subprocess
import time
import threading
from threading import Event
from typing import Callable

from gvc.process_utils import hidden_subprocess_kwargs

TIME_RE = re.compile(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)")


class FFmpegRunError(RuntimeError):
    pass


ProgressCallback = Callable[[int], None]
StatusCallback = Callable[[str], None]

def run_ffmpeg(
    ffmpeg_path: str,
    args: list[str],
    total_seconds: float | None = None,
    on_progress: ProgressCallback | None = None,
    on_status: StatusCallback | None = None,
    cancel_event: Event | None = None,
) -> None:
    cmd = [ffmpeg_path, *args]
    if on_status:
        on_status("ffmpeg_launch")
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        **hidden_subprocess_kwargs(),
    )

    if process.stderr is None:
        raise FFmpegRunError("Failed to capture FFmpeg stderr")

    line_queue: queue.Queue[str | None] = queue.Queue()

    def _read_stderr() -> None:
        assert process.stderr is not None
        try:
            for raw_line in process.stderr:
                line_queue.put(raw_line)
        finally:
            line_queue.put(None)

    reader = threading.Thread(target=_read_stderr, name="ffmpeg-stderr-reader", daemon=True)
    reader.start()

    last_progress = 0
    errors: list[str] = []
    started_at = time.monotonic()
    announced_warmup = False

    reader_finished = False
    while True:
        if cancel_event and cancel_event.is_set():
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)
            reader.join(timeout=1)
            raise FFmpegRunError("FFmpeg run cancelled by user")

        if on_status and not announced_warmup and last_progress == 0 and time.monotonic() - started_at >= 2.0:
            announced_warmup = True
            on_status("ffmpeg_warmup")

        try:
            line = line_queue.get(timeout=0.2)
        except queue.Empty:
            if process.poll() is not None and reader_finished:
                break
            continue

        if line is None:
            reader_finished = True
            if process.poll() is not None:
                break
            continue

        if "Error" in line or "Invalid" in line or "No such" in line or "Permission denied" in line:
            errors.append(line.strip())

        match = TIME_RE.search(line)
        if match and total_seconds and total_seconds > 0:
            if on_status and last_progress == 0:
                on_status("ffmpeg_encoding")
            h = float(match.group(1))
            m = float(match.group(2))
            s = float(match.group(3))
            current = h * 3600 + m * 60 + s
            percent = int(min((current / total_seconds) * 100, 100))
            if percent > last_progress:
                last_progress = percent
                if on_progress:
                    on_progress(percent)

    if cancel_event and cancel_event.is_set():
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)
        reader.join(timeout=1)
        raise FFmpegRunError("FFmpeg run cancelled by user")

    process.wait()
    reader.join(timeout=1)
    if process.returncode != 0:
        detail = "; ".join(errors[:5]) if errors else f"Exit code {process.returncode}"
        raise FFmpegRunError(f"FFmpeg failed: {detail}")

    if on_progress:
        on_progress(100)
