"""Deterministic core. Everything that must be exact lives here, not in the model.

Input:  a case (documents + customer) and an extraction (what the AI read from
        each document: entities and links, each with a verbatim quote).
Output: verified links, beneficial owners, effective stakes, flags, a file status.

Flow:   validate schema -> verify evidence -> resolve identities -> check direction
        -> pick latest/conflicting versions -> gap check -> solve stakes
        -> apply dated rule -> flags -> status.
Nothing that failed a check enters the ownership graph.
"""
from __future__ import annotations

import itertools
import re
from dataclasses import dataclass, field
from datetime import date

from .rules import NEAR_MISS_FRACTION, TERMINAL_TYPES, RuleMissing, rule_for, RULES_VERSION

ENGINE_VERSION = "0.2.0"

EQUITY = "equity"                       # shares, capital or profit share
CONTROL_KINDS = {"appoint_directors", "veto"}
SHARE_CLASS = "special_voting"
ROLES = {"director", "managing_director"}
LINK_KINDS = {EQUITY, SHARE_CLASS, *CONTROL_KINDS, *ROLES}
ENTITY_TYPES = {"person", "company", "llp", "trust", "listed", "partnership"}

# Status categories in order of precedence. The file's status is the first one with an open issue.
CATEGORIES: list[tuple[str, set[str]]] = [
    ("PROCESSING ERROR", {"RULE_MISSING", "EXTRACTION_FAILED", "CALCULATION_FAILED"}),
    ("EVIDENCE VALIDATION FAILED", {"QUOTE_FAILED", "NUMBER_MISMATCH", "SCHEMA_INVALID", "DIRECTION_INVALID",
                                    "RUNS_DISAGREE", "INJECTION_SUSPECTED"}),
    ("INSUFFICIENT INFORMATION", {"GAP_BLOCKING", "MISSING_CUSTOMER"}),
    ("OWNERSHIP STRUCTURE UNRESOLVED", {"CONTRADICTION", "OVERALLOCATED", "CYCLE_UNSOLVABLE"}),
    ("IDENTITY MATCH REQUIRES REVIEW", {"NAME_ONLY_MATCH", "NAME_COLLISION", "AMBIGUOUS_NAME", "UNKNOWN_TYPE"}),
    ("REGULATORY ASSESSMENT REQUIRES REVIEW", {"CONTROL_REVIEW", "SHARE_CLASS", "CYCLE", "NEAR_THRESHOLD",
                                               "CONTROL_METHOD_ONLY", "NO_BO_SMO", "RULE_INTERPRETATION"}),
]
READY = "READY FOR OFFICER APPROVAL"
INFO = {"SUPERSEDED", "GAP_MINOR", "IDENTITY_CONFIRMED", "IDENTITY_REJECTED"}
CATEGORY_OF = {code: cat for cat, codes in CATEGORIES for code in codes}
# kept for callers of the previous version
BLOCKING = set().union(*(codes for cat, codes in CATEGORIES[:4]))
REVIEW = set().union(*(codes for cat, codes in CATEGORIES[4:]))

EPS = 1e-9
INJECTION_PATTERNS = re.compile(
    r"ignore (?:all |any |the )?(?:previous|prior|above)|disregard (?:the )?(?:previous|prior|above)|"
    r"(?:note|instruction|message)s? (?:to|for) (?:the )?(?:ai|assistant|model|system)|system prompt|"
    r"you are (?:now )?(?:an? )?(?:ai|assistant|chatgpt|claude)", re.I)


@dataclass
class Flag:
    code: str
    message: str
    subject: str = ""

    @property
    def category(self) -> str:
        return CATEGORY_OF.get(self.code, "INFO")

    @property
    def level(self) -> str:
        return "blocking" if self.code in BLOCKING else "review" if self.code in REVIEW else "info"


