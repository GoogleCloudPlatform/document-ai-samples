#!/usr/bin/env python3
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

"""compare_processors.py - read-only, side-by-side comparison of two Document AI processors.

Answers "why does the same pretrained version score differently on these two processors?" and
"is the copy in qa really the processor we had in dev?" by showing everything that can differ:

  1. processor facts        type, default version, location, creation time
  2. versions               id, name, state, model type, Google-managed or not, fine-tune base,
                            latest evaluation F1
  3. dataset                storage, number of documents per split (train / test / unassigned)
                            and labeling state (labeled / auto-labeled / unlabeled), page counts
  4. schema                 the dataset schema of each processor (what the console shows under
                            "Define schema", what labeling, evaluation and the next training use)
  5. schema diff            field by field: fields only in one, differing value type / occurrence /
                            method / description / inactive flag, and field ORDER (the schema is the
                            prompt for the foundation model, so all of this moves accuracy)
  6. evaluations            per-field precision / recall / F1, fuzzy and exact, with the number
                            of test documents behind the number; side by side where both
                            processors evaluated the same version
  7. audit log              Admin Activity: schema changes, training, imports, deploys, default
                            switches - who, when, console or script; which versions were imported
                            into the processor and which were trained in it; process calls if Data
                            Access logging is on
  8. probe (optional)       send the same document(s) - a gs:// file, or a gs:// folder ending in /
                            - to both processors with the given versions and the same empty process
                            options; optionally repeat with each other's schema
                            (processOptions.schemaOverride). Prints per-field counts, confidences
                            and whether the extracted values agree - the values themselves only
                            with --show-values. No labels needed: this checks "same model, same
                            answer", not accuracy.
  9. migration check        --migration: PASS/FAIL that B is a faithful copy of A (same type,
                            identical dataset schema, B's default deployed and named like the pinned
                            source version, same kind and base model, and the schema frozen inside
                            the version itself - the one inference uses - identical on both sides)

Nothing is created, changed or deleted. Nothing about document content is printed unless
--show-values is given. Needs roles/documentai.viewer on the project (listing dataset documents
and the probe need more; those sections are skipped with a message if the role is missing).

A processor can be given as a display name or id (with --project), as PROJECT/NAME-OR-ID, or as a
full resource name - so A and B may live in different projects (source in dev, copy in qa).

Examples (Cloud Shell, your own account):
  # two processors in one project
  python3 scripts/compare_processors.py --project my-training-project \
      invoice_extractor invoice_extractor_v2 --out ~/compare_invoice_extractors
  # after a promotion: source in the training project vs the copy in qa, pinned source version
  python3 scripts/compare_processors.py my-training-project/<source-processor-id> \
      my-qa-project/<qa-processor-id> --migration --version-a <source-version-id>
  # the same documents through both (version ids differ after an import: give both)
  python3 scripts/compare_processors.py my-training-project/<id> my-qa-project/<id> \
      --migration --version-a <source version> --version-b <qa version> \
      --probe gs://my-bucket/approved-test-documents/
"""
from __future__ import annotations

# pylint: disable=broad-exception-caught,line-too-long,missing-class-docstring
# pylint: disable=missing-function-docstring,too-many-arguments,too-many-branches
# pylint: disable=too-many-lines,too-many-locals,too-many-nested-blocks
# pylint: disable=too-many-statements

import argparse
from collections import Counter, OrderedDict
import datetime as dt
import difflib
import json
import math
import os
import re
import subprocess
import sys
from typing import Any, NoReturn
import urllib.error
import urllib.parse
import urllib.request

API_VERSION = "v1beta3"
HEX_ID = re.compile(r"^[0-9a-f]{8,16}$")


# ----------------------------------------------------------------------------- plumbing
class ApiError(Exception):
    def __init__(self, code: int, msg: str):
        super().__init__(f"HTTP {code}: {msg}")
        self.code, self.msg = code, msg


