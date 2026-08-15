from __future__ import annotations

from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from gvc.desktop import open_directory


class OpenDirectoryTests(TestCase):
    @patch("gvc.desktop.sys.platform", "linux")
    @patch("gvc.desktop._linux_file_manager", return_value="nautilus")
    @patch("gvc.desktop.Popen")
    @patch("gvc.desktop.external_subprocess_env", return_value={"PATH": "/bin"})
    def test_uses_desktop_file_manager_on_linux(self, environment, popen, file_manager) -> None:
        path = Path("output")

        self.assertTrue(open_directory(path))

        file_manager.assert_called_once_with()
        popen.assert_called_once_with(["nautilus", str(path.resolve())], env={"PATH": "/bin"})

    @patch("gvc.desktop.sys.platform", "linux")
    @patch("gvc.desktop._linux_file_manager", return_value=None)
    @patch("gvc.desktop.Popen")
    def test_falls_back_to_gio_when_no_known_file_manager_is_available(self, popen, _file_manager) -> None:
        self.assertTrue(open_directory(Path("output")))

        popen.assert_called_once()
        self.assertEqual(popen.call_args.args[0][:2], ["gio", "open"])