@dataclass
class Result:
    customer: str
    threshold: float = 0.0
    rule: str = ""
    rule_detail: dict = field(default_factory=dict)
    flags: list[Flag] = field(default_factory=list)
    documented: list[dict] = field(default_factory=list)      # verified links (the only ones in the graph)
    rejected: list[dict] = field(default_factory=list)        # failed checks, original values preserved
    entities: dict = field(default_factory=dict)              # key -> {name, type, docs}
    identity_log: list[dict] = field(default_factory=list)    # why records were matched or kept apart
    scenarios: list[dict] = field(default_factory=list)       # one per contradiction choice
    owners: list[str] = field(default_factory=list)           # beneficial owners in every scenario
    unresolved: list[str] = field(default_factory=list)       # owners in some scenarios, or via unresolved structure
    status: str = ""
    open_issues: dict = field(default_factory=dict)           # status category -> codes

    def name(self, key: str) -> str:
        if key.startswith("UNACCOUNTED:"):
            return f"Unaccounted share of {self.name(key.split(':', 1)[1])}"
        return self.entities.get(key, {}).get("name", key)

    def flag(self, code, message, subject=""):
        if not any(f.code == code and f.subject == subject and f.message == message for f in self.flags):
            self.flags.append(Flag(code, message, subject))

    def reject(self, item: dict, doc_id: str, reason: str, code: str, message: str):
        self.rejected.append({"original": dict(item), "doc": doc_id, "reason": reason, "code": code})
        self.flag(code, message, str(item.get("holder", item.get("name", ""))))


# ----------------------------------------------------------------- text helpers
def norm_text(s: str) -> str:
    """Normalise only presentation: case, whitespace, curly quotes, dashes, and
    words split by a line-end hyphen. Letters and digits are never changed."""
    s = str(s)
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    s = s.replace("–", "-").replace("—", "-").replace(" ", " ")
    s = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", s)
    return re.sub(r"\s+", " ", s).strip().lower()


_SUFFIXES = {"private", "pvt", "limited", "ltd", "llp", "the", "mr", "ms", "mrs", "shri", "smt"}


def norm_name(s: str) -> str:
    words = re.sub(r"[^\w\s]", " ", str(s).lower()).split()
    return " ".join(w for w in words if w not in _SUFFIXES)


def numbers_in(s: str) -> list[float]:
    return [float(x) for x in re.findall(r"\d+(?:\.\d+)?", s.replace(",", ""))]


_PCT = re.compile(r"(\d+(?:\.\d+)?)\s*(?:%|per\s?cent\b|percent\b)")


def percentages_in(s: str) -> list[float]:
    """Numbers written AS percentages. A share count ("800 shares") is not one."""
    return [float(x) for x in _PCT.findall(norm_text(s).replace(",", ""))]


def locate(doc_text: str, quote: str) -> str:
    """Line number of the quote, so an officer can find it."""
    q = norm_text(quote)
    lines = doc_text.split("\n")
    for i, line in enumerate(lines, 1):
        if norm_text(line) and (q.startswith(norm_text(line)[:30]) or norm_text(line).find(q[:30]) >= 0):
            return f"line {i}"
    return "location not found by line"


# ----------------------------------------------------------------- 1. schema + evidence
def _schema_problem_link(l) -> str | None:
    if not isinstance(l, dict):
        return "link is not an object"
    for k in ("holder", "held", "kind", "quote"):
        if not isinstance(l.get(k), str) or not l.get(k).strip():
            return f"missing or empty '{k}'"
    if l["kind"] not in LINK_KINDS:
        return f"unknown kind '{l['kind']}'"
    pct = l.get("pct")
    if l["kind"] == EQUITY:
        if pct is None:
            return "equity link without a percentage"
        if isinstance(pct, bool) or not isinstance(pct, (int, float)):
            return f"percentage is not a number: {pct!r}"
        if not (0 < pct <= 100):
            return f"percentage outside (0, 100]: {pct}"
    elif pct is not None:
        return f"percentage given for a non-equity link: {pct!r}"
    if norm_name(l["holder"]) == norm_name(l["held"]) and l.get("holder_id") == l.get("held_id"):
        return "holder and held are the same"
    return None