def http_json(method: str, url: str, token: str, body=None, quota_project: str | None = None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")
    if quota_project:
        req.add_header("x-goog-user-project", quota_project)
    try:
        with urllib.request.urlopen(req, timeout=900) as resp:
            return json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        text = e.read().decode(errors="replace")
        try:
            msg = json.loads(text)["error"]["message"]
        except Exception:
            msg = text[:400]
        raise ApiError(e.code, msg) from None


class Api:
    def __init__(self, location: str, token: str, quota_project: str | None = None):
        self.base = f"https://{location}-documentai.googleapis.com/{API_VERSION}/"
        self.token, self.quota_project = token, quota_project

    def call(self, method: str, path: str, body=None, params=None):
        url = self.base + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        return http_json(method, url, self.token, body, self.quota_project)

    def paged(self, path: str, key: str, page_size: int = 100, params=None):
        params = dict(params or {})
        params["pageSize"] = page_size
        items, token = [], None
        while True:
            if token:
                params["pageToken"] = token
            resp = self.call("GET", path, params=params)
            items += resp.get(key, [])
            token = resp.get("nextPageToken")
            if not token:
                return items


def gcloud_token(account: str | None) -> str:
    if os.environ.get("DOCAI_TOKEN"):
        return os.environ["DOCAI_TOKEN"]
    cmd = ["gcloud", "auth", "print-access-token"] + (["--account", account] if account else [])
    return subprocess.check_output(cmd, text=True).strip()


def die(msg: str) -> NoReturn:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def short(s: str, n: int = 70) -> str:
    s = " ".join((s or "").split())
    return s if len(s) <= n else s[:n - 1] + "…"


def section(title: str):
    print(f"\n{'=' * 100}\n{title}\n{'=' * 100}")


def table(headers, rows, max_width=60):
    if not rows:
        print("  (none)")
        return
    rows = [[short(str(c), max_width) for c in r] for r in rows]
    widths = [max(len(h), *(len(r[i]) for r in rows)) for i, h in enumerate(headers)]
    fmt = "  " + "  ".join(f"{{:<{w}}}" for w in widths)
    print(fmt.format(*headers))
    print(fmt.format(*["-" * w for w in widths]))
    for r in rows:
        print(fmt.format(*r))


# ----------------------------------------------------------------------------- lookups
def resolve(api: Api, project: str | None, location: str, ident: str) -> str:
    if ident.startswith("projects/"):
        return ident
    if ident.count("/") == 1:  # PROJECT/NAME-OR-ID
        project, ident = ident.split("/", 1)
    if not project:
        die(f"{ident!r}: give --project, or write it as PROJECT/{ident}")
    parent = f"projects/{project}/locations/{location}"
    if HEX_ID.match(ident):
        return f"{parent}/processors/{ident}"
    procs = api.paged(f"{parent}/processors", "processors")
    hits = [p for p in procs if p.get("displayName") == ident]
    if not hits:
        hits = [p for p in procs if p.get("displayName", "").lower() == ident.lower()]
    if len(hits) == 1:
        # keep the project ID the caller gave: the API answers with the project NUMBER, and the audit-log
        # filter (logName="projects/<id>/...") only matches the ID form
        return f"{parent}/processors/{hits[0]['name'].split('/')[-1]}"
    names = ", ".join(sorted(p.get("displayName", "?") for p in procs))
    if not hits:
        die(f"no processor named {ident!r} in {parent}. Processors there: {names}")
    ids = ", ".join(h["name"].split("/")[-1] for h in hits)
    die(f"{len(hits)} processors are named {ident!r}: {ids} - pass the id instead")


def version_rows(versions, default_id=""):
    rows = []
    for v in versions:
        vid = v["name"].split("/")[-1]
        g = v.get("genAiModelInfo", {})
        if "foundationGenAiModelInfo" in g:
            f = g["foundationGenAiModelInfo"]
            ft = "allowed" if f.get("finetuningAllowed") else "not allowed"
            min_docs = f.get("minTrainLabeledDocuments", "?")
            kind = f"foundation; fine-tuning {ft}; min train docs {min_docs}"
        elif "customGenAiModelInfo" in g:
            c = g["customGenAiModelInfo"]
            kind = f"{c.get('customModelType', '?')} base={c.get('baseProcessorVersionId', '?')}"
        else:
            kind = ""
        le = v.get("latestEvaluation", {})
        am = le.get("aggregateMetrics", {})
        f1 = f"{am['f1Score']:.3f}" if "f1Score" in am else "-"
        dep = v.get("deprecationInfo", {})
        rows.append([
            ("* " if vid == default_id else "  ") + vid,
            v.get("displayName", ""),
            v.get("state", ""),
            v.get("modelType", "").replace("MODEL_TYPE_", "") or "-",
            "yes" if v.get("googleManaged") else "no",
            kind or "-",
            f1,
            v.get("createTime", "")[:10],
            ("deprecated " + dep.get("deprecationTime", "")[:10]) if dep else "",
        ])
    return rows


def dataset_counts(api: Api, proc: str):
    body: dict[str, Any] = {"pageSize": 100, "returnTotalSize": True}
    docs: Counter[tuple[str, str]] = Counter()
    pages: Counter[tuple[str, str]] = Counter()
    total = None
    token = None
    while True:
        if token:
            body["pageToken"] = token
        resp = api.call("POST", f"{proc}/dataset:listDocuments", body=body)
        total = resp.get("totalSize", total)
        for d in resp.get("documentMetadata", []):
            key = (
                d.get("datasetType", "?").replace("DATASET_SPLIT_", ""),
                d.get("labelingState", "?").replace("DOCUMENT_", ""),
            )
            docs[key] += 1
            pages[key] += int(d.get("pageCount", 0) or 0)
        token = resp.get("nextPageToken")
        if not token:
            break
    return docs, pages, total


# ----------------------------------------------------------------------------- schema
def flatten_schema(doc_schema: dict):
    """Returns (header_attrs, OrderedDict path -> attrs). Nested entity types are walked from the
    document-level type(s); the path is parent/child."""
    types = OrderedDict((t["name"], t) for t in doc_schema.get("entityTypes", []))
    roots = [t for t in types.values() if "document" in (t.get("baseTypes") or [])]
    if not roots and types:
        roots = [next(iter(types.values()))]
    fields: OrderedDict[str, dict] = OrderedDict()

    def walk(t: dict, prefix: str, depth: int):
        if depth > 6:
            return
        for p in t.get("properties", []):
            path = prefix + p.get("name", "?")
            meta = p.get("propertyMetadata", {}) or {}
            summary = (meta.get("fieldExtractionMetadata") or {}).get("summaryOptions")
            fields[path] = {
                "valueType": p.get("valueType", ""),
                "occurrenceType": p.get("occurrenceType", ""),
                "description": " ".join((p.get("description") or "").split()),
                "displayName": p.get("displayName", ""),
                "inactive": "yes" if meta.get("inactive") else "no",
                "method": p.get("method", ""),
                "summary": json.dumps(summary, sort_keys=True) if summary else "",
            }
            child = types.get(p.get("valueType"))
            if child is not None and child is not t:
                walk(child, path + "/", depth + 1)

    for r in roots:
        walk(r, "", 0)

    header = OrderedDict()
    header["schema.displayName"] = doc_schema.get("displayName", "")
    header["schema.description"] = " ".join((doc_schema.get("description") or "").split())
    header["root.entityType"] = ", ".join(r.get("name", "?") for r in roots)
    header["root.displayName"] = ", ".join(r.get("displayName", "") for r in roots)
    header["root.description"] = ", ".join(" ".join((r.get("description") or "").split()) for r in roots)
    header["entityTypes.count"] = str(len(types))
    for k, v in (doc_schema.get("metadata") or {}).items():
        header[f"metadata.{k}"] = str(v)
    return header, fields


def normalized_schema_text(doc_schema: dict) -> str:
    return json.dumps(doc_schema, indent=2, sort_keys=True, ensure_ascii=False)


def compare_schemas(label_a, header_a, fields_a, label_b, header_b, fields_b):
    print(f"\n  {label_a}: {len(fields_a)} fields    {label_b}: {len(fields_b)} fields")
    hdr = [
        [k, header_a.get(k, ""), header_b.get(k, "")]
        for k in sorted(set(header_a) | set(header_b))
        if header_a.get(k, "") != header_b.get(k, "")
    ]
    print("\n  schema-level differences:")
    table(["attribute", label_a, label_b], hdr, max_width=45)

    only_a = [k for k in fields_a if k not in fields_b]
    only_b = [k for k in fields_b if k not in fields_a]
    print(f"\n  fields only in {label_a} ({len(only_a)}):")
    table(
        ["field", "valueType", "occurrence", "inactive", "description"],
        [
            [
                k,
                fields_a[k]["valueType"],
                fields_a[k]["occurrenceType"],
                fields_a[k]["inactive"],
                fields_a[k]["description"],
            ]
            for k in only_a
        ],
    )
    print(f"\n  fields only in {label_b} ({len(only_b)}):")
    table(
        ["field", "valueType", "occurrence", "inactive", "description"],
        [
            [
                k,
                fields_b[k]["valueType"],
                fields_b[k]["occurrenceType"],
                fields_b[k]["inactive"],
                fields_b[k]["description"],
            ]
            for k in only_b
        ],
    )

    common = [k for k in fields_a if k in fields_b]
    diffs = []
    for k in common:
        for attr in ("valueType", "occurrenceType", "inactive", "method", "summary", "displayName", "description"):
            va, vb = fields_a[k][attr], fields_b[k][attr]
            if va == vb:
                continue
            note = ""
            if attr == "description":
                if va.lower() == vb.lower():
                    note = " [case only]"
                elif not va or not vb:
                    note = " [one side empty]"
            diffs.append([k, attr + note, va or "(empty)", vb or "(empty)"])
    diff_field_count = len({d[0] for d in diffs})
    print(f"\n  fields in both but different ({len(diffs)} differences across {diff_field_count} fields):")
    table(["field", "attribute", label_a, label_b], diffs, max_width=55)

    core_attrs = ("valueType", "occurrenceType", "inactive", "description")
    same_attrs = [
        k for k in common
        if all(fields_a[k][a] == fields_b[k][a] for a in core_attrs)
    ]
    print(
        "\n  fields identical in both (name, type, occurrence, inactive, description): "
        f"{len(same_attrs)} of {len(common)} common"
    )

    order_a = [k for k in fields_a if k in fields_b]
    order_b = [k for k in fields_b if k in fields_a]
    if order_a != order_b:
        first = next(i for i, (x, y) in enumerate(zip(order_a, order_b)) if x != y)
        print(
            f"\n  ORDER of the common fields differs - first difference at position {first + 1}: "
            f"{label_a}={order_a[first]!r}, {label_b}={order_b[first]!r}"
        )
    else:
        print("\n  order of the common fields: identical")

    verdict = []
    if only_a or only_b:
        verdict.append(f"{len(only_a) + len(only_b)} field(s) exist on one side only")
    if diffs:
        verdict.append(f"{diff_field_count} shared field(s) differ in type/occurrence/description")
    if hdr:
        verdict.append("schema-level attributes differ")
    if order_a != order_b:
        verdict.append("field order differs")
    print("\n  VERDICT: " + ("; ".join(verdict) if verdict else "the two schemas are identical"))
    return not verdict


# ----------------------------------------------------------------------------- evaluations
def level0(mcm: dict, exact: bool = False):
    lv = mcm.get("confidenceLevelMetricsExact" if exact else "confidenceLevelMetrics") or []
    if not lv:
        return None
    return min(lv, key=lambda x: float(x.get("confidenceLevel", 0))).get("metrics", {})


def f3(x) -> str:
    """Metrics come back as numbers, or as the string "NaN" when undefined (no ground truth for the field)."""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return "-"
    return "nan" if math.isnan(v) else f"{v:.3f}"


def fmt_metrics(m):
    if not m:
        return "-"
    text = f"F1 {f3(m.get('f1Score'))}  P {f3(m.get('precision'))}  R {f3(m.get('recall'))}"
    if m.get("predictedOccurrencesCount") or m.get("groundTruthOccurrencesCount"):
        pred_cnt = m.get("predictedOccurrencesCount", 0)
        gt_cnt = m.get("groundTruthOccurrencesCount", 0)
        text += f"  (predicted {pred_cnt}, ground truth {gt_cnt})"
    return text


def show_evaluation(api: Api, ev_ref: dict):
    """ev_ref = the version's latestEvaluation (EvaluationReference)."""
    ev_name = ev_ref["evaluation"]
    ev = api.call("GET", ev_name)
    dc = ev.get("documentCounters", {})
    print(
        f"    evaluation {ev_name.split('/')[-1]}  created {ev.get('createTime', '')[:19]}   test documents: "
        f"input {dc.get('inputDocumentsCount', 0)}, evaluated {dc.get('evaluatedDocumentsCount', 0)}, "
        f"invalid {dc.get('invalidDocumentsCount', 0)}, failed {dc.get('failedDocumentsCount', 0)}"
    )
    allm = ev.get("allEntitiesMetrics") or {}
    # the aggregate is not always inside the Evaluation; the version's reference carries it too
    fuzzy = level0(allm) or ev_ref.get("aggregateMetrics")
    exact = level0(allm, True) or ev_ref.get("aggregateMetricsExact")
    print(f"      all fields  fuzzy: {fmt_metrics(fuzzy)}")
    print(f"                  exact: {fmt_metrics(exact)}")
    per_field: dict[str, float | None] = {}
    rows = []
    for name, m in sorted(ev.get("entityMetrics", {}).items()):
        f, e = level0(m) or {}, level0(m, True) or {}
        f1_raw = f.get("f1Score")
        try:
            per_field[name] = float(f1_raw) if f1_raw is not None else None
        except (TypeError, ValueError):
            per_field[name] = None
        rows.append([
            name,
            f3(f.get("f1Score")) if f else "-",
            f3(e.get("f1Score")) if e else "-",
            f3(f.get("precision")) if f else "-",
            f3(f.get("recall")) if f else "-",
            f.get("groundTruthOccurrencesCount", "-"),
            f.get("predictedOccurrencesCount", "-"),
        ])
    table(["field", "F1 fuzzy", "F1 exact", "P fuzzy", "R fuzzy", "truth", "predicted"], rows)
    return ev, per_field


# ----------------------------------------------------------------------------- audit log
INTERESTING = {
    "UpdateDatasetSchema": "SCHEMA CHANGED",
    "UpdateDataset": "dataset config changed",
    "ImportDocuments": "documents imported",
    "BatchMoveDocuments": "documents moved (train/test split)",
    "BatchDeleteDocuments": "documents deleted",
    "TrainProcessorVersion": "training started",
    "ImportProcessorVersion": "version imported",
    "EvaluateProcessorVersion": "evaluation run",
    "DeployProcessorVersion": "version deployed",
    "UndeployProcessorVersion": "version undeployed",
    "SetDefaultProcessorVersion": "default changed",
    "DeleteProcessorVersion": "version deleted",
    "CreateProcessor": "processor created",
    "UpdateProcessor": "processor updated",
}


def count_schema_fields(doc_schema: dict) -> int:
    return sum(len(t.get("properties", []) or []) for t in (doc_schema or {}).get("entityTypes", []) or [])


def audit_entries(token: str, project: str, filter_str: str, max_entries: int = 600):
    entries: list[dict[str, Any]] = []
    page = None
    while len(entries) < max_entries:
        body: dict[str, Any] = {
            "resourceNames": [f"projects/{project}"],
            "filter": filter_str,
            "orderBy": "timestamp desc",
            "pageSize": 200,
        }
        if page:
            body["pageToken"] = page
        resp = http_json("POST", "https://logging.googleapis.com/v2/entries:list", token, body)
        entries += resp.get("entries", [])
        page = resp.get("nextPageToken")
        if not page:
            break
    return entries


def audit_section(token: str, project: str, proc_name: str, label: str, display: str, days: int):
    pid = proc_name.split("/")[-1]
    if project.isdigit():
        print(
            f"\n  {label}  {display}: the audit log is filed under the project ID, not the number {project} - "
            f"give the processor as PROJECT_ID/{pid} to see it; skipped"
        )
        return
    since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    base = (
        f'protoPayload.serviceName="documentai.googleapis.com" '
        f'AND protoPayload.resourceName:"processors/{pid}" '
        f'AND timestamp>="{since}"'
    )
    print(f"\n  {label}  {display}  - last {days} days")
    # Admin Activity: always on, needs roles/logging.viewer
    try:
        act_filter = f'logName="projects/{project}/logs/cloudaudit.googleapis.com%2Factivity" AND {base}'
        acts = audit_entries(token, project, act_filter)
    except ApiError as err:
        print(
            f"    admin-activity log: cannot read ({err.code}: {short(err.msg, 120)}) "
            f"- needs roles/logging.viewer on {project}"
        )
        acts = None
    if acts is not None:
        rows = []
        schema_changes = []
        origins: dict[str, tuple[str, str, str]] = {}
        for entry in acts:
            pl = entry.get("protoPayload", {})
            method = (pl.get("methodName") or "").split(".")[-1]
            who = (pl.get("authenticationInfo") or {}).get("principalEmail", "?")
            status = pl.get("status", {}) or {}
            req = pl.get("request", {}) or {}
            ua = ((pl.get("requestMetadata") or {}).get("callerSuppliedUserAgent") or "").lower()
            # long-running operations log twice: the request (has a user agent) and the completion (none)
            if "mozilla" in ua:
                via = "console"
            elif "gcloud" in ua:
                via = "gcloud"
            elif "python" in ua:
                via = "python"
            elif ua:
                via = "script"
            else:
                via = "op completed"
            rn_tail = (pl.get("resourceName") or "").split("/")[-1]
            extra = ""
            if method == "UpdateDatasetSchema":
                # the schema itself is not kept in the log; who / when / from where is
                ds = (req.get("datasetSchema") or {}).get("documentSchema")
                extra = f"via {via}" + (f", {count_schema_fields(ds)} fields" if ds else "")
                schema_changes.append((entry.get("timestamp", "")[:19], who, extra))
            elif method == "SetDefaultProcessorVersion":
                extra = f"-> {rn_tail} via {via}"
            elif method in (
                "TrainProcessorVersion",
                "ImportProcessorVersion",
                "EvaluateProcessorVersion",
                "DeployProcessorVersion",
                "UndeployProcessorVersion",
                "DeleteProcessorVersion",
            ):
                extra = f"version {rn_tail} via {via}"
                # the completion entry names the new version; the request entry only names the processor
                if (
                    method in ("TrainProcessorVersion", "ImportProcessorVersion")
                    and rn_tail != pid
                    and not status.get("code")
                ):
                    origins.setdefault(rn_tail, (method, entry.get("timestamp", "")[:10], who))
            elif method == "ImportDocuments":
                extra = f"via {via}"
            if status.get("code"):
                extra = (extra + f"  FAILED: {short(status.get('message', ''), 60)}").strip()
            rows.append([entry.get("timestamp", "")[:19], INTERESTING.get(method, method), who, extra])
        print(f"    admin-activity entries for this processor: {len(rows)}")
        table(["time (UTC)", "what", "who", "detail"], rows[:60], max_width=70)
        if len(rows) > 60:
            print(f"    ... {len(rows) - 60} older entries not shown")
        if schema_changes:
            last_ts, last_who, last_extra = schema_changes[0]
            print(
                f"    SCHEMA CHANGES: {len(schema_changes)} in the window; "
                f"last one {last_ts} by {last_who} ({last_extra})"
            )
        else:
            print(
                f"    SCHEMA CHANGES: none in the last {days} days "
                "(the schema is older than the window, or was set at creation)"
            )
        imported = [f"{v} ({d}, {w})" for v, (m, d, w) in origins.items() if m == "ImportProcessorVersion"]
        trained = [f"{v} ({d})" for v, (m, d, w) in origins.items() if m == "TrainProcessorVersion"]
        print(
            f"    VERSIONS: imported into this processor: {', '.join(imported) or 'none in the window'};  "
            f"trained in this processor: {', '.join(trained) or 'none in the window'}"
        )
        if imported:
            print(
                "      the log keeps who imported and when, NOT where from. To find the original: "
                "look in the suspected source project for a version with the same display name and "
                "base model - the original has an evaluation and an earlier creation time; "
                "the copy has no evaluation and a new id."
            )
    # Data Access: only if enabled on the project; shows how the processor was CALLED
    try:
        da_filter = (
            f'logName="projects/{project}/logs/cloudaudit.googleapis.com%2Fdata_access" AND {base} '
            'AND protoPayload.methodName:("ProcessDocument" OR "BatchProcessDocuments")'
        )
        das = audit_entries(token, project, da_filter)
    except ApiError as err:
        print(
            f"    data-access log: cannot read ({err.code}: {short(err.msg, 100)}) "
            "- needs roles/logging.privateLogViewer; skipped"
        )
        return
    if not das:
        print(
            "    data-access log: no ProcessDocument / BatchProcessDocuments entries "
            "(data-access logging is probably not enabled)"
        )
        return
    calls: Counter[tuple[str, str, str]] = Counter()
    opts: Counter[str] = Counter()
    for entry in das:
        pl = entry.get("protoPayload", {})
        method = (pl.get("methodName") or "").split(".")[-1]
        who = (pl.get("authenticationInfo") or {}).get("principalEmail", "?")
        rn = pl.get("resourceName") or ""
        ver = rn.split("/processorVersions/")[-1] if "/processorVersions/" in rn else "(default)"
        calls[(method, ver, who)] += 1
        req = pl.get("request", {}) or {}
        po = req.get("processOptions")
        opts["with processOptions" if po else "no processOptions"] += 1
        if po and "schemaOverride" in po:
            opts["with schemaOverride"] += 1
    print(f"    data-access: {len(das)} process calls in the window (newest {len(das)} shown in counts)")
    table(["method", "version called", "who", "calls"], [[k[0], k[1], k[2], v] for k, v in calls.most_common(30)])
    print("    request options seen: " + ", ".join(f"{k}: {v}" for k, v in opts.items()))


# ----------------------------------------------------------------------------- probe
def norm_value(s: str) -> str:
    return " ".join((s or "").lower().split())


def summarize_entities(entities):
    out: OrderedDict[str, dict] = OrderedDict()

    def add(e, prefix=""):
        t = prefix + e.get("type", "?")
        d = out.setdefault(t, {"n": 0, "conf": [], "values": []})
        d["n"] += 1
        d["conf"].append(float(e.get("confidence", 0) or 0))
        text = e.get("mentionText") or (e.get("normalizedValue") or {}).get("text") or ""
        d["values"].append(norm_value(text))
        for c in e.get("properties", []) or []:
            add(c, t + "/")

    for e in entities:
        add(e)
    return out


def probe(api: Api, proc: str, version: str, gcs_uri: str, mime: str, schema_override=None):
    body = {
        "gcsDocument": {"gcsUri": gcs_uri, "mimeType": mime},
        "skipHumanReview": True,
        "fieldMask": "entities",
    }
    if schema_override is not None:
        body["processOptions"] = {"schemaOverride": schema_override}
    resp = api.call("POST", f"{proc}/processorVersions/{version}:process", body=body)
    return summarize_entities(resp.get("document", {}).get("entities", []))


MIME_BY_EXT = {
    ".pdf": "application/pdf",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
    ".webp": "image/webp",
}


def expand_probe(token: str, items, default_mime: str, limit: int):
    """gs://bucket/file -> [(uri, mime)]; gs://bucket/folder/ -> every PDF/image under it."""
    docs = []
    for item in items:
        if not item.startswith("gs://"):
            die(f"--probe {item!r}: must be a gs:// file or a gs:// folder ending in /")
        bucket, _, path = item[5:].partition("/")
        if not item.endswith("/"):
            docs.append((item, MIME_BY_EXT.get(os.path.splitext(path)[1].lower(), default_mime)))
            continue
        found, page = [], None
        while True:
            params = {"prefix": path, "fields": "items(name),nextPageToken", "maxResults": 1000}
            if page:
                params["pageToken"] = page
            try:
                list_url = f"https://storage.googleapis.com/storage/v1/b/{bucket}/o?" + urllib.parse.urlencode(params)
                resp = http_json("GET", list_url, token)
            except ApiError as e:
                die(f"--probe {item}: cannot list the folder ({e}) - needs storage.objects.list on the bucket")
            found += [
                o["name"] for o in resp.get("items", [])
                if os.path.splitext(o["name"])[1].lower() in MIME_BY_EXT
            ]
            page = resp.get("nextPageToken")
            if not page:
                break
        if not found:
            die(f"--probe {item}: no PDF or image files under this folder")
        found.sort()
        if len(found) > limit:
            print(f"  --probe {item}: {len(found)} documents, taking the first {limit} (raise --probe-max for more)")
        docs += [(f"gs://{bucket}/{n}", MIME_BY_EXT[os.path.splitext(n)[1].lower()]) for n in found[:limit]]
    return docs


def probe_agreement(sa, sb):
    """(fields with identical extracted values, fields seen by either side)."""
    agree = total = 0
    for t in set(sa) | set(sb):
        a, b = sa.get(t), sb.get(t)
        total += 1
        agree += int(bool(a and b) and sorted(a["values"]) == sorted(b["values"]))
    return agree, total


def compare_probe(label_a, sa, label_b, sb, show_values=False):
    rows = []
    for t in sorted(set(sa) | set(sb)):
        a, b = sa.get(t), sb.get(t)
        ca = f"{sum(a['conf']) / len(a['conf']):.2f}" if a and a["conf"] else "-"
        cb = f"{sum(b['conf']) / len(b['conf']):.2f}" if b and b["conf"] else "-"
        same = (sorted(a["values"]) == sorted(b["values"])) if (a and b) else False
        row = [t, a["n"] if a else 0, b["n"] if b else 0, ca, cb, "same" if same else "DIFFERENT"]
        if show_values:
            row += [" | ".join(a["values"]) if a else "", " | ".join(b["values"]) if b else ""]
        rows.append(row)
    headers = ["field", f"n {label_a}", f"n {label_b}", f"conf {label_a}", f"conf {label_b}", "values"]
    if show_values:
        headers += [f"{label_a} values", f"{label_b} values"]
    table(headers, rows, max_width=80 if show_values else 40)
    agree, total = probe_agreement(sa, sb)
    print(f"  fields with identical extracted values: {agree} of {total}")


def probe_report(docs, run, label_a, label_b, show_values, detail_when_single=True):
    """run(uri, mime) -> {label: summary or None}. Prints one line per document and returns a summary."""
    complete = identical = 0
    for i, (uri, mime) in enumerate(docs, 1):
        r = run(uri, mime)
        if r.get(label_a) is None or r.get(label_b) is None:
            continue
        complete += 1
        agree, total = probe_agreement(r[label_a], r[label_b])
        identical += int(agree == total)
        na, nb = sum(d["n"] for d in r[label_a].values()), sum(d["n"] for d in r[label_b].values())
        print(
            f"\n  [{i}/{len(docs)}] {uri}: {label_a} {na} entities, {label_b} {nb} entities; "
            f"fields with identical values {agree} of {total}" + ("" if agree == total else "  <-- DIFFERENT")
        )
        if (len(docs) == 1 and detail_when_single) or agree != total or show_values:
            compare_probe(label_a, r[label_a], label_b, r[label_b], show_values)
    failed = len(docs) - complete
    fail_str = f", {failed} document(s) failed" if failed else ""
    summary = f"{identical} of {complete} documents with every field identical{fail_str}"
    if identical < complete:
        summary += (
            "\n    (a generative model can flip a borderline field between two identical calls - "
            "run the probe a second time: a real difference repeats, noise does not)"
        )
    return summary


# ----------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("a", help="processor A: display name, id, or full resource name")
    ap.add_argument("b", help="processor B: display name, id, or full resource name")
    ap.add_argument("--project", help="project of both processors (not needed with full resource names)")
    ap.add_argument("--location", default="us")
    ap.add_argument("--account", help="gcloud account for the access token (default: active account)")
    ap.add_argument("--quota-project", help="send x-goog-user-project (only if you get USER_PROJECT_DENIED)")
    ap.add_argument("--out", default="compare_out", help="directory for the raw JSON and the schema diff")
    ap.add_argument("--no-documents", action="store_true", help="skip counting dataset documents")
    ap.add_argument("--no-evaluations", action="store_true", help="skip the per-field evaluation metrics")
    ap.add_argument("--no-audit", action="store_true", help="skip the audit-log section")
    ap.add_argument(
        "--audit-days",
        type=int,
        default=180,
        help="audit-log window in days (default 180; Admin Activity is kept 400)",
    )
    ap.add_argument(
        "--probe",
        metavar="GS_URI",
        action="append",
        help="send the same document(s) to both processors: a gs:// file, or a gs:// folder ending in / "
             "(every PDF/image under it, up to --probe-max). Repeatable. Read-only for the processors; "
             "costs page quota",
    )
    ap.add_argument(
        "--probe-max",
        type=int,
        default=20,
        help="most documents to take from a --probe folder (default 20)",
    )
    ap.add_argument(
        "--version",
        help="processor version id to probe with, e.g. pretrained-foundation-model-v3.1-lite-2026-07-15 "
             "(same id for both)",
    )
    ap.add_argument(
        "--version-a",
        help="version id on A (source): for --probe, and the pinned source version for --migration "
             "(default: A's default)",
    )
    ap.add_argument("--version-b", help="version id on B for --probe (default: --version)")
    ap.add_argument("--migration", action="store_true", help="print PASS/FAIL lines: is B a faithful copy of A?")
    ap.add_argument(
        "--mime",
        default="application/pdf",
        help="mime type for --probe files without a known extension (default application/pdf)",
    )
    ap.add_argument(
        "--swap-schema",
        action="store_true",
        help="with --probe: also run A with B's schema and B with A's schema (schemaOverride)",
    )
    ap.add_argument(
        "--show-values",
        action="store_true",
        help="with --probe: print the extracted values (document content!)",
    )
    args = ap.parse_args()

    if args.probe and not (args.version or (args.version_a and args.version_b)):
        die("--probe needs --version (same id on both) or --version-a and --version-b")
    ver = {"A": args.version_a or args.version, "B": args.version_b or args.version}

    api = Api(args.location, gcloud_token(args.account), args.quota_project)
    os.makedirs(args.out, exist_ok=True)
    probe_docs = expand_probe(api.token, args.probe, args.mime, args.probe_max) if args.probe else []
    probe_summary = None

    names = {}
    for label, ident in (("A", args.a), ("B", args.b)):
        names[label] = resolve(api, args.project, args.location, ident)

    procs, versions, schemas, flat = {}, {}, {}, {}
    schemas_identical = None

    section("1. Processors")
    for label in ("A", "B"):
        p = api.call("GET", names[label])
        procs[label] = p
        with open(os.path.join(args.out, f"{label}.processor.json"), "w", encoding="utf-8") as fh:
            json.dump(p, fh, indent=2)
        print(f"  {label}  {p.get('displayName')}  ({p['name']})")
        print(f"      type {p.get('type')}   state {p.get('state')}   created {p.get('createTime', '')[:10]}")
        print(f"      default version: {(p.get('defaultProcessorVersion') or '-').split('/')[-1]}")
        if p.get("kmsKeyName"):
            print(f"      CMEK: {p['kmsKeyName']}")
    if procs["A"].get("type") != procs["B"].get("type"):
        print("\n  !! different processor TYPES - the comparison stops making sense here")

    section("2. Versions")
    for label in ("A", "B"):
        vs = api.paged(f"{names[label]}/processorVersions", "processorVersions", page_size=20)
        versions[label] = vs
        with open(os.path.join(args.out, f"{label}.versions.json"), "w", encoding="utf-8") as fh:
            json.dump(vs, fh, indent=2)
        default_id = (procs[label].get("defaultProcessorVersion") or "").split("/")[-1]
        print(f"\n  {label}  {procs[label].get('displayName')}  - {len(vs)} versions  (* = default)")
        table(
            ["version id", "name", "state", "model", "google-managed", "kind", "latest F1", "created", "note"],
            version_rows(vs, default_id),
            max_width=70,
        )

    section("3. Dataset documents (train / test split and labeling state)")
    if args.no_documents:
        print("  skipped (--no-documents)")
    for label in ("A", "B"):
        if args.no_documents:
            break
        try:
            docs, pages, total = dataset_counts(api, names[label])
            doc_total = total if total is not None else sum(docs.values())
            print(f"\n  {label}  {procs[label].get('displayName')}  - {doc_total} documents")
            table(["split", "labeling", "documents", "pages"],
                  [[k[0], k[1], docs[k], pages[k]] for k in sorted(docs)])
        except ApiError as e:
            print(
                f"\n  {label}  {procs[label].get('displayName')}  "
                f"- cannot list dataset documents ({e.code}: {short(e.msg, 140)}); "
                "needs dataset read permission (roles/documentai.editor or a custom role "
                "with documentai.datasets.*); skipped"
            )
        except Exception as e:  # never let one section kill the run
            print(f"\n  {label}  dataset documents: unexpected error {e!r}")

    section("4. Schema")
    for label in ("A", "B"):
        try:
            s = api.call("GET", f"{names[label]}/dataset/datasetSchema")
        except ApiError as e:
            print(f"  {label}  schema: {e}")
            continue
        doc_schema = s.get("documentSchema", {})
        schemas[label] = doc_schema
        path = os.path.join(args.out, f"{label}.schema.json")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(normalized_schema_text(doc_schema))
        header, fields = flatten_schema(doc_schema)
        flat[label] = (header, fields)
        print(
            f"\n  {label}  {procs[label].get('displayName')}  "
            f"- {len(fields)} fields, {header['entityTypes.count']} entity types  -> {path}"
        )
        schema_rows = [
            [
                i + 1,
                k,
                v["valueType"],
                v["occurrenceType"],
                (v["method"] or "EXTRACT(default)") + (" +summary" if v["summary"] else ""),
                v["inactive"],
                v["description"],
            ]
            for i, (k, v) in enumerate(fields.items())
        ]
        table(
            ["#", "field", "valueType", "occurrence", "method", "inactive", "description"],
            schema_rows,
            max_width=80,
        )
        methods = Counter((v["method"] or "EXTRACT") for v in fields.values())
        inactive_cnt = sum(1 for v in fields.values() if v["inactive"] == "yes")
        method_str = ", ".join(f"{m}: {n}" for m, n in sorted(methods.items()))
        print(f"      methods: {method_str}   inactive: {inactive_cnt}")

    if "A" in flat and "B" in flat:
        section(f"5. Schema diff  (A = {procs['A'].get('displayName')}, B = {procs['B'].get('displayName')})")
        schemas_identical = compare_schemas("A", *flat["A"], "B", *flat["B"])
        diff = difflib.unified_diff(
            normalized_schema_text(schemas["A"]).splitlines(),
            normalized_schema_text(schemas["B"]).splitlines(),
            fromfile="A.schema.json",
            tofile="B.schema.json",
            lineterm="",
        )
        diff_path = os.path.join(args.out, "schema.diff")
        with open(diff_path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(diff) + "\n")
        print(f"\n  full unified diff of the two schema JSON files: {diff_path}")

    if not args.no_evaluations:
        section("6. Evaluations (per field, confidence threshold 0)")
        per_version: dict[str, dict[str, dict[str, float | None]]] = {"A": {}, "B": {}}
        for label in ("A", "B"):
            print(f"\n  {label}  {procs[label].get('displayName')}")
            evaluated = [v for v in versions[label] if v.get("latestEvaluation", {}).get("evaluation")]
            if not evaluated:
                print("    no evaluation on any version (console: 'Run evaluation first')")
            for v in evaluated:
                vid = v["name"].split("/")[-1]
                print(f"\n    version {vid}  ({v.get('displayName')})")
                try:
                    ev, per_field = show_evaluation(api, v["latestEvaluation"])
                    per_version[label][vid] = per_field
                    with open(os.path.join(args.out, f"{label}.eval.{vid}.json"), "w", encoding="utf-8") as fh:
                        json.dump(ev, fh, indent=2)
                except ApiError as e:
                    print(f"    cannot read evaluation: {e}")
                except Exception as e:
                    print(f"    unexpected error while reading the evaluation: {e!r}")
        shared = sorted(set(per_version["A"]) & set(per_version["B"]))
        for vid in shared:
            print(f"\n  side by side, version {vid} (F1 fuzzy per field):")
            fa, fb = per_version["A"][vid], per_version["B"][vid]
            rows = []
            for f in sorted(set(fa) | set(fb)):
                a, b = fa.get(f), fb.get(f)
                delta = f"{(b - a) * 100:+.1f} pts" if (a is not None and b is not None) else ""
                rows.append([f, f"{a:.3f}" if a is not None else "-", f"{b:.3f}" if b is not None else "-", delta])
            table(["field", "A", "B", "B - A"], rows)
        if not shared:
            print(
                "\n  no version was evaluated on both processors, so the console numbers are not comparable "
                "(different test sets and labels). Run the evaluation of the same version on both, or use --probe."
            )

    if not args.no_audit:
        section("7. Audit log: who changed these processors, and how they were called")
        for label in ("A", "B"):
            try:
                audit_section(
                    api.token,
                    names[label].split("/")[1],
                    names[label],
                    label,
                    procs[label].get("displayName", ""),
                    args.audit_days,
                )
            except Exception as e:
                print(f"  {label}: unexpected error in the audit section: {e!r}")

    if probe_docs:
        section(
            f"8. Probe: {len(probe_docs)} document(s)  "
            f"(A version {ver['A']}, B version {ver['B']}), no process options"
        )
        cache: dict = {}  # uri -> {label: summary or None}

        def fetch(uri, mime, label, side, schema_override=None):
            r = cache.setdefault(uri, {})
            if label in r:
                return r
            try:
                r[label] = probe(api, names[side], ver[side], uri, mime, schema_override=schema_override)
            except ApiError as e:
                r[label] = None
                print(f"  {uri}  {label}: {e}")
            except Exception as e:
                r[label] = None
                print(f"  {uri}  {label}: unexpected error {e!r}")
            return r

        def run_plain(uri, mime):
            fetch(uri, mime, "A", "A")
            return fetch(uri, mime, "B", "B")

        probe_summary = probe_report(probe_docs, run_plain, "A", "B", args.show_values)
        print(f"\n  PROBE RESULT: {probe_summary}")
        if args.swap_schema and "A" in schemas and "B" in schemas:
            print("\n  swapped schemas: A with B's schema, B with A's schema (processOptions.schemaOverride)")

            def run_swapped(uri, mime):
                fetch(uri, mime, "A(B-schema)", "A", schemas["B"])
                return fetch(uri, mime, "B(A-schema)", "B", schemas["A"])

            print(
                "\n  A with B's schema  vs  B with its own schema  "
                "(same schema, different processor -> shows what the processor itself adds):"
            )
            s1 = probe_report(probe_docs, run_swapped, "A(B-schema)", "B", args.show_values)
            print(f"  -> {s1}")
            print("\n  B with A's schema  vs  A with its own schema:")
            s2 = probe_report(probe_docs, run_swapped, "B(A-schema)", "A", args.show_values)
            print(f"  -> {s2}")

    if args.migration:
        section("9. Migration check: is B a faithful copy of A?")
        checks, infos = [], []
        checks.append((
            "processor type equal",
            procs["A"].get("type") == procs["B"].get("type"),
            f"A {procs['A'].get('type')} / B {procs['B'].get('type')}",
        ))
        if schemas_identical is None:
            checks.append(("schema identical", False, "one of the schemas could not be read"))
        else:
            checks.append((
                "schema identical (fields, types, occurrence, method, descriptions, order)",
                schemas_identical,
                f"{len(flat['A'][1])} fields in A, {len(flat['B'][1])} in B",
            ))
        by_id = {lab: {v["name"].split("/")[-1]: v for v in versions[lab]} for lab in ("A", "B")}
        src_id = args.version_a or (procs["A"].get("defaultProcessorVersion") or "").split("/")[-1]
        src = by_id["A"].get(src_id)
        dst_id = (procs["B"].get("defaultProcessorVersion") or "").split("/")[-1]
        dst = by_id["B"].get(dst_id)
        checks.append((
            f"source version {src_id} exists on A",
            src is not None,
            src.get("displayName", "") if src else "not found on A",
        ))
        checks.append((
            f"B default version {dst_id or '-'} is deployed",
            bool(dst) and dst.get("state") == "DEPLOYED",
            f"state {dst.get('state')}" if dst else "no default version on B",
        ))
        if src and dst:
            if src_id.startswith("pretrained-"):
                checks.append(("B default is the same pretrained version", dst_id == src_id, f"B default {dst_id}"))
            else:
                checks.append((
                    "B default has the source version's name",
                    dst.get("displayName") == src.get("displayName"),
                    f"A {src.get('displayName')!r} / B {dst.get('displayName')!r}",
                ))
                checks.append((
                    "B default is a copy, not the pretrained model",
                    dst.get("modelType") == src.get("modelType") and not dst.get("googleManaged"),
                    f"B modelType {dst.get('modelType')}, googleManaged {dst.get('googleManaged', False)}",
                ))
                base = {
                    lab: ((v.get("genAiModelInfo") or {}).get("customGenAiModelInfo") or {})
                    for lab, v in (("A", src), ("B", dst))
                }
                checks.append((
                    "same base model and kind",
                    base["A"] == base["B"],
                    f"A {base['A'].get('customModelType')} on {base['A'].get('baseProcessorVersionId')} / "
                    f"B {base['B'].get('customModelType')} on {base['B'].get('baseProcessorVersionId')}",
                ))
                # the version carries its own frozen schema (the one it was created with) - that is what
                # inference uses; the list call omits it, a GET returns it
                own, infos = {}, []
                for lab, v in (("A", src), ("B", dst)):
                    try:
                        own[lab] = api.call("GET", v["name"]).get("documentSchema") or {}
                    except ApiError as e:
                        print(f"  cannot read the schema of version {lab} ({e})")
                if "A" in own and "B" in own:
                    fa_s, fb_s = flatten_schema(own["A"]), flatten_schema(own["B"])
                    same_fields = fa_s[1] == fb_s[1] and list(fa_s[1]) == list(fb_s[1])
                    checks.append((
                        "version's own schema identical (what inference uses)",
                        same_fields and bool(fa_s[1]),
                        f"{len(fa_s[1])} fields in A's version, {len(fb_s[1])} in B's version",
                    ))
                    for lab in ("A", "B"):
                        if lab in flat:
                            ds_fields, v_fields = flat[lab][1], (fa_s if lab == "A" else fb_s)[1]
                            if not v_fields:
                                infos.append(
                                    f"{lab}'s version has no schema of its own (pretrained model) "
                                    f"- inference uses {lab}'s dataset schema ({len(ds_fields)} fields)"
                                )
                            elif ds_fields == v_fields and list(ds_fields) == list(v_fields):
                                infos.append(f"{lab}'s version was created with the schema {lab} shows today")
                            else:
                                changed = (
                                    sorted(set(ds_fields) ^ set(v_fields))
                                    or sorted(k for k in ds_fields if ds_fields[k] != v_fields.get(k))
                                )
                                infos.append(
                                    f"{lab}'s dataset schema differs from {lab}'s version schema in "
                                    f"{len(changed)} field(s) (schema edited after the version was created; "
                                    f"inference still uses the version's own schema): "
                                    f"{', '.join(changed[:6])}{'…' if len(changed) > 6 else ''}"
                                )
        for name, ok, detail in checks:
            print(f"  [{'PASS' if ok else 'FAIL'}] {name}  - {detail}")
        for line in infos:
            print(f"  info: {line}")
        failed = [c for c in checks if not c[1]]
        print(f"\n  RESULT: {'all checks passed' if not failed else str(len(failed)) + ' check(s) FAILED'}")
        if probe_summary:
            print(
                f"  probe (section 8): {probe_summary.splitlines()[0]} "
                "- with a faithful copy every document shows every field identical"
            )

    section("Files")
    for f in sorted(os.listdir(args.out)):
        print(f"  {os.path.join(args.out, f)}")
    print("\nRead-only run finished. Nothing was created or changed.")


if __name__ == "__main__":
    main()
