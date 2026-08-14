from __future__ import annotations

from types import SimpleNamespace
import subprocess
import unittest
from unittest.mock import patch

from gvc.media_probe import FFPROBE_TIMEOUT_SECONDS, probe_media_json


class MediaProbeTests(unittest.TestCase):
    @patch("gvc.media_probe.subprocess.run")
    def test_returns_json_data_and_uses_a_timeout(self, run) -> None:
        run.return_value = SimpleNamespace(
            returncode=0,
            stdout='{"format": {"duration": "1.5"}, "streams": []}',
        )

        result = probe_media_json("ffprobe", "clip.mp4")

        self.assertEqual(result, {"format": {"duration": "1.5"}, "streams": []})
        self.assertEqual(run.call_args.kwargs["timeout"], FFPROBE_TIMEOUT_SECONDS)

    @patch("gvc.media_probe.subprocess.run")
    def test_timeout_is_treated_as_an_unreadable_file(self, run) -> None:
        run.side_effect = subprocess.TimeoutExpired(["ffprobe"], FFPROBE_TIMEOUT_SECONDS)

        self.assertIsNone(probe_media_json("ffprobe", "problematic.mp4"))

    @patch("gvc.media_probe.subprocess.run")
    def test_invalid_json_is_treated_as_an_unreadable_file(self, run) -> None:
        run.return_value = SimpleNamespace(returncode=0, stdout="not json")

        self.assertIsNone(probe_media_json("ffprobe", "broken.mp4"))
