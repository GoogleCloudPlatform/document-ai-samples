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

# pylint: disable=missing-class-docstring,missing-function-docstring,too-few-public-methods

import sys
from typing import Any

from google.cloud import documentai_v1beta3 as docai

sys.path.insert(0, "scripts")
import copy_processor as cp  # noqa: E402  # pylint: disable=wrong-import-position

PROC = "projects/123/locations/us/processors/destproc"
OLD = f"{PROC}/processorVersions/old1"
NEW = f"{PROC}/processorVersions/new1"
S = docai.ProcessorVersion.State


class _Op:
    def result(self, timeout: Any = None) -> None:
        del timeout


class FakeClient:
    """Just enough of DocumentProcessorServiceClient for deploy_and_default and confirmation."""

    def __init__(
        self,
        default: str = OLD,
        new_state: Any = S.DEPLOYED,
        switch_takes_effect: bool = True,
    ) -> None:
        self.default = default
        self.versions = {
            OLD: docai.ProcessorVersion(name=OLD, state=S.DEPLOYED),
            NEW: docai.ProcessorVersion(name=NEW, state=new_state),
        }
        self.switch_takes_effect = switch_takes_effect
        self.set_calls: list[str] = []
        self.deploy_calls: list[str] = []

    def get_processor(self, name: str) -> docai.Processor:
        return docai.Processor(name=name, default_processor_version=self.default)

    def get_processor_version(self, name: str) -> docai.ProcessorVersion:
        return self.versions[name]

    def deploy_processor_version(self, name: str) -> _Op:
        self.deploy_calls.append(name)
        self.versions[name] = docai.ProcessorVersion(name=name, state=S.DEPLOYED)
        return _Op()

    def set_default_processor_version(self, request: Any) -> _Op:
        self.set_calls.append(request.default_processor_version)
        if self.switch_takes_effect:
            self.default = request.default_processor_version
        return _Op()


def run(client: Any, **kw: Any) -> tuple[str | None, dict[str, Any]]:
    row: dict[str, Any] = {}
    args: dict[str, Any] = {
        "deploy": True,
        "set_default": True,
        "verified": True,
        "dry_run": False,
        "run_row": row,
    }
    args.update(kw)
    problem = cp.switch_default_after_verification(client, PROC, NEW, **args)
    return problem, row


def test_failed_verification_leaves_default_alone() -> None:
    c = FakeClient()
    problem, row = run(c, verified=False)
    assert problem is None and not c.set_calls and c.default == OLD
    assert row["default_processor_version"] == "old1"


def test_passed_verification_switches_and_confirms() -> None:
    c = FakeClient()
    problem, row = run(c, verified=True)
    assert problem is None and c.set_calls == [NEW] and c.default == NEW
    assert row["default_processor_version"] == "new1"


def test_no_verify_still_switches() -> None:
    c = FakeClient()
    problem, _ = run(c, verified=None)
    assert problem is None and c.set_calls == [NEW]


def test_switch_that_does_not_take_effect_is_reported() -> None:
    c = FakeClient(switch_takes_effect=False)
    problem, _ = run(c, verified=True)
    assert problem and "expected new1" in problem


def test_no_set_default_or_dry_run_touches_nothing() -> None:
    for kw in ({"set_default": False}, {"dry_run": True}):
        c = FakeClient()
        problem, row = run(c, **kw)
        assert problem is None and not c.set_calls and c.default == OLD and not row


def test_undeployed_version_without_deploy_flag_is_refused() -> None:
    c = FakeClient(new_state=S.UNDEPLOYED)
    try:
        run(c, deploy=False, verified=None)
    except RuntimeError as e:
        assert "not deployed" in str(e) and not c.set_calls
    else:
        raise AssertionError(
            "expected RuntimeError for an undeployed version without --deploy"
        )


if __name__ == "__main__":
    tests = [f for n, f in sorted(globals().items()) if n.startswith("test_")]
    for t in tests:
        t()
        print(f"ok  {t.__name__}")
    print(f"{len(tests)} passed")
