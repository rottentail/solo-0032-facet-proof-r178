"""Thin client over the Facet Proof in-process HTTP router.

Using route_request exercises the same validation, sealing, leasing and tile
code paths as the JSON HTTP server, without opening a network port. All calls
go through the public routing surface rather than reaching into service
internals, except where a test needs to simulate a crashed worker lease.
"""
from facetproof.application import Application
from facetproof.routing import PREFIX, route_request
from facetproof.errors import Fault


class Client:
    def __init__(self, root):
        self.app = Application(root)

    def call(self, method, route, data=None):
        return route_request(self.app, method, PREFIX + route, data)

    # -- resources ---------------------------------------------------------
    def resource_snapshot(self):
        return self.call("GET", "resources")

    def set_capacity(self, capacity, revision):
        return self.call("PUT", "resources",
                         {"capacity": capacity, "revision": revision})

    # -- intake ------------------------------------------------------------
    def create_mesh(self, payload):
        return self.call("POST", "meshes", payload)

    def create_pigment(self, payload):
        return self.call("POST", "pigments", payload)

    def create_assembly(self, payload):
        return self.call("POST", "assemblies", payload)

    def revise_assembly(self, assembly_id, revision, **changes):
        return self.call("PUT", f"assemblies/{assembly_id}",
                         {"revision": revision, **changes})

    def seal(self, assembly_id, revision):
        return self.call("POST", f"assemblies/{assembly_id}/seal",
                         {"revision": revision})

    # -- exposure lifecycle ------------------------------------------------
    def submit_exposure(self, seal_id, key, request):
        return self.call("POST", f"seals/{seal_id}/exposures",
                         {"key": key, **request})

    def get_exposure(self, exposure_id):
        return self.call("GET", f"exposures/{exposure_id}")

    def progress(self, exposure_id):
        return self.call("GET", f"exposures/{exposure_id}/progress")

    def cancel(self, exposure_id):
        return self.call("POST", f"exposures/{exposure_id}/cancel")

    def retry(self, exposure_id):
        return self.call("POST", f"exposures/{exposure_id}/retry")

    def recover(self):
        return self.call("POST", "worker/recover")

    def worker_step(self):
        return self.call("POST", "worker/step")

    # -- plate facts -------------------------------------------------------
    def get_plate(self, plate_id):
        return self.call("GET", f"plates/{plate_id}")

    def verify_plate(self, plate_id):
        return self.call("POST", f"plates/{plate_id}/verify")

    def read_pass(self, plate_id, name):
        data, _content_type = self.call("GET", f"plates/{plate_id}/passes/{name}")
        return data

    def bundle(self, plate_id):
        data, _content_type = self.call("GET", f"plates/{plate_id}/bundle")
        return data

    def pick(self, plate_id, x, y):
        return route_request(
            self.app, "GET",
            PREFIX + f"plates/{plate_id}/pick?x={int(x)}&y={int(y)}")

    # -- test-only lease manipulation (simulates a hard worker crash) ------
    def crash_running_lease(self, exposure_id):
        """Expire the lease of a running exposure without settling it.

        Mirrors a process killed mid-render: the exposure stays 'running' with
        an expired lease, its tiles and capacity reservation remain on disk.
        """
        from facetproof.values import now
        with self.app.db.unit_of_work() as conn:
            row = conn.execute(
                "SELECT state FROM exposures WHERE id=?", (exposure_id,)
            ).fetchone()
            if row is None or row["state"] != "running":
                raise Fault("state", "Exposure is not running")
            conn.execute(
                "UPDATE exposures SET lease_until=? WHERE id=?",
                (now() - 1, exposure_id),
            )
