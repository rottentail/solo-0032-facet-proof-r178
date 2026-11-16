"""Persistent commissioning journal for cross-run resumability.

The journal lives outside the service data root but references service object
ids inside it. It records, per catalog sample:

  * the catalog spec version and a hash of the exact sample definition,
  * the ids of the sealed assembly and seal (the frozen geometry),
  * the exposure id and its idempotency key, plus the terminal plate id,
  * the independent reader verdict and every exported artifact's checksum.

A second run never replaces a frozen seal: if the sample's stored seal hash no
longer matches the current catalog definition the sample is flagged as
"drifted" and left untouched, rather than silently rendering new geometry under
the same sample id.
"""
import hashlib
import json
from pathlib import Path

from .catalog import SPEC_VERSION

JOURNAL_NAME = "commission-journal.json"
INDEX_NAME = "resource-index.json"


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


def spec_hash(sample):
    """Hash of the full render definition for one catalog sample."""
    definition = {"spec_version": SPEC_VERSION, "sample": {
        "id": sample["id"], "title": sample["title"],
        "placements": sample["placements"], "lens": sample["lens"],
        "request": sample["request"],
    }}
    return hashlib.sha256(canonical(definition).encode("utf-8")).hexdigest()


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


class Store:
    def __init__(self, work_root):
        self.root = Path(work_root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.journal_path = self.root / JOURNAL_NAME
        self.index_path = self.root / INDEX_NAME

    # -- generic JSON load/save --------------------------------------------
    def _read(self, path, default):
        if not path.exists():
            return json.loads(json.dumps(default))
        return json.loads(path.read_text(encoding="utf-8"))

    def _write(self, path, value):
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                  indent=2) + "\n", encoding="utf-8")
        tmp.replace(path)

    # -- catalog-wide journal ----------------------------------------------
    def load_journal(self):
        journal = self._read(self.journal_path, {
            "spec_version": SPEC_VERSION, "samples": {}})
        journal.setdefault("spec_version", SPEC_VERSION)
        journal.setdefault("samples", {})
        return journal

    def save_journal(self, journal):
        self._write(self.journal_path, journal)

    def record(self, journal, sample_id, **fields):
        entry = journal["samples"].setdefault(sample_id, {})
        entry.update(fields)
        self.save_journal(journal)
        return entry

    # -- stable catalog key -> service id resource index -------------------
    def load_index(self):
        return self._read(self.index_path,
                          {"spec_version": SPEC_VERSION,
                           "meshes": {}, "pigments": {}})

    def save_index(self, index):
        self._write(self.index_path, index)