def _schema_problem_entity(e) -> str | None:
    if not isinstance(e, dict):
        return "entity is not an object"
    if not isinstance(e.get("name"), str) or not e["name"].strip():
        return "missing name"
    if e.get("type") not in ENTITY_TYPES:
        return f"unknown entity type {e.get('type')!r}"
    if not isinstance(e.get("quote"), str) or not e["quote"].strip():
        return "missing quote"
    return None


def verify(case: dict, extraction: dict, res: Result) -> dict:
    """Keep only well-formed entities and links whose quote is really in the
    document and whose percentage is really written in that quote as a percentage.
    Everything else is quarantined with its original values."""
    clean = {}
    for doc_id, ex in (extraction or {}).items():
        doc = case["documents"].get(doc_id)
        if doc is None or not isinstance(ex, dict):
            continue
        text = norm_text(doc["text"])
        ents, links = [], []
        for e in ex.get("entities", []) or []:
            prob = _schema_problem_entity(e)
            if prob:
                res.reject(e if isinstance(e, dict) else {"raw": e}, doc_id, prob, "SCHEMA_INVALID", f"Entity in {doc_id}: {prob}")
            elif norm_text(e["quote"]) not in text:
                res.reject(e, doc_id, "entity quote not in document", "QUOTE_FAILED", f"Entity '{e['name']}' quote not found in {doc_id}")
            else:
                ents.append(e)
        for l in ex.get("links", []) or []:
            prob = _schema_problem_link(l)
            if prob:
                res.reject(l if isinstance(l, dict) else {"raw": l}, doc_id, prob, "SCHEMA_INVALID", f"Link in {doc_id}: {prob}")
                continue
            if norm_text(l["quote"]) not in text:
                res.reject(l, doc_id, "quote not in document", "QUOTE_FAILED", f"Link {l['holder']} -> {l['held']} quote not found in {doc_id}")
                continue
            if l["kind"] == EQUITY and not any(abs(p - float(l["pct"])) < 1e-6 for p in percentages_in(l["quote"])):
                res.reject(l, doc_id, "percentage not written as a percentage in the quote", "NUMBER_MISMATCH",
                           f"{l['holder']} -> {l['held']}: {l['pct']}% is not stated as a percentage in the quoted text ({doc_id})")
                continue
            first = (norm_name(l["holder"]).split() or [""])[0]
            if l["kind"] == EQUITY and first not in norm_text(l["quote"]):
                # a real quote about someone else's stake is not evidence of this holder's stake
                res.reject(l, doc_id, "holder not named in the quote", "QUOTE_FAILED",
                           f"{l['holder']} is not named in the quote offered for their stake ({doc_id})")
                continue
            links.append({**l, "location": locate(doc["text"], l["quote"]), "doc_type": doc.get("title", ""),
                          "verification": "quote and percentage verified" if l["kind"] == EQUITY else "quote verified",
                          "basis": "stated in document"})
        clean[doc_id] = {"entities": ents, "links": links}
    return clean


def scan_for_injection(case: dict, res: Result):
    """Documents are untrusted data. Instruction-like text is shown to the officer;
    it never changes what the system does."""
    for doc_id, d in case["documents"].items():
        m = INJECTION_PATTERNS.search(d["text"])
        if m:
            res.flag("INJECTION_SUSPECTED", f"{doc_id} contains instruction-like text (\"{m.group(0)}\"); treated as data, review the document", doc_id)


