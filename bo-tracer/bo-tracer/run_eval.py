"""Run every synthetic case and score it.

  python run_eval.py              # fixture mode: hand-written correct extractions -> tests the engine and checks
  python run_eval.py --live       # live mode: the AI reads the documents (needs OPENROUTER_API_KEY)
  python run_eval.py --live --model <openrouter model id> --runs 2

Writes reports/<mode>/<case>.md and results_<mode>.md.
"""
import argparse
import copy
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bo_tracer.engine import analyse, norm_name, processing_error, BLOCKING, REVIEW   # noqa: E402
from bo_tracer import audit                                             # noqa: E402
from bo_tracer.report import render                                    # noqa: E402
from cases.synthetic_cases import CASES, CASE3                         # noqa: E402


def score(res, expected):
    codes = {f.code for f in res.flags}
    actionable = {f.code for f in res.flags if f.code in BLOCKING | REVIEW}
    problems = []
    if sorted(res.owners) != sorted(expected["owners"]):
        problems.append(f"owners {res.owners} != expected {expected['owners']}")
    if sorted(res.unresolved) != sorted(expected["unresolved"]):
        problems.append(f"unresolved {res.unresolved} != expected {expected['unresolved']}")
    missing = set(expected["flags"]) - codes
    if missing:
        problems.append(f"missing flags {sorted(missing)}")
    extra = actionable - set(expected["flags"])
    if extra:
        problems.append(f"unexpected flags {sorted(extra)}")
    if res.status != expected["status"]:
        problems.append(f"status '{res.status}' != '{expected['status']}'")
    return problems


def link_key(l):
    return (norm_name(l.get("holder", "")), norm_name(l.get("held", "")), l.get("kind"),
            None if l.get("pct") is None else round(float(l["pct"]), 4))


def link_scores(gold, got):
    g = {(d,) + link_key(l) for d, ex in gold.items() for l in ex["links"]}
    p = {(d,) + link_key(l) for d, ex in got.items() for l in ex["links"]}
    tp = len(g & p)
    return tp, len(p), len(g)


