from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from gvc.batch import next_available_output_path


class BatchPathTests(unittest.TestCase):
    def test_chooses_a_non_destructive_output_name(self) -> None:
        with TemporaryDirectory() as directory:
            output_dir = Path(directory)
            (output_dir / "clip_converted.ogv").touch()
            (output_dir / "clip_converted_1.ogv").touch()

            self.assertEqual(
                next_available_output_path(output_dir, "clip", "converted", ".ogv").name,
                "clip_converted_2.ogv",
            )
