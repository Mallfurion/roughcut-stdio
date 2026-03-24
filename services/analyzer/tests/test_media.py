from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from services.analyzer.app.media import (
    DiscoveredMedia,
    MediaProbe,
    build_assets_from_matches,
    classify_media_role,
    datetime_to_timecode,
    discover_media_files,
    match_media_files,
    normalized_clip_key,
    select_exiftool_timecode,
)


class FakeProbeRunner:
    def __init__(self, responses: dict[str, MediaProbe]) -> None:
        self.responses = responses

    def probe(self, media_path: str | Path) -> MediaProbe:
        return self.responses[str(Path(media_path).resolve())]


class MediaDiscoveryTests(unittest.TestCase):
    def test_classifies_proxy_by_folder_and_filename(self) -> None:
        self.assertEqual(classify_media_role("/tmp/Proxy/A001_C001.mov"), "proxy")
        self.assertEqual(classify_media_role("/tmp/A001_C001_proxy.mov"), "proxy")
        self.assertEqual(classify_media_role("/tmp/Originals/A001_C001.mov"), "source")

    def test_normalized_clip_key_removes_proxy_markers(self) -> None:
        self.assertEqual(normalized_clip_key("A001_C001_proxy"), normalized_clip_key("A001_C001"))

    def test_discovers_and_matches_source_and_proxy(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            originals = root / "Originals"
            proxies = root / "Proxy"
            originals.mkdir()
            proxies.mkdir()

            source = originals / "A001_C001_0324AB.mov"
            proxy = proxies / "A001_C001_0324AB.mov"
            source.touch()
            proxy.touch()

            probe_runner = FakeProbeRunner(
                {
                    str(source.resolve()): MediaProbe(10.0, 24.0, 1920, 1080, True, "01:00:00:00"),
                    str(proxy.resolve()): MediaProbe(10.0, 24.0, 1280, 720, True, "01:00:00:00"),
                }
            )

            discovered = discover_media_files([root], probe_runner=probe_runner)
            matches = match_media_files(discovered)
            assets = build_assets_from_matches(matches)

            self.assertEqual(len(discovered), 2)
            self.assertEqual(len(matches), 1)
            self.assertEqual(matches[0].proxy.path, str(proxy.resolve()))
            self.assertGreaterEqual(matches[0].confidence, 0.85)
            self.assertEqual(len(assets), 1)
            self.assertEqual(assets[0].proxy_path, str(proxy.resolve()))
            self.assertEqual(assets[0].source_timecode, "01:00:00:00")
            self.assertTrue(assets[0].has_proxy)

    def test_proxy_only_file_is_usable_placeholder(self) -> None:
        proxy = DiscoveredMedia(
            path="/tmp/Proxy/B001_C002.mov",
            role="proxy",
            clip_key="B001C002",
            stem="B001_C002",
            extension=".mov",
            probe=MediaProbe(8.0, 24.0, 1280, 720, False, None),
        )

        matches = match_media_files([proxy])
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].proxy.path, proxy.path)
        self.assertGreater(matches[0].confidence, 0.4)

    def test_source_only_clip_is_supported_without_proxy(self) -> None:
        source = DiscoveredMedia(
            path="/tmp/DJI_0692.MP4",
            role="source",
            clip_key="DJI0692",
            stem="DJI_0692",
            extension=".mp4",
            probe=MediaProbe(28.97, 59.94, 1920, 1080, False, "06:50:32:00"),
        )

        matches = match_media_files([source])
        assets = build_assets_from_matches(matches)

        self.assertEqual(len(matches), 1)
        self.assertIsNone(matches[0].proxy)
        self.assertEqual(matches[0].confidence, 1.0)
        self.assertIn("Source-only processing", matches[0].reason)
        self.assertEqual(len(assets), 1)
        self.assertFalse(assets[0].has_proxy)
        self.assertEqual(assets[0].proxy_path, source.path)

    def test_datetime_metadata_can_be_used_as_timecode(self) -> None:
        self.assertEqual(datetime_to_timecode("2025-08-10T15:22:18+0300"), "15:22:18:00")
        self.assertEqual(datetime_to_timecode("2025:08:10 12:22:18"), "12:22:18:00")

    def test_select_exiftool_timecode_ignores_generic_create_date(self) -> None:
        payload = {
            "CreateDate": "2025:08:11 06:57:32",
            "TimeCode": 0,
        }

        self.assertIsNone(select_exiftool_timecode(payload))

    def test_select_exiftool_timecode_uses_blackmagic_recorded_date(self) -> None:
        payload = {
            "Blackmagic-designCameraDateRecorded": "2025-08-10T15:22:18+0300",
        }

        self.assertEqual(select_exiftool_timecode(payload), "15:22:18:00")


if __name__ == "__main__":
    unittest.main()
