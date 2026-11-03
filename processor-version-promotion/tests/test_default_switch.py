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

"""Offline test for step 8 of copy_processor.py: the default switches only after verification.
Run from the repo root: .venv/bin/python tests/test_default_switch.py   (or: pytest tests/)
"""
import sys

sys.path.insert(0, "scripts")
import copy_processor as cp
from google.cloud import documentai_v1beta3 as docai

PROC = "projects/123/locations/us/processors/destproc"
OLD = f"{PROC}/processorVersions/old1"
NEW = f"{PROC}/processorVersions/new1"
S = docai.ProcessorVersion.State


class _Op:
    def result(self, timeout=None):
        return None


class FakeClient:
    """Just enough of DocumentProcessorServiceClient for deploy_and_default and the confirmation."""

    def __init__(self, default=OLD, new_state=S.DEPLOYED, switch_takes_effect=True):
        self.default = default
        self.versions = {OLD: docai.ProcessorVersion(name=OLD, state=S.DEPLOYED),
                         NEW: docai.ProcessorVersion(name=NEW, state=new_state)}
        self.switch_takes_effect = switch_takes_effect
        self.set_calls, self.deploy_calls = [], []

    def get_processor(self, name):
        return docai.Processor(name=name, default_processor_version=self.default)

    def get_processor_version(self, name):
        return self.versions[name]

    def deploy_processor_version(self, name):
        self.deploy_calls.append(name)
        self.versions[name].state = S.DEPLOYED
        return _Op()

    def set_default_processor_version(self, request):
        self.set_calls.append(request.default_processor_version)
        if self.switch_takes_effect:
            self.default = request.default_processor_version
        return _Op()


def run(client, **kw):
    row = {}
    args = dict(deploy=True, set_default=True, verified=True, dry_run=False, run_row=row)
    args.update(kw)
    problem = cp.switch_default_after_verification(client, PROC, NEW, **args)
    return problem, row


def test_failed_verification_leaves_default_alone():
    c = FakeClient()
    problem, row = run(c, verified=False)
    assert problem is None and c.set_calls == [] and c.default == OLD
    assert row["default_processor_version"] == "old1"


def test_passed_verification_switches_and_confirms():
    c = FakeClient()
    problem, row = run(c, verified=True)
    assert problem is None and c.set_calls == [NEW] and c.default == NEW
    assert row["default_processor_version"] == "new1"


def test_no_verify_still_switches():
    c = FakeClient()
    problem, _ = run(c, verified=None)
    assert problem is None and c.set_calls == [NEW]


def test_switch_that_does_not_take_effect_is_reported():
    c = FakeClient(switch_takes_effect=False)
    problem, _ = run(c, verified=True)
    assert problem and "expected new1" in problem


def test_no_set_default_or_dry_run_touches_nothing():
    for kw in (dict(set_default=False), dict(dry_run=True)):
        c = FakeClient()
        problem, row = run(c, **kw)
        assert problem is None and c.set_calls == [] and c.default == OLD and row == {}


def test_undeployed_version_without_deploy_flag_is_refused():
    c = FakeClient(new_state=S.UNDEPLOYED)
    try:
        run(c, deploy=False, verified=None)
    except RuntimeError as e:
        assert "not deployed" in str(e) and c.set_calls == []
    else:
        raise AssertionError("expected RuntimeError for an undeployed version without --deploy")


if __name__ == "__main__":
    tests = [f for n, f in sorted(globals().items()) if n.startswith("test_")]
    for t in tests:
        t()
        print(f"ok  {t.__name__}")
    print(f"{len(tests)} passed")
