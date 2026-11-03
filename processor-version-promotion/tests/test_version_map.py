# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Offline branch test for copy_processor.import_version + VersionMap (no GCP calls).
Run from the repo root: .venv/bin/python tests/test_version_map.py
"""
import sys, tempfile, types
from pathlib import Path
sys.path.insert(0, "scripts")
import copy_processor as cp
from google.cloud import documentai_v1beta3 as docai
from google.api_core.exceptions import NotFound

DEST = "projects/123/locations/us/processors/destproc"
SRC = "projects/123/locations/us/processors/srcproc"
S = docai.ProcessorVersion.State

def ver(pid, name, state=S.DEPLOYED):
    return docai.ProcessorVersion(name=f"{DEST}/processorVersions/{pid}", display_name=name, state=state)

class FakeClient:
    def __init__(self, versions): self.versions = {v.name: v for v in versions}; self.imports = []
    def list_processor_versions(self, parent): return list(self.versions.values())
    def get_processor_version(self, name):
        if name not in self.versions: raise NotFound(name)
        return self.versions[name]
    def import_processor_version(self, request):
        new_id = f"new{len(self.imports)+1}"
        src_id = request.external_processor_version_source.processor_version.split("/")[-1]
        self.imports.append(src_id)
        # the imported version keeps the SOURCE display name
        dn = {"srcA": "custom-v1", "srcB": "custom-v1", "srcC": "custom-v2"}[src_id]
        v = ver(new_id, dn); self.versions[v.name] = v
        class Op:
            def result(self_, timeout): return types.SimpleNamespace(processor_version=v.name)
        return Op()

def src(pid, name): return docai.ProcessorVersion(name=f"{SRC}/processorVersions/{pid}", display_name=name)

tmp = tempfile.mkdtemp()
results = []
def check(label, cond): results.append((label, cond)); print(("PASS " if cond else "FAIL ") + label)

# --- legacy: no map -> reuse by name with warning
c = FakeClient([ver("d1", "custom-v1")])
lin = {}
out = cp.import_version(c, DEST, src("srcB", "custom-v1"), "us", False, version_map=None, lineage=lin)
check("legacy reuses by display name", out.endswith("/d1") and lin["version_action"] == "reused_by_name" and not c.imports)

# --- adopt: map empty, d1 unclaimed -> adopt, recorded
c = FakeClient([ver("d1", "custom-v1")])
vm = cp.VersionMap(tmp, DEST, SRC, "proj")
lin = {}
out = cp.import_version(c, DEST, src("srcA", "custom-v1"), "us", False, version_map=vm, lineage=lin)
check("adopt unclaimed same-name version", out.endswith("/d1") and lin["version_action"] == "adopted" and not c.imports)
check("adoption persisted", cp.VersionMap(tmp, DEST, SRC, "proj").lookup("srcA").endswith("/d1"))

# --- pinned: second run with same source id -> reuse by id, no listing needed
lin = {}
out = cp.import_version(c, DEST, src("srcA", "custom-v1"), "us", False, version_map=vm, lineage=lin)
check("pinned reuse by id", out.endswith("/d1") and lin["version_action"] == "reused" and not c.imports)

# --- COLLISION: srcB also called 'custom-v1' but d1 is claimed by srcA -> must import
lin = {}
out = cp.import_version(c, DEST, src("srcB", "custom-v1"), "us", False, version_map=vm, lineage=lin)
check("same name, different source id -> imported, not reused", c.imports == ["srcB"] and out.endswith("/new1") and lin["version_action"] == "imported")
check("both pinned independently", vm.lookup("srcA").endswith("/d1") and vm.lookup("srcB").endswith("/new1"))

# --- revert to srcA: still resolves to d1 even though two 'custom-v1' exist now
lin = {}
out = cp.import_version(c, DEST, src("srcA", "custom-v1"), "us", False, version_map=vm, lineage=lin)
check("revert picks the exact old version among two same-name versions", out.endswith("/d1") and lin["version_action"] == "reused")

# --- stale entry: mapped version deleted -> forget + re-import
del c.versions[f"{DEST}/processorVersions/new1"]
lin = {}
out = cp.import_version(c, DEST, src("srcB", "custom-v1"), "us", False, version_map=vm, lineage=lin)
check("stale map entry -> re-import", c.imports == ["srcB", "srcB"] and out.endswith("/new2"))

# --- FAILED mapped version -> re-import
c.versions[f"{DEST}/processorVersions/new2"].state = S.FAILED
lin = {}
out = cp.import_version(c, DEST, src("srcB", "custom-v1"), "us", False, version_map=vm, lineage=lin)
check("FAILED mapped version -> re-import", c.imports == ["srcB", "srcB", "srcB"] and out.endswith("/new3"))

# --- dry run never writes
before = Path(vm.uri).read_text()
cp.import_version(c, DEST, src("srcC", "custom-v2"), "us", True, version_map=vm, lineage={})
check("dry-run does not write the map", Path(vm.uri).read_text() == before and len(c.imports) == 3)

print("\nmap file:", vm.uri); print(Path(vm.uri).read_text())
failed = [l for l, ok in results if not ok]
sys.exit(1 if failed else 0)
