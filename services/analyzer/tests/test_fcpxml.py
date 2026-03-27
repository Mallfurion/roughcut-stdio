from __future__ import annotations

from pathlib import Path
import unittest
from xml.etree import ElementTree as ET

from services.analyzer.app.fcpxml import export_fcpxml, parse_fcpxml_timeline
from services.analyzer.app.service import CLEAR_BEST_TAKE_SENTINEL, export_project_fcpxml, load_project


ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "fixtures" / "sample-project.json"


class FCPXMLExportTests(unittest.TestCase):
    def test_export_includes_clip_order_and_source_paths(self) -> None:
        xml_payload = export_project_fcpxml(FIXTURE)
        root = ET.fromstring(xml_payload.split("\n", 2)[2])

        assets = root.findall("./resources/asset")
        clips = root.findall("./library/event/project/sequence/spine/asset-clip")

        self.assertEqual(len(assets), 3)
        self.assertEqual(len(clips), 3)
        self.assertEqual(clips[0].attrib["name"], "City opener")
        self.assertEqual(clips[1].attrib["name"], "Narrative turn")
        self.assertEqual(clips[2].attrib["name"], "Evening outro")
        self.assertTrue(assets[0].attrib["src"].startswith("file:///Volumes/Shoot/Bucharest/Originals/"))

    def test_export_duration_matches_trimmed_timeline(self) -> None:
        xml_payload = export_project_fcpxml(FIXTURE)
        root = ET.fromstring(xml_payload.split("\n", 2)[2])

        sequence = root.find("./library/event/project/sequence")
        clips = root.findall("./library/event/project/sequence/spine/asset-clip")

        self.assertIsNotNone(sequence)
        self.assertEqual(sequence.attrib["duration"], "29/2s")
        self.assertEqual(clips[0].attrib["duration"], "5/1s")
        self.assertEqual(clips[1].attrib["duration"], "11/2s")
        self.assertEqual(clips[2].attrib["duration"], "4/1s")

    def test_round_trip_summary_preserves_order_and_trim_logic(self) -> None:
        project = load_project(FIXTURE)
        xml_payload = export_project_fcpxml(FIXTURE)
        clip_summaries = parse_fcpxml_timeline(xml_payload)

        self.assertEqual([clip.name for clip in clip_summaries], ["City opener", "Narrative turn", "Evening outro"])
        self.assertEqual([clip.asset_uid for clip in clip_summaries], ["A001_C001_0324AB", "A002_C014_0324CD", "A003_C007_0324EF"])
        self.assertAlmostEqual(clip_summaries[0].offset_sec, 0.0)
        self.assertAlmostEqual(clip_summaries[1].offset_sec, 5.0)
        self.assertAlmostEqual(clip_summaries[2].offset_sec, 10.5)

        timeline_durations = [item.trim_out_sec - item.trim_in_sec for item in project.timeline.items]
        export_durations = [clip.duration_sec for clip in clip_summaries]
        self.assertEqual([round(value, 3) for value in timeline_durations], [round(value, 3) for value in export_durations])
        self.assertAlmostEqual(clip_summaries[0].start_sec, 1.5)
        self.assertAlmostEqual(clip_summaries[1].start_sec, 10.75)
        self.assertAlmostEqual(clip_summaries[2].start_sec, 5.5)

    def test_clip_start_uses_asset_source_timecode_when_present(self) -> None:
        project = load_project(FIXTURE)
        project.assets[0].source_timecode = "15:22:18:00"

        xml_payload = export_fcpxml(project)
        clip_summaries = parse_fcpxml_timeline(xml_payload)

        self.assertAlmostEqual(clip_summaries[0].start_sec, (15 * 3600) + (22 * 60) + 18 + 1.5)

    def test_export_is_unchanged_when_review_provenance_is_present(self) -> None:
        project = load_project(FIXTURE)
        baseline_xml = export_fcpxml(project)
        baseline_summaries = parse_fcpxml_timeline(baseline_xml)

        first_segment = project.candidate_segments[0]
        if first_segment.review_state is not None:
            first_segment.review_state.boundary_strategy_label = "Transcript snapped"
            first_segment.review_state.boundary_confidence = 0.87
            first_segment.review_state.lineage_summary = "Built from 1 seed region (transcript)."
            first_segment.review_state.semantic_validation_status = "validated"
            first_segment.review_state.semantic_validation_summary = "Semantic validation kept the deterministic boundary at 87% confidence."

        xml_with_provenance = export_fcpxml(project)
        summaries_with_provenance = parse_fcpxml_timeline(xml_with_provenance)

        self.assertEqual(
            [(clip.name, clip.asset_uid, round(clip.offset_sec, 3), round(clip.start_sec, 3), round(clip.duration_sec, 3)) for clip in baseline_summaries],
            [(clip.name, clip.asset_uid, round(clip.offset_sec, 3), round(clip.start_sec, 3), round(clip.duration_sec, 3)) for clip in summaries_with_provenance],
        )

    def test_export_respects_best_take_overrides(self) -> None:
        override = {"asset-review": "segment-clip-gated"}
        fixture = ROOT / "fixtures" / "review-states-project.json"

        project = load_project(fixture, best_take_overrides=override)
        xml_payload = export_project_fcpxml(fixture, best_take_overrides=override)
        clip_summaries = parse_fcpxml_timeline(xml_payload)

        self.assertEqual(len(clip_summaries), len(project.timeline.items))
        self.assertEqual(len(clip_summaries), 1)
        self.assertAlmostEqual(
            clip_summaries[0].duration_sec,
            project.timeline.items[0].trim_out_sec - project.timeline.items[0].trim_in_sec,
        )

    def test_export_omits_asset_when_best_take_is_cleared(self) -> None:
        override = {"asset-review": CLEAR_BEST_TAKE_SENTINEL}
        fixture = ROOT / "fixtures" / "review-states-project.json"

        project = load_project(fixture, best_take_overrides=override)
        xml_payload = export_project_fcpxml(fixture, best_take_overrides=override)
        clip_summaries = parse_fcpxml_timeline(xml_payload)

        self.assertEqual(len(project.timeline.items), 0)
        self.assertEqual(len(clip_summaries), 0)


if __name__ == "__main__":
    unittest.main()
