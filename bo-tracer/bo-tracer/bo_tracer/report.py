"""Turn a Result into a reviewer-facing KYC file. Every finding carries one label:
Documented (quoted from a document and verified), Calculated (computed by code from
documented links), or Unresolved (needs documents or a person's decision)."""
from .engine import CATEGORIES, READY, Result, paths_to

STATUS_MEANING = {
    "PROCESSING ERROR": "A technical step failed (e.g. extraction or a missing rule). This is not a compliance finding; rerun or fix the input.",
    "EVIDENCE VALIDATION FAILED": "Some extracted facts failed their checks and were kept out of the ownership graph. Review them before relying on the result.",
    "INSUFFICIENT INFORMATION": "The documents do not account for enough of the ownership to rule out an unnamed owner.",
    "OWNERSHIP STRUCTURE UNRESOLVED": "The documents contradict each other or describe an impossible structure.",
    "IDENTITY MATCH REQUIRES REVIEW": "A person or company could not be matched with certainty across documents.",
    "REGULATORY ASSESSMENT REQUIRES REVIEW": "Ownership is computed, but control rights, near-threshold stakes or method choices need a decision.",
    READY: "All checks passed. An authorised officer still approves; the system never clears a file itself.",
}

FOLLOW_UP = {
    "GAP_BLOCKING": "Request the missing shareholder or partner records for {s}.",
    "MISSING_CUSTOMER": "Request a document that identifies the customer by its CIN.",
    "CONTRADICTION": "Ask the customer which document is current for {s}, with evidence.",
    "OVERALLOCATED": "Ask the customer to reconcile the shareholding of {s}, which exceeds 100%.",
    "QUOTE_FAILED": "Check the rejected extraction for {s} against the document by hand.",
    "NUMBER_MISMATCH": "Check the stated percentage for {s} against the document by hand.",
    "SCHEMA_INVALID": "Re-run extraction or record the fact manually; the extracted item was malformed.",
    "DIRECTION_INVALID": "Check who holds whom in the rejected link for {s}.",
    "NAME_ONLY_MATCH": "Confirm or reject that the record for {s} without an ID is the same person.",
    "NAME_COLLISION": "Confirm that the records named {s} are different people (different IDs).",
    "AMBIGUOUS_NAME": "Identify which {s} is meant; obtain an ID number.",
    "CONTROL_REVIEW": "Decide whether {s}'s control right makes them a beneficial owner.",
    "SHARE_CLASS": "Assess voting control for {s} given the special share class.",
    "NEAR_THRESHOLD": "Consider whether {s}'s stake just under the threshold warrants enhanced checks.",
    "CONTROL_METHOD_ONLY": "Apply the bank's policy on counting indirect stakes to {s}.",
    "INJECTION_SUSPECTED": "Read {s} yourself: it contains instruction-like text.",
    "RUNS_DISAGREE": "Two extraction runs disagreed; check the disputed fact by hand.",
    "CYCLE": "Review the circular holding; confirm the structure is genuine.",
    "NO_BO_SMO": "Record the senior managing official as beneficial owner, per the rules.",
}


def _pct(x: float) -> str:
    return f"{x * 100:.2f}%".replace(".00%", "%")


