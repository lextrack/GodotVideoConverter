from __future__ import annotations

import unittest

from gvc.convert import (
    ENGINE_PROFILE_GODOT,
    ENGINE_PROFILE_LOVE2D,
    _parse_resolution,
    _video_codec_args,
    normalize_engine_profile,
    validate_resolution,
)


class ConvertConfigurationTests(unittest.TestCase):
    def test_love_profile_and_preset_normalize_correctly(self) -> None:
        self.assertEqual(normalize_engine_profile("LÖVE"), ENGINE_PROFILE_LOVE2D)
        video, audio, extra = _video_codec_args(
            "ogv", "optimized", "LÖVE Compatibility", "LÖVE"
        )

        self.assertIn("libtheora", video)
        self.assertIn("libvorbis", audio)
        self.assertEqual(extra, ["-pix_fmt", "yuv420p", "-g", "24", "-keyint_min", "12", "-fps_mode", "cfr"])

    def test_unknown_profile_falls_back_to_godot(self) -> None:
        self.assertEqual(normalize_engine_profile("unknown"), ENGINE_PROFILE_GODOT)

    def test_resolution_validation(self) -> None:
        self.assertEqual(_parse_resolution("1280x720"), (1280, 720))
        validate_resolution("Keep original")
        with self.assertRaises(ValueError):
            validate_resolution("1280-by-720")