# ----------------------------------------------------------------- 2. resolve identities
def resolve(case: dict, clean: dict, res: Result, reviews: dict | None = None) -> list[dict]:
    """Same person/company across documents: match on ID numbers first.
    Name-only matches are tentative and flagged unless a reviewer confirmed them;
    a reviewer can also reject one, which keeps the records apart."""
    decisions = (reviews or {}).get("identity", {})
    ents = res.entities
    local: dict[str, dict[str, set]] = {}

    def add(key, name, etype, doc_id):
        rec = ents.setdefault(key, {"name": name, "type": etype, "docs": set()})
        rec["docs"].add(doc_id)
        if rec["type"] in (None, "unknown") and etype:
            rec["type"] = etype

    for doc_id, ex in clean.items():
        local[doc_id] = {}
        for e in ex["entities"]:
            key = e.get("id") or f"NAME:{norm_name(e['name'])}"
            add(key, e["name"], e.get("type"), doc_id)
            local[doc_id].setdefault(norm_name(e["name"]), set()).add(key)

    cust_key = case["customer"]["id"]
    if cust_key not in ents:
        res.flag("MISSING_CUSTOMER", "No document identifies the customer by its ID")
        add(cust_key, case["customer"]["name"], case["customer"]["type"], "case")

    by_name: dict[str, list[str]] = {}
    for k, v in ents.items():
        if not k.startswith("NAME:"):
            by_name.setdefault(norm_name(v["name"]), []).append(k)
            if len(v["docs"]) > 1:
                res.identity_log.append({"key": k, "name": v["name"], "decision": "matched by identifier",
                                         "reason": f"same ID in {sorted(v['docs'])}", "deterministic": True})
    for n, keys in by_name.items():
        if len(keys) > 1:
            res.flag("NAME_COLLISION", f"Different ID numbers share the name '{ents[keys[0]]['name']}': kept as separate records", ents[keys[0]]["name"])
            res.identity_log.append({"key": keys, "name": ents[keys[0]]["name"], "decision": "kept separate",
                                     "reason": "same name, different identifiers", "deterministic": True})
    merge = {}
    for k in list(ents):
        if not k.startswith("NAME:"):
            continue
        cands = by_name.get(k[5:], [])
        verdict = decisions.get(k)
        entry = {"key": k, "name": ents[k]["name"], "candidates": cands, "deterministic": False}
        if len(cands) == 1 and verdict != "reject":
            merge[k] = cands[0]
            if verdict == "confirm":
                res.flag("IDENTITY_CONFIRMED", f"Reviewer confirmed '{ents[k]['name']}' (no ID) is {cands[0]}", ents[k]["name"])
                entry.update(decision="merged (reviewer confirmed)", reason="name match confirmed by reviewer")
            else:
                res.flag("NAME_ONLY_MATCH", f"'{ents[k]['name']}' (no ID) tentatively matched by name to {cands[0]}; confirm or reject", ents[k]["name"])
                entry.update(decision="merged tentatively", reason="exact normalised name, one candidate with an ID", review="pending")
            ents[cands[0]]["docs"] |= ents[k]["docs"]
            del ents[k]
        elif len(cands) == 1:
            res.flag("IDENTITY_REJECTED", f"Reviewer rejected matching '{ents[k]['name']}' to {cands[0]}; kept separate", ents[k]["name"])
            entry.update(decision="kept separate (reviewer rejected)", reason="reviewer decision")
        elif len(cands) > 1:
            res.flag("AMBIGUOUS_NAME", f"'{ents[k]['name']}' (no ID) could be any of {cands}; not merged", ents[k]["name"])
            entry.update(decision="not merged", reason="several candidates with IDs")
        else:
            entry.update(decision="name-only record", reason="no record with an ID shares this name")
        res.identity_log.append(entry)

    links = []
    for doc_id, ex in clean.items():
        for l in ex["links"]:
            keys, ok = [], True
            for side in ("holder", "held"):
                k = l.get(f"{side}_id")
                if not k:
                    cand = local[doc_id].get(norm_name(l[side]), set())
                    if len(cand) > 1:
                        res.reject(l, doc_id, "ambiguous name", "AMBIGUOUS_NAME", f"'{l[side]}' matches more than one ID in {doc_id}; link not used")
                        ok = False
                        break
                    k = next(iter(cand)) if cand else f"NAME:{norm_name(l[side])}"
                k = merge.get(k, k)
                if k not in ents:
                    add(k, l[side], "unknown", doc_id)
                keys.append(k)
            if not ok:
                continue
            held_type = ents[keys[1]]["type"]
            if held_type == "person":
                res.reject(l, doc_id, f"'{l['held']}' is a person and cannot be owned", "DIRECTION_INVALID",
                           f"Link {l['holder']} -> {l['held']} points the wrong way ({doc_id}); not used")
                continue
            links.append({**l, "holder_key": keys[0], "held_key": keys[1], "doc": doc_id,
                          "date": case["documents"][doc_id]["date"]})
    for k, v in ents.items():
        if v["type"] in (None, "unknown"):
            res.flag("UNKNOWN_TYPE", f"Could not tell whether '{v['name']}' is a person or an entity", v["name"])
    res.documented = links
    return links