def render(case: dict, res: Result) -> str:
    rd = res.rule_detail
    out = [f"# KYC beneficial-ownership file: {res.customer}", "",
           f"*Synthetic case {case['id']}: {case['title']}. Not a real company or person.*", "",
           f"**Status: {res.status}**  ", STATUS_MEANING.get(res.status, ""), ""]
    if rd:
        out += [f"**Rule applied:** {rd['rule_id']}: owner if stake is more than {_pct(rd['threshold'])}, valid from {rd['valid_from']}"
                f"{' to ' + rd['valid_to'] if rd.get('valid_to') else ''}, assessed on {rd['assessed_on']} (rules version {rd['rules_version']}).  ",
                f"Source: {rd['source']}  ", f"Verification: **{rd['verification']}** (last checked {rd['last_checked']})."
                + (f"  \nNote: {rd['note']}" if rd.get("note") else "") + (f"  \nInterpretation: {rd['interpretation']}" if rd.get("interpretation") else ""), ""]

    out += ["## Beneficial owners (by ownership)", ""]
    if res.status != READY:
        out += ["*Supported by verified evidence so far. The file is not ready, so this list may change.*", ""]
    out += [f"- **{o}**" for o in res.owners] or ["- None established above the threshold from verified evidence"]
    if res.unresolved:
        out += ["", "Possible owners that the evidence cannot settle:", ""] + [f"- {o}: **Unresolved**" for o in res.unresolved]
    controls = [f for f in res.flags if f.code in ("CONTROL_REVIEW", "SHARE_CLASS")]
    if controls:
        out += ["", "## Documented control indicators (not ownership)", ""] + [f"- {f.message}" for f in controls]
    out.append("")

    out += ["## Findings", "", "| Finding | Basis | Label |", "| --- | --- | --- |"]
    for l in res.documented:
        what = {"equity": f"{res.name(l['holder_key'])} holds {l['pct']}% of {res.name(l['held_key'])}",
                "appoint_directors": f"{res.name(l['holder_key'])} can appoint directors of {res.name(l['held_key'])}",
                "veto": f"{res.name(l['holder_key'])} has a veto over {res.name(l['held_key'])}",
                "special_voting": f"{res.name(l['holder_key'])} has special voting rights in {res.name(l['held_key'])}",
                "director": f"{res.name(l['holder_key'])} is a director of {res.name(l['held_key'])}",
                "managing_director": f"{res.name(l['holder_key'])} is managing director of {res.name(l['held_key'])}",
                }.get(l["kind"], f"{l['holder']} - {l['kind']} - {l['held']}")
        quote = l["quote"].replace("|", "/")
        out.append(f"| {what} | {l['doc']}, {l.get('location', '')} ({l['date']}): \"{quote}\" | Documented |")
    multi = len(res.scenarios) > 1
    for i, s in enumerate(res.scenarios):
        tag = f" (reading {i + 1}: {', '.join(f'{k} per {v}' for k, v in s['choice'].items() if v)})" if multi else ""
        if s.get("overallocated"):
            out.append(f"| Stakes in this reading are not reported: the stated holdings exceed 100% | OVERALLOCATED{tag} | Unresolved |")
            continue
        for k, v in sorted(s["economic"].items(), key=lambda kv: -kv[1]):
            if k.startswith("UNACCOUNTED:"):
                out.append(f"| {res.name(k)}: {_pct(v)} of the customer | Holders on file don't add up to 100%{tag} | Unresolved |")
                continue
            ps = paths_to(s["holdings"], k, case["customer"]["id"])
            how = " + ".join(" x ".join(_pct(s["holdings"][p[j + 1]][p[j]]) for j in range(len(p) - 1)) for p, _ in ps) or "via cycle"
            if abs(sum(f for _, f in ps) - v) > 1e-6:
                how += " + repeated trips round the circular holding (solved exactly)"
            if res.entities.get(k, {}).get("type") == "listed":
                out.append(f"| {res.name(k)} holds {_pct(v)}: listed company, trail stops | {how}{tag} | Calculated |")
            else:
                out.append(f"| {res.name(k)}'s effective economic stake is {_pct(v)} | {how}{tag} | Calculated |")
    out.append("")

    out += ["## Open issues for the officer", ""]
    if not res.open_issues:
        out += ["- None", ""]
    for cat, _ in CATEGORIES:
        fs = [f for f in res.flags if f.category == cat]
        if fs:
            out += [f"**{cat.title()}**", ""] + [f"- `{f.code}` {f.message}" for f in fs] + [""]
    info = [f for f in res.flags if f.category == "INFO"]
    if info:
        out += ["**Notes**", ""] + [f"- `{f.code}` {f.message}" for f in info] + [""]

    if res.identity_log:
        out += ["## Identity decisions", "", "| Record | Decision | Reason | Method |", "| --- | --- | --- | --- |"]
        for d in res.identity_log:
            key = d["key"] if isinstance(d["key"], str) else ", ".join(d["key"])
            out.append(f"| {d['name']} ({key}) | {d['decision']}{' - review pending' if d.get('review') else ''} | {d['reason']} | "
                       f"{'identifier' if d.get('deterministic') else 'name-based'} |")
        out.append("")

    if res.rejected:
        out += ["## Rejected extractions (kept out of the ownership graph, original values preserved)", ""]
        for r in res.rejected:
            o = r["original"]
            out.append(f"- {r['doc']}: `{o.get('holder', o.get('name', o.get('raw', '?')))}` -> `{o.get('held', '')}` "
                       f"{o.get('kind', '')} {o.get('pct', '')}: **{r['reason']}** ({r['code']}). Quote given: \"{o.get('quote', '')}\"")
        out.append("")

    steps = []
    for f in res.flags:
        t = FOLLOW_UP.get(f.code)
        if t:
            line = t.format(s=f.subject or "this item")
            if line not in steps:
                steps.append(line)
    out += ["## Recommended follow-up", ""] + ([f"{i}. {s}" for i, s in enumerate(steps, 1)] or ["1. None beyond officer approval."]) + [""]
    out += ["---", "Decision support only. Only an authorised compliance officer can approve this file. "
            "The system identifies evidence and open questions; it makes no allegation about any person."]
    return "\n".join(out)
