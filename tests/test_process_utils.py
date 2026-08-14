from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from gvc.process_utils import external_subprocess_env


class ExternalSubprocessEnvironmentTests(unittest.TestCase):
    @patch("gvc.process_utils.sys.frozen", True, create=True)
    @patch("gvc.process_utils.sys.platform", "linux")
    def test_restores_original_library_path_for_system_programs(self) -> None:
        with patch.dict(
            os.environ,
            {
                "LD_LIBRARY_PATH": "/tmp/pyinstaller",
                "LD_LIBRARY_PATH_ORIG": "/usr/local/lib",
            },
            clear=True,
        ):
            self.assertEqual(
                external_subprocess_env()["LD_LIBRARY_PATH"], "/usr/local/lib"
            )

    @patch("gvc.process_utils.sys.frozen", True, create=True)
    @patch("gvc.process_utils.sys.platform", "linux")
    def test_removes_pyinstaller_library_path_when_no_original_exists(self) -> None:
        with patch.dict(
            os.environ, {"LD_LIBRARY_PATH": "/tmp/pyinstaller"}, clear=True
        ):
            self.assertNotIn("LD_LIBRARY_PATH", external_subprocess_env())

    @patch("gvc.process_utils.sys.platform", "win32")
    def test_does_not_modify_library_path_on_non_linux_systems(self) -> None:
        with patch.dict(
            os.environ, {"LD_LIBRARY_PATH": "/tmp/pyinstaller"}, clear=True
        ):
            self.assertEqual(
                external_subprocess_env()["LD_LIBRARY_PATH"], "/tmp/pyinstaller"
            )

    @patch("gvc.process_utils.sys.platform", "linux")
    def test_does_not_modify_library_path_outside_a_bundle(self) -> None:
        with patch.dict(
            os.environ, {"LD_LIBRARY_PATH": "/custom/lib"}, clear=True
        ):
            self.assertEqual(
                external_subprocess_env()["LD_LIBRARY_PATH"], "/custom/lib"
            )
