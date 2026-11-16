"""Export journaled, independently verified samples into the deliverable tree.

Only journal entries in state "complete" are exported. Every sample directory
receives the six channels (three raw semantic channels plus their PNG
previews), the offline bundle, the frozen seal and plate metadata, the
independent reader report, and a per-sample manifest tying them together with
checksums. A top-level dataset manifest lets a receiver cross-check the whole
collection without contacting the service.
"""
import json
import struct
from pathlib import Path

from . import catalog
from .store import sha256_bytes

CHANNELS = ("color.png", "depth.png", "object.png",
            "color.rgb", "depth.f32", "object.u32")


class Exporter:
    def __init__(self, commissioner, output_root):
        self.commissioner = commissioner
        self.client = commissioner.client
        self.journal = commissioner.journal
        self.output = Path(output_root)

    def export_all(self):
        self.output.mkdir(parents=True, exist_ok=True)
        records = []
        for sample in catalog.SAMPLES:
            entry = self.journal["samples"].get(sample["id"], {})
            if entry.get("state") != "complete":
                # Missing-channel, failed or duplicate-attempt results never
                # enter the delivered dataset.
                continue
            records.append(self._export_sample(sample, entry))

        manifest = {
            "spec_version": catalog.SPEC_VERSION,
            "sample_count": len(records),
            "coverage": self._coverage(records),
            "samples": records,
        }
        manifest_path = self.output / "dataset-manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2)
            + "\n", encoding="utf-8")
        return manifest

    def _export_sample(self, sample, entry):
        plate_id = entry["plate_id"]
        plate = self.client.get_plate(plate_id)
        seal = self.client.call("GET", f"seals/{entry['seal_id']}")
        bundle = self.client.bundle(plate_id)

        directory = self.output / sample["id"]
        channels_dir = directory / "channels"
        channels_dir.mkdir(parents=True, exist_ok=True)

        channel_checksums = {}
        for name in CHANNELS:
            data = self.client.read_pass(plate_id, name)
            (channels_dir / name).write_bytes(data)
            channel_checksums[name] = {
                "sha256": sha256_bytes(data), "size": len(data)}

        (directory / "plate-bundle.zip").write_bytes(bundle)
        (directory / "plate.json").write_text(
            json.dumps(plate, ensure_ascii=False, sort_keys=True, indent=2)
            + "\n", encoding="utf-8")
        (directory / "seal.json").write_text(
            json.dumps(seal, ensure_ascii=False, sort_keys=True, indent=2)
            + "\n", encoding="utf-8")

        from facetreader import validate_bundle
        reader_report = validate_bundle(bundle)
        (directory / "reader-report.json").write_text(
            json.dumps(reader_report, ensure_ascii=False, sort_keys=True,
                       indent=2, allow_nan=False) + "\n", encoding="utf-8")

        cross_check = self._cross_channel_check(sample, plate, directory)
        sample_manifest = {
            "id": sample["id"],
            "title": sample["title"],
            "spec_version": catalog.SPEC_VERSION,
            "spec_hash": entry["spec_hash"],
            "seal_id": entry["seal_id"],
            "seal_hash": entry["seal_hash"],
            "assembly_id": entry["assembly_id"],
            "assembly_revision": entry["assembly_revision"],
            "exposure_id": entry["exposure_id"],
            "exposure_key": entry["exposure_key"],
            "plate_id": plate_id,
            "visual_hash": entry["visual_hash"],
            "request": sample["request"],
            "lens": sample["lens"],
            "illumination": catalog.ILLUMINATION,
            "objects": plate["payload"]["objects"],
            "statistics": plate["payload"]["statistics"],
            "reader_summary": reader_report["summary"],
            "cross_channel_check": cross_check,
            "channels": channel_checksums,
            "bundle": {"file": "plate-bundle.zip",
                       "sha256": sha256_bytes(bundle), "size": len(bundle)},
        }
        (directory / "sample-manifest.json").write_text(
            json.dumps(sample_manifest, ensure_ascii=False, sort_keys=True,
                       indent=2) + "\n", encoding="utf-8")
        return {
            "id": sample["id"], "directory": sample["id"],
            "seal_hash": entry["seal_hash"], "spec_hash": entry["spec_hash"],
            "plate_id": plate_id, "exposure_key": entry["exposure_key"],
            "request": sample["request"],
            "projection": sample["lens"]["projection"],
            "cross_channel_check": cross_check,
        }

    def _cross_channel_check(self, sample, plate, directory):
        """Independent byte-level cross-check of the three raw channels.

        Re-derives coverage and depth bounds from the raw bytes and confirms
        every object id resolves to a placement in the frozen closure. This
        duplicates the receiver's checks using only the exported files, never
        the service's own verification functions.
        """
        width = plate["payload"]["width"]
        height = plate["payload"]["height"]
        objects = plate["payload"]["objects"]
        depth_raw = (directory / "channels" / "depth.f32").read_bytes()
        object_raw = (directory / "channels" / "object.u32").read_bytes()
        color_raw = (directory / "channels" / "color.rgb").read_bytes()

        assert len(depth_raw) == width * height * 4
        assert len(object_raw) == width * height * 4
        assert len(color_raw) == width * height * 3

        covered = 0
        background = 0
        min_depth = float("inf")
        max_depth = 0.0
        ids_seen = set()
        for offset in range(width * height):
            depth = struct.unpack_from("<f", depth_raw, offset * 4)[0]
            obj_id = struct.unpack_from("<I", object_raw, offset * 4)[0]
            if obj_id == 0:
                background += 1
                assert depth == float("inf"), "background depth must be +inf"
            else:
                assert str(obj_id) in objects, "unknown object id in pixels"
                assert depth > 0 and depth == depth, "foreground depth invalid"
                covered += 1
                ids_seen.add(obj_id)
                min_depth = min(min_depth, depth)
                max_depth = max(max_depth, depth)

        expected_placements = {p["key"] for p in sample["placements"]
                               if p["visible"]}
        mapped_placements = {meta["key"] for meta in objects.values()}
        assert mapped_placements == expected_placements, "object mapping drift"
        assert covered == plate["payload"]["statistics"]["covered_pixels"]

        return {
            "width": width, "height": height,
            "covered_pixels": covered, "background_pixels": background,
            "object_ids_seen": sorted(ids_seen),
            "objects_total": len(objects),
            "all_visible_placements_mapped": True,
            "finite_depth_range": [min_depth, max_depth] if covered else None,
            "background_depth": "positive_infinity",
            "depth_units": "camera_forward_distance",
            "byte_order": "little",
        }

    def _coverage(self, records):
        return {
            "projections": sorted({r["projection"] for r in records}),
            "sampling": sorted({r["request"]["samples"] for r in records}),
            "dimensions": sorted({(r["request"]["width"], r["request"]["height"])
                                  for r in records}),
            "exposure_keys": [r["exposure_key"] for r in records],
            "seal_hashes": sorted({r["seal_hash"] for r in records}),
        }