# ----------------------------------------------------------------- 3. versions & contradictions
def ownership_versions(links: list[dict], res: Result) -> dict[str, list[dict]]:
    """For each entity, the latest-dated shareholding statement(s). Older statements
    are superseded; disagreeing statements of the same date become separate scenarios."""
    per: dict[str, dict[str, dict]] = {}
    for l in links:
        if l["kind"] != EQUITY:
            continue
        d = per.setdefault(l["held_key"], {}).setdefault(l["doc"], {"date": l["date"], "holdings": {}})
        d["holdings"][l["holder_key"]] = d["holdings"].get(l["holder_key"], 0) + float(l["pct"]) / 100
    options = {}
    for held, docs in per.items():
        latest = max(d["date"] for d in docs.values())
        for doc_id, d in docs.items():
            if d["date"] < latest:
                res.flag("SUPERSEDED", f"{doc_id} ({d['date']}) on {res.name(held)} is replaced by a later document", res.name(held))
        distinct = []
        for doc_id, d in docs.items():
            if d["date"] != latest:
                continue
            sig = tuple(sorted((k, round(v, 6)) for k, v in d["holdings"].items()))
            if all(sig != s for s, _, _ in distinct):
                distinct.append((sig, doc_id, d["holdings"]))
        if len(distinct) > 1:
            res.flag("CONTRADICTION", f"Documents dated {latest} disagree on who owns {res.name(held)}: "
                     + " vs ".join(doc for _, doc, _ in distinct), res.name(held))
        options[held] = [{"doc": doc, "holdings": h} for _, doc, h in distinct]
    return options


# ----------------------------------------------------------------- 4. maths
def _solve(a: list[list[float]], b: list[float]) -> list[float]:
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(m[r][c]))
        if abs(m[p][c]) < 1e-12:
            raise ValueError("Ownership system is singular (100% circular holding?)")
        m[c], m[p] = m[p], m[c]
        for r in range(n):
            if r != c and m[r][c]:
                f = m[r][c] / m[c][c]
                m[r] = [x - f * y for x, y in zip(m[r], m[c])]
    return [m[i][n] / m[i][i] for i in range(n)]


def _effective(holdings: dict, customer: str, types: dict, control: bool) -> dict[str, float]:
    """Integrated stake of every terminal holder in the customer.
    Economic method: multiply along every path, add paths (cycles solved exactly,
    no double counting: each path is counted once through the linear system).
    Control method: a majority holder of an intermediate entity takes all of its stake."""
    w = {held: dict(h) for held, h in holdings.items()}
    if control:
        for held, h in w.items():
            if held == customer:
                continue
            top = max(h.items(), key=lambda kv: kv[1], default=(None, 0))
            if top[1] > 0.5 + EPS:
                w[held] = {top[0]: 1.0}
    inner = [k for k in w if types.get(k) not in TERMINAL_TYPES and not k.startswith("UNACCOUNTED:")]
    if customer not in inner:
        inner.append(customer)
    idx = {k: i for i, k in enumerate(inner)}
    n = len(inner)
    a = [[0.0] * n for _ in range(n)]
    b = [0.0] * n
    for e in inner:
        a[idx[e]][idx[e]] = 1.0
        if e == customer:
            b[idx[e]] = 1.0
            continue
        for held, h in w.items():                 # v(e) = sum_j w(e,j) v(j)
            if held in idx and e in h:
                a[idx[e]][idx[held]] -= h[e]
    v = dict(zip(inner, _solve(a, b)))
    stakes: dict[str, float] = {}
    for held, h in w.items():
        if held not in v:
            continue
        for holder, frac in h.items():
            if holder in v:
                continue
            stakes[holder] = stakes.get(holder, 0.0) + frac * v[held]
    return stakes


