"""A reproducible audit record for one KYC file.

Contains: document hashes (not the documents), the extraction as received, every
validation outcome, identity decisions, ownership calculations per scenario, the
rule applied with its source and verification status, reviewer decisions, and
software/model versions. It never contains API keys. ID numbers appear only as
they already appear in the documents the bank holds; set redact_ids=True to mask them.
"""
from __future__ import annotations

import hashlib
import json
import platform
import re

from .engine import ENGINE_VERSION, Result

_ID = re.compile(r"\b([A-Z]{5})([0-9]{4})([A-Z])\b")


def _mask(obj, on: bool):
    if not on:
        return obj
    if isinstance(obj, str):
        return _ID.sub(lambda m: m.group(1)[:2] + "XXX" + "XXXX" + m.group(3), obj)
    if isinstance(obj, list):
        return [_mask(x, on) for x in obj]
    if isinstance(obj, dict):
        return {k: _mask(v, on) for k, v in obj.items()}
    return obj


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build(case: dict, extraction: dict, res: Result, mode: str, reviews: dict | None = None, redact_ids: bool = False) -> dict:
    meta = {d: (ex.get("_meta") if isinstance(ex, dict) else None) for d, ex in (extraction or {}).items()}
    record = {
        "case_id": case["id"],
        "customer": case["customer"],
        "assessed_on": res.rule_detail.get("assessed_on"),
        "software": {"engine_version": ENGINE_VERSION, "python": platform.python_version()},
        "extraction_mode": mode,
        "extraction_meta": meta,
        "documents": [{"doc_id": d, "title": v.get("title"), "date": v["date"], "sha256": sha256(v["text"])}
                      for d, v in case["documents"].items()],
        "extraction_received": {d: {"entities": ex.get("entities", []), "links": ex.get("links", [])}
                                for d, ex in (extraction or {}).items() if isinstance(ex, dict)},
        "validation": {
            "accepted_links": [{k: l[k] for k in ("doc", "holder", "held", "kind", "pct", "quote", "location", "verification")
                                if k in l} for l in res.documented],
            "rejected": res.rejected,
        },
        "identity_decisions": res.identity_log,
        "rule": res.rule_detail,
        "scenarios": [{"choice": s["choice"], "overallocated": s.get("overallocated", False),
                       "holdings": {res.name(h): {res.name(k): round(v, 10) for k, v in hs.items()} for h, hs in s["holdings"].items()},
                       "economic_stakes": {res.name(k): round(v, 10) for k, v in sorted(s["economic"].items())},
                       "control_method_stakes": {res.name(k): round(v, 10) for k, v in sorted(s["control"].items())}}
                      for s in res.scenarios],
        "flags": [{"code": f.code, "category": f.category, "message": f.message} for f in res.flags],
        "outcome": {"status": res.status, "open_issues": res.open_issues,
                    "beneficial_owners": res.owners, "unresolved": res.unresolved},
        "reviewer_decisions": reviews or {},
        "final_approval": "pending: only an authorised compliance officer can approve this file",
    }
    return _mask(record, redact_ids)


def dumps(record: dict) -> str:
    return json.dumps(record, indent=2, sort_keys=True, default=sorted, ensure_ascii=False)