# ---------------------------------------------------------------- planted faults (guardrail tests)
def faults():
    out = []

    c = copy.deepcopy(CASE3)                       # F1: AI invents a link with a made-up quote
    c["gold"]["orion_shareholders"]["links"].append(
        {"holder": "Nikhil Varma", "held": "Orion Traders Private Limited", "kind": "equity", "pct": 15,
         "quote": "Nikhil Varma (PAN HIJPV8901J) - 1,500 equity shares - 15%"})
    out.append(("F1", "AI invents a shareholding (quote not in document)", c,
                {"owners": ["Arjun Shah", "Meera Pillai", "Nikhil Varma"], "unresolved": [],
                 "flags": ["QUOTE_FAILED"], "status": "EVIDENCE VALIDATION FAILED"}))

    c = copy.deepcopy(CASE3)                       # F2: AI misreads 30% as 40%, real quote
    c["gold"]["kestrel_partners"]["links"][0]["pct"] = 40
    out.append(("F2", "AI misreads Arjun's 30% as 40%", c,
                {"owners": ["Meera Pillai", "Nikhil Varma"], "unresolved": [],
                 "flags": ["NUMBER_MISMATCH", "GAP_BLOCKING"], "status": "EVIDENCE VALIDATION FAILED"}))

    c = copy.deepcopy(CASE3)                       # F3: AI misses Nikhil entirely
    c["gold"]["kestrel_partners"]["links"].pop(2)
    out.append(("F3", "AI misses a 60% partner", c,
                {"owners": ["Arjun Shah", "Meera Pillai"], "unresolved": [],
                 "flags": ["GAP_BLOCKING"], "status": "INSUFFICIENT INFORMATION"}))

    c = copy.deepcopy(CASE3)                       # F4: AI drops Meera's PAN in the LLP document
    ents = c["gold"]["kestrel_partners"]["entities"]
    ents[2] = {"name": "Meera Pillai", "type": "person", "id": None, "quote": "Meera Pillai"}
    out.append(("F4", "AI drops Meera's PAN in one document", c,
                {"owners": ["Arjun Shah", "Meera Pillai", "Nikhil Varma"], "unresolved": [],
                 "flags": ["NAME_ONLY_MATCH"], "status": "IDENTITY MATCH REQUIRES REVIEW"}))

    c = copy.deepcopy(CASE3)                       # F5: AI calls the listed company an ordinary company
    c["gold"]["orion_shareholders"]["entities"][3]["type"] = "company"
    out.append(("F5", "AI misses that Delta is listed", c,
                {"owners": ["Arjun Shah", "Meera Pillai", "Nikhil Varma"], "unresolved": [],
                 "flags": ["GAP_BLOCKING"], "status": "INSUFFICIENT INFORMATION"}))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--model", default=None)
    ap.add_argument("--runs", type=int, default=2)
    ap.add_argument("--cases", default="", help="comma-separated case ids, e.g. 01,03")
    args = ap.parse_args()
    mode = "live" if args.live else "fixture"
    os.makedirs(f"reports/{mode}", exist_ok=True)
    chosen = [c for c in CASES if not args.cases or c["id"] in args.cases.split(",")]

    if args.live and not os.environ.get("OPENROUTER_API_KEY"):
        print("Live mode needs OPENROUTER_API_KEY in the environment (fixture mode needs nothing).", file=sys.stderr)
        sys.exit(2)
    rows, tp_all, p_all, g_all = [], 0, 0, 0
    for case in chosen:
        extra = []
        if args.live:
            from bo_tracer.extract import extract_case, DEFAULT_MODEL, ExtractionError
            try:
                extraction, extra = extract_case(case, args.model or DEFAULT_MODEL, args.runs)
            except ExtractionError as e:
                res = processing_error(case, f"EXTRACTION_FAILED: {e}")
                with open(f"reports/{mode}/{case['id']}.md", "w") as f:
                    f.write(render(case, res))
                rows.append((case["id"], case["title"], [], res.status, [f"processing error: {e}"]))
                continue
            tp, p, g = link_scores(case["gold"], extraction)
            tp_all, p_all, g_all = tp_all + tp, p_all + p, g_all + g
        else:
            extraction = case["gold"]
        res = analyse(case, extraction, extra_flags=extra)
        with open(f"reports/{mode}/{case['id']}.md", "w") as f:
            f.write(render(case, res))
        with open(f"reports/{mode}/{case['id']}.audit.json", "w") as f:
            f.write(audit.dumps(audit.build(case, extraction, res, mode)))
        probs = score(res, case["expected"])
        rows.append((case["id"], case["title"], res.owners, res.status, probs))

    frows = []
    if not args.live:
        for fid, title, case, exp in faults():
            res = analyse(case, case["gold"])
            with open(f"reports/{mode}/{fid}.md", "w") as f:
                f.write(render(case, res))
            with open(f"reports/{mode}/{fid}.audit.json", "w") as f:
                f.write(audit.dumps(audit.build(case, case["gold"], res, "fixture-fault")))
            frows.append((fid, title, res.owners, res.status, score(res, exp)))

    lines = [f"# Results ({mode} mode)", ""]
    if not args.live:
        lines += ["*Fixture mode: hand-written correct extractions. Tests the deterministic engine and checks, not the AI reading step. All data synthetic.*", ""]
    if args.live:
        lines += ["**Live mode: the AI read the synthetic documents. These are synthetic-data results, not results on real documents.**", "",
                  f"Model: `{args.model or os.environ.get('OPENROUTER_MODEL', 'default')}`, runs per document: {args.runs}", "",
                  f"Link extraction: precision {tp_all}/{p_all}, recall {tp_all}/{g_all}", ""]
    lines += ["| Case | What it tests | Owners found | Status | Result |", "| --- | --- | --- | --- | --- |"]
    for cid, title, owners, status, probs in rows:
        lines.append(f"| {cid} | {title} | {', '.join(owners) or '-'} | {status} | {'PASS' if not probs else 'FAIL: ' + '; '.join(probs)} |")
    if frows:
        lines += ["", "## Planted AI errors (do the checks catch them?)", "",
                  "| Fault | What goes wrong | Owners found | Status | Result |", "| --- | --- | --- | --- | --- |"]
        for fid, title, owners, status, probs in frows:
            lines.append(f"| {fid} | {title} | {', '.join(owners) or '-'} | {status} | {'PASS' if not probs else 'FAIL: ' + '; '.join(probs)} |")
    passed = sum(1 for r in rows + frows if not r[4])
    lines += ["", f"**{passed} of {len(rows) + len(frows)} passed.**"]
    text = "\n".join(lines)
    with open(f"results_{mode}.md", "w") as f:
        f.write(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
