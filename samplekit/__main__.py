"""Command line entry point for the sample commissioning kit.

Subcommands:
  build    Create/seal catalog samples and render their plates, resuming any
           work already present in the persistent data root.
  export   Materialize every complete sample into a receiver-ready dataset.
  audit    Re-verify an exported dataset purely from its on-disk files and the
           independent facetreader, with no service connection.

Run with isolated Python (the entry point bootstraps sys.path itself):
  python3 -I -m samplekit --repo /workspace build --root ./sample-work ...
"""
import argparse
import json
import sys
from pathlib import Path

# Allow "python3 -I" execution without an installed package.
REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from samplekit import catalog  # noqa: E402
from samplekit.commissioner import Commissioner  # noqa: E402
from samplekit.exporter import Exporter  # noqa: E402
from samplekit.store import sha256_bytes  # noqa: E402
from facetproof.errors import Fault  # noqa: E402


def _build(args):
    commissioner = Commissioner(args.root)
    commissioner.ensure_resources()
    selected = [s for s in catalog.SAMPLES
                if not args.only or s["id"] in set(args.only)]

    # First recover anything a crashed process left running. Recovery never
    # changes the render definition; committed tiles stay reusable.
    recovered = commissioner.recover_expired()

    actions = []
    rendered = []
    for sample in selected:
        entry = commissioner.journal["samples"].get(sample["id"], {})
        if entry.get("state") == "complete":
            actions.append({"id": sample["id"], "action": "already_complete"})
            continue

        seal, seal_action = commissioner.ensure_seal(sample)
        if seal_action == "drifted":
            actions.append({"id": sample["id"], "action": "drifted_frozen_kept"})
            continue
        exposure = commissioner.ensure_exposure(sample, seal)
        actions.append({"id": sample["id"], "action": "commissioned",
                        "seal": seal_action, "exposure": exposure["id"],
                        "state": exposure["state"]})
        # A previous process may already have rendered this exposure: reconcile
        # its plate through the same completeness gate instead of waiting for a
        # worker run that will never claim finished work.
        if exposure["state"] == "succeeded" and commissioner.sample_state(sample["id"]) != "complete":
            accepted = commissioner.accept_if_complete(sample, exposure)
            rendered.append({"exposure": exposure["id"],
                             "result": "accepted" if accepted else "not_accepted"})

    # Drive the worker until this invocation's budget is spent or the queue
    # drains. The same call on a later process resumes via persisted tiles.
    steps = 0
    while steps < args.max_steps:
        result = commissioner.run_worker()
        steps += 1
        if result["state"] == "idle":
            break
        exposure_id = result.get("exposure_id")
        if result["state"] == "succeeded":
            sample = next((s for s in selected
                           if commissioner.journal["samples"].get(s["id"], {})
                           .get("exposure_id") == exposure_id), None)
            exposure = commissioner.client.get_exposure(exposure_id)
            accepted = (commissioner.accept_if_complete(sample, exposure)
                        if sample else False)
            rendered.append({"exposure": exposure_id,
                             "result": "accepted" if accepted else "not_accepted"})
        else:
            rendered.append({"exposure": exposure_id, "state": result["state"],
                             "error": result.get("error")})

    # Report the current state of every selected sample, including queued work
    # that a future run must continue.
    statuses = []
    for sample in selected:
        entry = commissioner.journal["samples"].get(sample["id"], {})
        status = {"id": sample["id"], "state": entry.get("state", "missing")}
        if entry.get("exposure_id"):
            status["progress"] = commissioner.client.progress(
                entry["exposure_id"])
        statuses.append(status)
    return {"recovered": recovered, "actions": actions,
            "worker_runs": rendered, "statuses": statuses,
            "resources": commissioner.client.resource_snapshot()}


def _export(args):
    commissioner = Commissioner(args.root)
    manifest = Exporter(commissioner, args.output).export_all()
    return {"output": str(Path(args.output).resolve()),
            "sample_count": manifest["sample_count"],
            "coverage": manifest["coverage"]}


def _audit(args):
    """Independent receiver-side audit of an exported dataset."""
    from facetreader import inspect_bundle
    dataset_root = Path(args.dataset)
    manifest = json.loads((dataset_root / "dataset-manifest.json").read_text(
        encoding="utf-8"))
    results = []
    for record in manifest["samples"]:
        directory = dataset_root / record["directory"]
        bundle_path = directory / "plate-bundle.zip"
        reader = inspect_bundle(str(bundle_path))
        if not reader["valid"]:
            results.append({"id": record["id"], "valid": False,
                            "error": reader.get("error")})
            continue

        sample_manifest = json.loads(
            (directory / "sample-manifest.json").read_text(encoding="utf-8"))
        # Re-hash every exported channel and the bundle from disk.
        channel_mismatch = []
        for name, descriptor in sample_manifest["channels"].items():
            data = (directory / "channels" / name).read_bytes()
            if sha256_bytes(data) != descriptor["sha256"] or len(data) != descriptor["size"]:
                channel_mismatch.append(name)
        bundle_bytes = bundle_path.read_bytes()
        bundle_ok = (sha256_bytes(bundle_bytes)
                     == sample_manifest["bundle"]["sha256"])
        # The reader's provenance must name the same frozen seal.
        provenance = reader["provenance"]
        seal_ok = provenance["seal_hash"] == record["seal_hash"]
        valid = not channel_mismatch and bundle_ok and seal_ok
        results.append({
            "id": record["id"], "valid": valid,
            "reader_valid": reader["valid"],
            "bundle_hash_ok": bundle_ok, "seal_hash_ok": seal_ok,
            "channel_mismatch": channel_mismatch,
            "summary": reader["summary"],
            "cross_channel_check": sample_manifest["cross_channel_check"],
        })
    all_valid = all(item["valid"] for item in results)
    return {"dataset": str(dataset_root.resolve()),
            "expected_samples": manifest["sample_count"],
            "audited": len(results), "all_valid": all_valid,
            "results": results}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Facet Proof sample kit")
    parser.add_argument("--root", default="sample-work",
                        help="persistent Facet Proof data root / work directory")
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build", help="commission and render catalog samples")
    build.add_argument("--only", nargs="*", help="catalog sample ids to process")
    build.add_argument("--max-steps", type=int, default=20,
                       help="worker invocations in this process")
    build.set_defaults(func=_build)

    export = sub.add_parser("export", help="export complete samples")
    export.add_argument("--output", default="sample-dataset")
    export.set_defaults(func=_export)

    audit = sub.add_parser("audit", help="receiver-side audit of an export")
    audit.add_argument("--dataset", default="sample-dataset")
    audit.set_defaults(func=_audit)

    args = parser.parse_args(argv)
    try:
        result = args.func(args)
    except Fault as exc:
        print(json.dumps({"ok": False, "error": exc.code,
                          "message": exc.message}, ensure_ascii=False))
        return 1
    print(json.dumps({"ok": True, "result": result}, ensure_ascii=False,
                     indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