def _has_cycle(holdings: dict, types: dict) -> bool:
    graph = {held: [h for h in hs if h in holdings and types.get(h) not in TERMINAL_TYPES]
             for held, hs in holdings.items()}
    seen, stack = set(), set()

    def dfs(n):
        seen.add(n); stack.add(n)
        for m in graph.get(n, []):
            if m in stack or (m not in seen and dfs(m)):
                return True
        stack.discard(n)
        return False
    return any(dfs(n) for n in graph if n not in seen)


def paths_to(holdings: dict, holder: str, customer: str, limit: int = 8) -> list[tuple[list[str], float]]:
    out = []

    def walk(node, path, prod):
        if len(path) > limit:
            return
        for held, h in holdings.items():
            if node in h and held not in path:
                p2, f2 = path + [held], prod * h[node]
                if held == customer:
                    out.append((p2, f2))
                else:
                    walk(held, p2, f2)
    walk(holder, [holder], 1.0)
    return out


# ----------------------------------------------------------------- 5. status
def decide_status(res: Result) -> None:
    res.open_issues = {}
    for f in res.flags:
        if f.category != "INFO":
            res.open_issues.setdefault(f.category, set()).add(f.code)
    res.open_issues = {k: sorted(v) for k, v in res.open_issues.items()}
    for cat, _ in CATEGORIES:
        if cat in res.open_issues:
            res.status = cat
            return
    res.status = READY


