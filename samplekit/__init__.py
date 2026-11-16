"""Facet Proof sample commissioning kit.

Drives the Facet Proof service through its own in-process HTTP routing layer
to build a resumable library of multi-part assembly plates with matching RGB,
depth and object-identifier channels.
"""

# Repository root is inserted on sys.path by the entry points so every script
# can run under "python3 -I" without relying on PYTHONPATH or a site install.
