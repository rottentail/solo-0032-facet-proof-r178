"""Commission catalog samples against one persistent Facet Proof data root.

The commissioner is idempotent and resumable:

  * mesh/pigment resources are created once per data root and remembered in a
    catalog-key index, so later runs reuse the exact same service objects;
  * each sample is sealed once. The journal stores the seal content hash and
    the catalog spec hash. A later catalog edit changes the spec hash, so the
    old sample is marked "drifted" and its frozen geometry is never replaced;
  * exposure submission uses a fixed idempotency key per sample, and the
    service itself rejects a key that names a different request;
  * worker runs consume queued exposures one at a time. Expired leases from a
    crashed process are recovered first, and the tile engine reuses every
    already committed 64x64 tile under the same render definition;
  * only plates whose six channels exist, verify server-side and pass the
    independent facetreader are recorded as complete in the journal.
"""
from . import catalog
from .client import Client
from .store import Store, spec_hash, sha256_bytes
from facetproof.errors import Fault


class Commissioner:
    def __init__(self, work_root):
        self.store = Store(work_root)
        self.client = Client(work_root)
        self.journal = self.store.load_journal()
        self.index = self.store.load_index()

    # ------------------------------------------------------------------
    # Resource intake (stable catalog keys -> service ids, created once)
    # ------------------------------------------------------------------
    def ensure_resources(self):
        changed = False
        for mesh_key, definition in catalog.MESHES.items():
            if mesh_key not in self.index["meshes"]:
                mesh = self.client.create_mesh(definition)
                self.index["meshes"][mesh_key] = mesh["id"]
                changed = True
        for pigment_key, definition in catalog.PIGMENTS.items():
            if pigment_key not in self.index["pigments"]:
                pigment = self.client.create_pigment(definition)
                self.index["pigments"][pigment_key] = pigment["id"]
                changed = True
        if changed:
            self.store.save_index(self.index)

    def mesh_id(self, key):
        return self.index["meshes"][key]

    def pigment_id(self, key):
        return self.index["pigments"][key]

    # ------------------------------------------------------------------
    # Per-sample seal, created once and then immutable
    # ------------------------------------------------------------------
    def ensure_seal(self, sample):
        entry = self.journal["samples"].get(sample["id"], {})
        current_hash = spec_hash(sample)
        if entry.get("seal_id"):
            # Frozen geometry from an earlier run: prove it is the same spec.
            if entry.get("spec_hash") != current_hash:
                if entry.get("state") != "drifted":
                    self.store.record(self.journal, sample["id"], state="drifted")
                return None, "drifted"
            seal = self.client.call("GET", f"seals/{entry['seal_id']}")
            if seal["payload"]["content_hash"] != entry["seal_hash"]:
                raise Fault("seal_hash", "Stored seal hash disagrees with service")
            # A previously flagged drift is moot once the spec matches again;
            # the frozen seal id and hash remain exactly the original ones.
            if entry.get("state") == "drifted":
                self.store.record(self.journal, sample["id"], state="sealed")
            return seal, "reused"

        assembly = self.client.create_assembly({"name": sample["title"]})
        placements = [{
            "key": p["key"],
            "mesh_id": self.mesh_id(p["mesh"]),
            "pigment_id": self.pigment_id(p["pigment"]),
            "transform": p["transform"],
            "visible": p["visible"],
        } for p in sample["placements"]]
        self.client.revise_assembly(
            assembly["id"], 1,
            name=sample["title"], placements=placements,
            lens=sample["lens"], illumination=catalog.ILLUMINATION)
        seal = self.client.seal(assembly["id"], 2)
        self.store.record(
            self.journal, sample["id"],
            state="sealed", spec_hash=current_hash,
            assembly_id=assembly["id"], assembly_revision=2,
            seal_id=seal["id"], seal_hash=seal["payload"]["content_hash"],
            request=sample["request"], exposure_key="sample-" + sample["id"])
        return seal, "created"

    # ------------------------------------------------------------------
    # Exposure submission, keyed and therefore duplicate-safe
    # ------------------------------------------------------------------
    def ensure_exposure(self, sample, seal):
        entry = self.journal["samples"][sample["id"]]
        key = "sample-" + sample["id"]
        exposure = self.client.submit_exposure(seal["id"], key, sample["request"])
        if entry.get("exposure_id") != exposure["id"]:
            self.store.record(self.journal, sample["id"],
                              exposure_id=exposure["id"])
        return exposure

    def sample_state(self, sample_id):
        return self.journal["samples"].get(sample_id, {}).get("state")

    # ------------------------------------------------------------------
    # Crash recovery: expired leases go back to the queue, tiles persist
    # ------------------------------------------------------------------
    def recover_expired(self):
        return self.client.recover()

    def run_worker(self):
        return self.client.worker_step()

    # ------------------------------------------------------------------
    # Completion gate: six channels, server verify, independent reader
    # ------------------------------------------------------------------
    def accept_if_complete(self, sample, exposure):
        sample_id = sample["id"]
        if exposure["state"] != "succeeded":
            self.store.record(self.journal, sample_id, state=exposure["state"])
            return False
        plate = self.client.get_plate(exposure["plate_id"])
        if plate["state"] != "ready":
            self.store.record(self.journal, sample_id, state="plate_" + plate["state"])
            return False

        payload = plate["payload"]
        expected_channels = {"color.rgb", "depth.f32", "object.u32",
                             "color.png", "depth.png", "object.png"}
        if set(payload["passes"]) != expected_channels:
            # A missing-channel result is never allowed into the dataset.
            self.store.record(self.journal, sample_id, state="incomplete_channels")
            return False

        verification = self.client.verify_plate(plate["id"])
        if not verification["valid"]:
            self.store.record(self.journal, sample_id, state="verify_failed")
            return False

        bundle = self.client.bundle(plate["id"])
        from facetreader import validate_bundle
        reader_report = validate_bundle(bundle)
        if not reader_report["valid"]:
            self.store.record(self.journal, sample_id,
                              state="reader_rejected", reader_error=reader_report.get("error"))
            return False

        self.store.record(
            self.journal, sample_id,
            state="complete", plate_id=plate["id"],
            exposure_id=exposure["id"],
            bundle_sha256=sha256_bytes(bundle),
            reader_summary=reader_report["summary"],
            statistics=payload["statistics"],
            visual_hash=payload["visual_hash"])
        return True