# ----------------------------------------------------------------- 6. the whole run
def analyse(case: dict, extraction: dict, on: date | None = None, extra_flags=(), reviews: dict | None = None) -> Result:
    on = on or date.fromisoformat(case.get("as_of", date.today().isoformat()))
    cust = case["customer"]
    res = Result(customer=cust["name"])
    for msg in extra_flags:                       # e.g. two AI runs disagreed, or extraction failed
        code = "EXTRACTION_FAILED" if str(msg).startswith("EXTRACTION_FAILED") else "RUNS_DISAGREE"
        res.flag(code, str(msg))
    try:
        rule, note = rule_for(cust["type"], on)
    except RuleMissing as e:
        res.flag("RULE_MISSING", str(e))
        decide_status(res)
        return res
    res.threshold = rule.threshold
    res.rule = f"rule {rule.rule_id} valid from {rule.valid_from.isoformat()}"
    res.rule_detail = {"rule_id": rule.rule_id, "threshold": rule.threshold, "valid_from": rule.valid_from.isoformat(),
                       "valid_to": rule.valid_to.isoformat() if rule.valid_to else None, "source": rule.source,
                       "verification": rule.verification, "last_checked": rule.last_checked.isoformat(),
                       "note": rule.note, "interpretation": note, "rules_version": RULES_VERSION, "assessed_on": on.isoformat()}
    if note:
        res.flag("RULE_INTERPRETATION", note)
    thr = rule.threshold

    scan_for_injection(case, res)
    clean = verify(case, extraction, res)
    links = resolve(case, clean, res, reviews)
    types = {k: v["type"] for k, v in res.entities.items()}
    customer = cust["id"]

    for l in links:
        if l["kind"] in CONTROL_KINDS:
            res.flag("CONTROL_REVIEW", f"{res.name(l['holder_key'])} has a documented control right over {res.name(l['held_key'])}: \"{l['quote']}\" ({l['doc']}). Ownership below the threshold does not rule out beneficial ownership through control.", res.name(l["holder_key"]))
        elif l["kind"] == SHARE_CLASS:
            res.flag("SHARE_CLASS", f"Special voting rights for {res.name(l['holder_key'])} in {res.name(l['held_key'])}: stakes computed on economic shares only ({l['doc']})", res.name(l["holder_key"]))

    options = ownership_versions(links, res)
    combos = list(itertools.product(*[[(held, o) for o in opts] for held, opts in options.items()])) or [()]
    combos = combos[:64]

    owner_sets, unsure_all = [], set()
    for combo in combos:
        holdings = {held: dict(o["holdings"]) for held, o in combo}
        frontier, seen, overallocated = [customer], set(), False
        while frontier:
            e = frontier.pop()
            if e in seen:
                continue
            seen.add(e)
            if types.get(e) in TERMINAL_TYPES:
                continue
            if e not in holdings:
                holdings[e] = {}
            total = sum(holdings[e].values())
            if total > 1 + 1e-6:
                overallocated = True
                res.flag("OVERALLOCATED", f"Holders of {res.name(e)} add up to {total:.1%}: at least one stated stake is wrong", res.name(e))
            elif total < 1 - 1e-6:
                holdings[e][f"UNACCOUNTED:{e}"] = 1 - total
            frontier += [h for h in holdings[e] if not h.startswith("UNACCOUNTED:")]
        holdings = {k: v for k, v in holdings.items() if k in seen}
        if _has_cycle(holdings, types):
            res.flag("CYCLE", "Circular holding detected; stakes solved exactly as an infinite series", "")
        try:
            econ = _effective(holdings, customer, types, control=False)
            ctrl = _effective(holdings, customer, types, control=True)
        except ValueError as e:
            res.flag("CYCLE_UNSOLVABLE", f"Ownership could not be computed: {e}")
            econ, ctrl = {}, {}
            unsure_all |= {k for k, t in types.items() if t == "person"}
        owners = set()
        for k, s in econ.items():
            if k.startswith("UNACCOUNTED:"):
                if s > thr + EPS:
                    res.flag("GAP_BLOCKING", f"{res.name(k)} is {s:.1%} of the customer: could hide an owner above {thr:.0%}; request documents", res.name(k))
                elif s > 1e-6:
                    res.flag("GAP_MINOR", f"{res.name(k)} is {s:.1%} of the customer (below threshold)", res.name(k))
            elif types.get(k) == "person":
                if s > thr + EPS:
                    owners.add(k)
                elif s >= NEAR_MISS_FRACTION * thr - EPS:
                    res.flag("NEAR_THRESHOLD", f"{res.name(k)} holds {s:.2%}, at or just under {thr:.0%}", res.name(k))
        for k, s in ctrl.items():
            if types.get(k) == "person" and s > thr + EPS and k not in owners:
                res.flag("CONTROL_METHOD_ONLY", f"{res.name(k)} crosses {thr:.0%} only if majority holders are treated as controlling the whole stake ({s:.1%} vs {econ.get(k, 0):.2%} economic)", res.name(k))
        if overallocated:                        # stakes in an impossible structure are not findings
            unsure_all |= owners
            owners = set()
        owner_sets.append(owners)
        res.scenarios.append({"choice": {res.name(h): o["doc"] for h, o in combo}, "holdings": holdings,
                              "economic": econ, "control": ctrl, "overallocated": overallocated,
                              "owners": sorted(res.name(k) for k in owners)})

    always = set.intersection(*owner_sets) if owner_sets else set()
    some = set.union(*owner_sets) if owner_sets else set()
    res.owners = sorted(res.name(k) for k in always - unsure_all)
    res.unresolved = sorted(res.name(k) for k in (some - always) | unsure_all)

    blocking = any(f.code in BLOCKING for f in res.flags)
    if not some and not unsure_all and not blocking:
        smo = sorted({res.name(l["holder_key"]) for l in links if l["kind"] == "managing_director"})
        res.flag("NO_BO_SMO", "No one crosses the threshold; senior managing official: " + (", ".join(smo) or "not named in documents"))
    decide_status(res)
    return res


def processing_error(case: dict, message: str) -> Result:
    """A technical failure is not a compliance finding; say so explicitly."""
    res = Result(customer=case["customer"]["name"])
    res.flag("EXTRACTION_FAILED", message)
    decide_status(res)
    return res
