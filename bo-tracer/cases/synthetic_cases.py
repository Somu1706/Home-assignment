"""Thirteen SYNTHETIC KYC cases. Every company, person, PAN, CIN and address
here is invented. None refers to a real company or person.

Each case has:
  documents  - the text a bank would receive (what the AI reads in live mode)
  gold       - the correct extraction, written by hand (used in fixture mode,
               and as the answer key for scoring a live AI extraction)
  expected   - who the beneficial owners are, which flags must appear, file status
"""
AS_OF = "2026-11-03"


def P(name, pan):                       # a person, keyed by PAN
    return {"name": name, "type": "person", "id": f"PAN:{pan}", "quote": name}


def C(name, cin, typ="company"):        # a company / LLP / listed company
    prefix = "LLPIN" if typ == "llp" else "CIN"
    return {"name": name, "type": typ, "id": f"{prefix}:{cin}", "quote": name}


def L(holder, held, kind, quote, pct=None, holder_id=None, held_id=None):
    d = {"holder": holder, "held": held, "kind": kind, "pct": pct, "quote": quote}
    if holder_id:
        d["holder_id"] = holder_id
    if held_id:
        d["held_id"] = held_id
    return d


def doc(title, date, *lines):
    return {"title": title, "date": date, "text": "\n".join(lines)}


CASES = []

# ---------------------------------------------------------------- 1
l1 = "1. Asha Rao (PAN ABCPR1234A) - 6,000 equity shares - 60%"
l2 = "2. Vikram Iyer (PAN ABCPI5678B) - 4,000 equity shares - 40%"
CASES.append({
    "id": "01", "title": "Two direct owners", "as_of": AS_OF,
    "customer": {"name": "Lotus Foods Private Limited", "id": "CIN:U15400TN2019PTC111111", "type": "company"},
    "documents": {"lotus_shareholders": doc("List of shareholders", "2026-03-31",
        "LOTUS FOODS PRIVATE LIMITED (CIN U15400TN2019PTC111111)",
        "List of shareholders as on 31 March 2026", l1, l2, "Total: 10,000 equity shares - 100%")},
    "gold": {"lotus_shareholders": {
        "entities": [C("Lotus Foods Private Limited", "U15400TN2019PTC111111"),
                     P("Asha Rao", "ABCPR1234A"), P("Vikram Iyer", "ABCPI5678B")],
        "links": [L("Asha Rao", "Lotus Foods Private Limited", "equity", l1, 60),
                  L("Vikram Iyer", "Lotus Foods Private Limited", "equity", l2, 40)]}},
    "expected": {"owners": ["Asha Rao", "Vikram Iyer"], "unresolved": [], "flags": [],
                 "status": "READY FOR OFFICER APPROVAL"},
})

# ---------------------------------------------------------------- 2
a1 = "Yamuna Holdings Private Limited (CIN U65900KA2015PTC222333) - 7,000 equity shares - 70%"
a2 = "Kiran Das (PAN BCDPD2345C) - 3,000 equity shares - 30%"
b1 = "Xylo Investments Private Limited (CIN U65990MH2012PTC444555) - 60,000 shares - 60%"
b2 = "Leela Nair (PAN CDEPN3456D) - 40,000 shares - 40%"
c1 = "Prakash Menon (PAN DEFPM4567E) - 800 shares - 80%"
c2 = "Sam Joseph (PAN EFGPJ5678F) - 200 shares - 20%"
CASES.append({
    "id": "02", "title": "Three-level chain", "as_of": AS_OF,
    "customer": {"name": "Saffron Textiles Private Limited", "id": "CIN:U17110TN2018PTC222222", "type": "company"},
    "documents": {
        "saffron_shareholders": doc("List of shareholders", "2026-03-31",
            "SAFFRON TEXTILES PRIVATE LIMITED (CIN U17110TN2018PTC222222)", "Shareholders as on 31 March 2026", a1, a2),
        "yamuna_shareholders": doc("List of shareholders", "2026-03-31",
            "YAMUNA HOLDINGS PRIVATE LIMITED (CIN U65900KA2015PTC222333)", "Shareholders as on 31 March 2026", b1, b2),
        "xylo_shareholders": doc("List of shareholders", "2026-03-31",
            "XYLO INVESTMENTS PRIVATE LIMITED (CIN U65990MH2012PTC444555)", "Shareholders as on 31 March 2026", c1, c2)},
    "gold": {
        "saffron_shareholders": {"entities": [C("Saffron Textiles Private Limited", "U17110TN2018PTC222222"),
                                              C("Yamuna Holdings Private Limited", "U65900KA2015PTC222333"), P("Kiran Das", "BCDPD2345C")],
                                 "links": [L("Yamuna Holdings Private Limited", "Saffron Textiles Private Limited", "equity", a1, 70),
                                           L("Kiran Das", "Saffron Textiles Private Limited", "equity", a2, 30)]},
        "yamuna_shareholders": {"entities": [C("Yamuna Holdings Private Limited", "U65900KA2015PTC222333"),
                                             C("Xylo Investments Private Limited", "U65990MH2012PTC444555"), P("Leela Nair", "CDEPN3456D")],
                                "links": [L("Xylo Investments Private Limited", "Yamuna Holdings Private Limited", "equity", b1, 60),
                                          L("Leela Nair", "Yamuna Holdings Private Limited", "equity", b2, 40)]},
        "xylo_shareholders": {"entities": [C("Xylo Investments Private Limited", "U65990MH2012PTC444555"),
                                           P("Prakash Menon", "DEFPM4567E"), P("Sam Joseph", "EFGPJ5678F")],
                              "links": [L("Prakash Menon", "Xylo Investments Private Limited", "equity", c1, 80),
                                        L("Sam Joseph", "Xylo Investments Private Limited", "equity", c2, 20)]}},
    "expected": {"owners": ["Kiran Das", "Leela Nair", "Prakash Menon"], "unresolved": [],
                 "flags": ["NEAR_THRESHOLD"], "status": "REGULATORY ASSESSMENT REQUIRES REVIEW"},
})

# ---------------------------------------------------------------- 3 (the brief's worked example, with the gap filled)
o1 = "Meera Pillai (PAN FGHPP6789G) - 800 equity shares - 8%"
o2 = "Kestrel Holdings LLP (LLPIN AAB-1234) - 4,000 equity shares - 40%"
o3 = "Delta Industries Limited (CIN L24100MH1995PLC093333), listed on the National Stock Exchange of India - 5,200 equity shares - 52%"
k1 = "Arjun Shah (PAN GHIPS7890H) - contribution Rs 30,00,000 - 30% of capital and profits"
k2 = "Meera Pillai (PAN FGHPP6789G) - contribution Rs 10,00,000 - 10% of capital and profits"
k3 = "Nikhil Varma (PAN HIJPV8901J) - contribution Rs 60,00,000 - 60% of capital and profits"
CASE3 = {
    "id": "03", "title": "Same person on two paths, listed holder", "as_of": AS_OF,
    "customer": {"name": "Orion Traders Private Limited", "id": "CIN:U51909TN2020PTC333333", "type": "company"},
    "documents": {
        "orion_shareholders": doc("List of shareholders", "2026-03-31",
            "ORION TRADERS PRIVATE LIMITED (CIN U51909TN2020PTC333333)", "Shareholders as on 31 March 2026", o1, o2, o3),
        "kestrel_partners": doc("Statement of partners' contribution", "2026-04-01",
            "KESTREL HOLDINGS LLP (LLPIN AAB-1234)", "Partners and their share of capital and profits as on 1 April 2026", k1, k2, k3)},
    "gold": {
        "orion_shareholders": {"entities": [C("Orion Traders Private Limited", "U51909TN2020PTC333333"), P("Meera Pillai", "FGHPP6789G"),
                                            C("Kestrel Holdings LLP", "AAB-1234", "llp"),
                                            {"name": "Delta Industries Limited", "type": "listed", "id": "CIN:L24100MH1995PLC093333",
                                             "quote": "Delta Industries Limited (CIN L24100MH1995PLC093333), listed on the National Stock Exchange of India"}],
                               "links": [L("Meera Pillai", "Orion Traders Private Limited", "equity", o1, 8),
                                         L("Kestrel Holdings LLP", "Orion Traders Private Limited", "equity", o2, 40),
                                         L("Delta Industries Limited", "Orion Traders Private Limited", "equity", o3, 52)]},
        "kestrel_partners": {"entities": [C("Kestrel Holdings LLP", "AAB-1234", "llp"), P("Arjun Shah", "GHIPS7890H"),
                                          P("Meera Pillai", "FGHPP6789G"), P("Nikhil Varma", "HIJPV8901J")],
                             "links": [L("Arjun Shah", "Kestrel Holdings LLP", "equity", k1, 30),
                                       L("Meera Pillai", "Kestrel Holdings LLP", "equity", k2, 10),
                                       L("Nikhil Varma", "Kestrel Holdings LLP", "equity", k3, 60)]}},
    "expected": {"owners": ["Arjun Shah", "Meera Pillai", "Nikhil Varma"], "unresolved": [], "flags": [],
                 "status": "READY FOR OFFICER APPROVAL"},
}
CASES.append(CASE3)

# ---------------------------------------------------------------- 4
s1 = "Anil Kumar (PAN IJKPK9012K) - 5,500 equity shares - 55%"
s2 = "Bina Shah (PAN JKLPS0123L) - 4,500 equity shares - 45%"
r1 = "Anil Kumar (DIN 07650001, PAN IJKPK9012K) - Managing Director"
r2 = "Chetan Rao (DIN 07650002, PAN KLMPR1234M) - Non-executive Director"
r3 = "Chetan Rao (DIN 07650002, PAN KLMPR1234M) - Director"
CASES.append({
    "id": "04", "title": "Overlapping directors, no shares", "as_of": AS_OF,
    "customer": {"name": "Banyan Logistics Private Limited", "id": "CIN:U63030TN2017PTC444444", "type": "company"},
    "documents": {
        "banyan_shareholders": doc("List of shareholders", "2026-03-31",
            "BANYAN LOGISTICS PRIVATE LIMITED (CIN U63030TN2017PTC444444)", "Shareholders as on 31 March 2026", s1, s2),
        "banyan_directors": doc("Register of directors", "2026-03-31",
            "BANYAN LOGISTICS PRIVATE LIMITED (CIN U63030TN2017PTC444444)", "Directors as on 31 March 2026", r1, r2),
        "cedar_directors": doc("Register of directors (other company)", "2026-03-31",
            "CEDAR FREIGHT PRIVATE LIMITED (CIN U60200TN2016PTC555555)", "Directors as on 31 March 2026", r3,
            "Registered office: 22 Harbour Street, Chennai")},
    "gold": {
        "banyan_shareholders": {"entities": [C("Banyan Logistics Private Limited", "U63030TN2017PTC444444"),
                                             P("Anil Kumar", "IJKPK9012K"), P("Bina Shah", "JKLPS0123L")],
                                "links": [L("Anil Kumar", "Banyan Logistics Private Limited", "equity", s1, 55),
                                          L("Bina Shah", "Banyan Logistics Private Limited", "equity", s2, 45)]},
        "banyan_directors": {"entities": [C("Banyan Logistics Private Limited", "U63030TN2017PTC444444"),
                                          P("Anil Kumar", "IJKPK9012K"), P("Chetan Rao", "KLMPR1234M")],
                             "links": [L("Anil Kumar", "Banyan Logistics Private Limited", "managing_director", r1),
                                       L("Chetan Rao", "Banyan Logistics Private Limited", "director", r2)]},
        "cedar_directors": {"entities": [C("Cedar Freight Private Limited", "U60200TN2016PTC555555"), P("Chetan Rao", "KLMPR1234M")],
                            "links": [L("Chetan Rao", "Cedar Freight Private Limited", "director", r3)]}},
    "expected": {"owners": ["Anil Kumar", "Bina Shah"], "unresolved": [], "flags": [],
                 "status": "READY FOR OFFICER APPROVAL"},
})

# ---------------------------------------------------------------- 5
i1 = "Rakesh Mehta (PAN AAAPM1111A) - 600 equity shares - 6%"
i2 = "Rakesh Mehta (PAN AAAPM2222B) - 600 equity shares - 6%"
i3 = "Sunrise Ventures Private Limited (CIN U74999DL2014PTC666666) - 8,800 equity shares - 88%"
u1 = "Uma Krishnan (PAN LMNPK2345N) - 10,000 equity shares - 100%"
CASES.append({
    "id": "05", "title": "Two different people with the same name", "as_of": AS_OF,
    "customer": {"name": "Indigo Pharma Private Limited", "id": "CIN:U24230TN2021PTC555000", "type": "company"},
    "documents": {
        "indigo_shareholders": doc("List of shareholders", "2026-03-31",
            "INDIGO PHARMA PRIVATE LIMITED (CIN U24230TN2021PTC555000)", "Shareholders as on 31 March 2026", i1, i2, i3),
        "sunrise_shareholders": doc("List of shareholders", "2026-03-31",
            "SUNRISE VENTURES PRIVATE LIMITED (CIN U74999DL2014PTC666666)", "Shareholders as on 31 March 2026", u1)},
    "gold": {
        "indigo_shareholders": {"entities": [C("Indigo Pharma Private Limited", "U24230TN2021PTC555000"),
                                             {**P("Rakesh Mehta", "AAAPM1111A"), "quote": "Rakesh Mehta (PAN AAAPM1111A)"},
                                             {**P("Rakesh Mehta", "AAAPM2222B"), "quote": "Rakesh Mehta (PAN AAAPM2222B)"},
                                             C("Sunrise Ventures Private Limited", "U74999DL2014PTC666666")],
                                "links": [L("Rakesh Mehta", "Indigo Pharma Private Limited", "equity", i1, 6, holder_id="PAN:AAAPM1111A"),
                                          L("Rakesh Mehta", "Indigo Pharma Private Limited", "equity", i2, 6, holder_id="PAN:AAAPM2222B"),
                                          L("Sunrise Ventures Private Limited", "Indigo Pharma Private Limited", "equity", i3, 88)]},
        "sunrise_shareholders": {"entities": [C("Sunrise Ventures Private Limited", "U74999DL2014PTC666666"), P("Uma Krishnan", "LMNPK2345N")],
                                 "links": [L("Uma Krishnan", "Sunrise Ventures Private Limited", "equity", u1, 100)]}},
    "expected": {"owners": ["Uma Krishnan"], "unresolved": [], "flags": ["NAME_COLLISION"],
                 "status": "IDENTITY MATCH REQUIRES REVIEW"},
})

# ---------------------------------------------------------------- 6
j1 = "Farhan Ali (PAN MNOPA3456P) - 3,000 equity shares - 30%"
j2 = "Gita Bose (PAN NOPPB4567Q) - 7,000 equity shares - 70%"
j3 = "Farhan Ali (PAN MNOPA3456P) holds 10% of the equity share capital"
j4 = "Gita Bose (PAN NOPPB4567Q) holds 90% of the equity share capital"
CASES.append({
    "id": "06", "title": "Two documents of the same date disagree", "as_of": AS_OF,
    "customer": {"name": "Jade Retail Private Limited", "id": "CIN:U52100TN2019PTC606060", "type": "company"},
    "documents": {
        "jade_shareholders": doc("List of shareholders", "2026-03-31",
            "JADE RETAIL PRIVATE LIMITED (CIN U52100TN2019PTC606060)", "Shareholders as on 31 March 2026", j1, j2),
        "jade_sbo_declaration": doc("Declaration of significant beneficial ownership", "2026-03-31",
            "JADE RETAIL PRIVATE LIMITED (CIN U52100TN2019PTC606060)", "Declaration as on 31 March 2026", j3, j4)},
    "gold": {
        "jade_shareholders": {"entities": [C("Jade Retail Private Limited", "U52100TN2019PTC606060"),
                                           P("Farhan Ali", "MNOPA3456P"), P("Gita Bose", "NOPPB4567Q")],
                              "links": [L("Farhan Ali", "Jade Retail Private Limited", "equity", j1, 30),
                                        L("Gita Bose", "Jade Retail Private Limited", "equity", j2, 70)]},
        "jade_sbo_declaration": {"entities": [C("Jade Retail Private Limited", "U52100TN2019PTC606060"),
                                              P("Farhan Ali", "MNOPA3456P"), P("Gita Bose", "NOPPB4567Q")],
                                 "links": [L("Farhan Ali", "Jade Retail Private Limited", "equity", j3, 10),
                                           L("Gita Bose", "Jade Retail Private Limited", "equity", j4, 90)]}},
    # Answer key corrected after the first run: in the declaration's reading Farhan holds exactly 10%,
    # which is not "more than 10%" but is a near miss. The engine flagged it; my first key had missed it.
    "expected": {"owners": ["Gita Bose"], "unresolved": ["Farhan Ali"], "flags": ["CONTRADICTION", "NEAR_THRESHOLD"],
                 "status": "OWNERSHIP STRUCTURE UNRESOLVED"},
})

# ---------------------------------------------------------------- 7
h1 = "Hari Prasad (PAN OPQPP5678R) - 6,000 equity shares - 60%"
h2 = "Isha Gupta (PAN PQRPG6789S) - 4,000 equity shares - 40%"
h3 = "Isha Gupta (PAN PQRPG6789S) - 10,000 equity shares - 100%"
CASES.append({
    "id": "07", "title": "Ownership changed since an older document", "as_of": AS_OF,
    "customer": {"name": "Opal Media Private Limited", "id": "CIN:U92100TN2016PTC707070", "type": "company"},
    "documents": {
        "opal_shareholders_2022": doc("List of shareholders", "2022-03-31",
            "OPAL MEDIA PRIVATE LIMITED (CIN U92100TN2016PTC707070)", "Shareholders as on 31 March 2022", h1, h2),
        "opal_shareholders_2026": doc("List of shareholders", "2026-03-31",
            "OPAL MEDIA PRIVATE LIMITED (CIN U92100TN2016PTC707070)", "Shareholders as on 31 March 2026", h3)},
    "gold": {
        "opal_shareholders_2022": {"entities": [C("Opal Media Private Limited", "U92100TN2016PTC707070"),
                                                P("Hari Prasad", "OPQPP5678R"), P("Isha Gupta", "PQRPG6789S")],
                                   "links": [L("Hari Prasad", "Opal Media Private Limited", "equity", h1, 60),
                                             L("Isha Gupta", "Opal Media Private Limited", "equity", h2, 40)]},
        "opal_shareholders_2026": {"entities": [C("Opal Media Private Limited", "U92100TN2016PTC707070"), P("Isha Gupta", "PQRPG6789S")],
                                   "links": [L("Isha Gupta", "Opal Media Private Limited", "equity", h3, 100)]}},
    "expected": {"owners": ["Isha Gupta"], "unresolved": [], "flags": ["SUPERSEDED"],
                 "status": "READY FOR OFFICER APPROVAL"},
})

# ---------------------------------------------------------------- 8
q1 = "Jai Malhotra (PAN QRSPM7890T) - 500 equity shares - 5%"
q2 = "Kavya Reddy (PAN RSTPR8901U) - 9,500 equity shares - 95%"
q3 = "Jai Malhotra shall be entitled to appoint two of the three directors of the Company"
CASES.append({
    "id": "08", "title": "5% holder who appoints most of the board", "as_of": AS_OF,
    "customer": {"name": "Quill Software Private Limited", "id": "CIN:U72200TN2022PTC808080", "type": "company"},
    "documents": {
        "quill_shareholders": doc("List of shareholders", "2026-03-31",
            "QUILL SOFTWARE PRIVATE LIMITED (CIN U72200TN2022PTC808080)", "Shareholders as on 31 March 2026", q1, q2),
        "quill_sha": doc("Shareholders' agreement (extract)", "2025-06-01",
            "SHAREHOLDERS' AGREEMENT relating to Quill Software Private Limited",
            "Clause 7.2 Board composition. " + q3 + ", and to remove and replace any director so appointed.")},
    "gold": {
        "quill_shareholders": {"entities": [C("Quill Software Private Limited", "U72200TN2022PTC808080"),
                                            P("Jai Malhotra", "QRSPM7890T"), P("Kavya Reddy", "RSTPR8901U")],
                               "links": [L("Jai Malhotra", "Quill Software Private Limited", "equity", q1, 5),
                                         L("Kavya Reddy", "Quill Software Private Limited", "equity", q2, 95)]},
        "quill_sha": {"entities": [{"name": "Quill Software Private Limited", "type": "company", "id": "CIN:U72200TN2022PTC808080",
                                    "quote": "Quill Software Private Limited"},
                                   {"name": "Jai Malhotra", "type": "person", "id": "PAN:QRSPM7890T", "quote": "Jai Malhotra"}],
                      "links": [L("Jai Malhotra", "Quill Software Private Limited", "appoint_directors", q3)]}},
    "expected": {"owners": ["Kavya Reddy"], "unresolved": [], "flags": ["CONTROL_REVIEW"],
                 "status": "REGULATORY ASSESSMENT REQUIRES REVIEW"},
})
# NOTE case 8: the agreement names Jai without a PAN. The gold extraction attaches the PAN from
# the shareholder list; in live mode the AI may not, which would raise NAME_ONLY_MATCH instead.

# ---------------------------------------------------------------- 9
n1 = "Maple Ventures LLP (LLPIN AAC-5678) - 5,000 equity shares - 50%"
n2 = "Neha Joshi (PAN STUPJ9012V) - 5,000 equity shares - 50%"
m1 = "Rohan Das (PAN TUVPD0123W) - 25% of capital and profits"
m2 = "Simran Kaur (PAN UVWPK1234X) - 15% of capital and profits"
CASES.append({
    "id": "09", "title": "Partnership deed explains only 40% of the LLP", "as_of": AS_OF,
    "customer": {"name": "Neem Exports Private Limited", "id": "CIN:U51100TN2018PTC909090", "type": "company"},
    "documents": {
        "neem_shareholders": doc("List of shareholders", "2026-03-31",
            "NEEM EXPORTS PRIVATE LIMITED (CIN U51100TN2018PTC909090)", "Shareholders as on 31 March 2026", n1, n2),
        "maple_partners": doc("Statement of partners' contribution (extract)", "2026-04-01",
            "MAPLE VENTURES LLP (LLPIN AAC-5678)", "Designated partners:", m1, m2,
            "The contribution of the remaining partners is recorded in Schedule B.")},
    "gold": {
        "neem_shareholders": {"entities": [C("Neem Exports Private Limited", "U51100TN2018PTC909090"),
                                           C("Maple Ventures LLP", "AAC-5678", "llp"), P("Neha Joshi", "STUPJ9012V")],
                              "links": [L("Maple Ventures LLP", "Neem Exports Private Limited", "equity", n1, 50),
                                        L("Neha Joshi", "Neem Exports Private Limited", "equity", n2, 50)]},
        "maple_partners": {"entities": [C("Maple Ventures LLP", "AAC-5678", "llp"), P("Rohan Das", "TUVPD0123W"), P("Simran Kaur", "UVWPK1234X")],
                           "links": [L("Rohan Das", "Maple Ventures LLP", "equity", m1, 25),
                                     L("Simran Kaur", "Maple Ventures LLP", "equity", m2, 15)]}},
    "expected": {"owners": ["Neha Joshi", "Rohan Das"], "unresolved": [], "flags": ["GAP_BLOCKING"],
                 "status": "INSUFFICIENT INFORMATION"},
})

# ---------------------------------------------------------------- 10
p1 = "Om Prakash (PAN VWXPP2345Y) - 7,000 equity shares - 70%"
p2 = "Priya Sen (PAN WXYPS3456Z) - 3,000 equity shares - 30%"
p3 = "Ravi Teja (DIN 08880001, PAN XYZPT4567A) - Director"
CASES.append({
    "id": "10", "title": "Shared address, no ownership link", "as_of": AS_OF,
    "customer": {"name": "Pearl Hotels Private Limited", "id": "CIN:U55101TN2015PTC101010", "type": "company"},
    "documents": {
        "pearl_shareholders": doc("List of shareholders", "2026-03-31",
            "PEARL HOTELS PRIVATE LIMITED (CIN U55101TN2015PTC101010)", "Registered office: 14 Lake Road, Chennai",
            "Shareholders as on 31 March 2026", p1, p2),
        "quartz_master_data": doc("Company master data (other company)", "2026-05-10",
            "QUARTZ TRADERS PRIVATE LIMITED (CIN U51909TN2019PTC111222)", "Registered office: 14 Lake Road, Chennai", p3)},
    "gold": {
        "pearl_shareholders": {"entities": [C("Pearl Hotels Private Limited", "U55101TN2015PTC101010"),
                                            P("Om Prakash", "VWXPP2345Y"), P("Priya Sen", "WXYPS3456Z")],
                               "links": [L("Om Prakash", "Pearl Hotels Private Limited", "equity", p1, 70),
                                         L("Priya Sen", "Pearl Hotels Private Limited", "equity", p2, 30)]},
        "quartz_master_data": {"entities": [C("Quartz Traders Private Limited", "U51909TN2019PTC111222"), P("Ravi Teja", "XYZPT4567A")],
                               "links": [L("Ravi Teja", "Quartz Traders Private Limited", "director", p3)]}},
    "expected": {"owners": ["Om Prakash", "Priya Sen"], "unresolved": [], "flags": [],
                 "status": "READY FOR OFFICER APPROVAL"},
})

# ---------------------------------------------------------------- 11
t1 = "Aster Holdings Private Limited (CIN U65920TN2010PTC121212) - 10,000 equity shares - 100%"
t2 = "Sita Raman (PAN YZAPR5678B) - 8,000 equity shares - 80%"
t3 = "Birch Capital Private Limited (CIN U65920TN2011PTC131313) - 2,000 equity shares - 20%"
t4 = "Aster Holdings Private Limited (CIN U65920TN2010PTC121212) - 3,000 equity shares - 30%"
t5 = "Tara Singh (PAN ZABPS6789C) - 7,000 equity shares - 70%"
CASES.append({
    "id": "11", "title": "Circular holding between two companies", "as_of": AS_OF,
    "customer": {"name": "Tamarind Agro Private Limited", "id": "CIN:U01100TN2020PTC111111", "type": "company"},
    "documents": {
        "tamarind_shareholders": doc("List of shareholders", "2026-03-31",
            "TAMARIND AGRO PRIVATE LIMITED (CIN U01100TN2020PTC111111)", "Shareholders as on 31 March 2026", t1),
        "aster_shareholders": doc("List of shareholders", "2026-03-31",
            "ASTER HOLDINGS PRIVATE LIMITED (CIN U65920TN2010PTC121212)", "Shareholders as on 31 March 2026", t2, t3),
        "birch_shareholders": doc("List of shareholders", "2026-03-31",
            "BIRCH CAPITAL PRIVATE LIMITED (CIN U65920TN2011PTC131313)", "Shareholders as on 31 March 2026", t4, t5)},
    "gold": {
        "tamarind_shareholders": {"entities": [C("Tamarind Agro Private Limited", "U01100TN2020PTC111111"),
                                               C("Aster Holdings Private Limited", "U65920TN2010PTC121212")],
                                  "links": [L("Aster Holdings Private Limited", "Tamarind Agro Private Limited", "equity", t1, 100)]},
        "aster_shareholders": {"entities": [C("Aster Holdings Private Limited", "U65920TN2010PTC121212"), P("Sita Raman", "YZAPR5678B"),
                                            C("Birch Capital Private Limited", "U65920TN2011PTC131313")],
                               "links": [L("Sita Raman", "Aster Holdings Private Limited", "equity", t2, 80),
                                         L("Birch Capital Private Limited", "Aster Holdings Private Limited", "equity", t3, 20)]},
        "birch_shareholders": {"entities": [C("Birch Capital Private Limited", "U65920TN2011PTC131313"),
                                            C("Aster Holdings Private Limited", "U65920TN2010PTC121212"), P("Tara Singh", "ZABPS6789C")],
                               "links": [L("Aster Holdings Private Limited", "Birch Capital Private Limited", "equity", t4, 30),
                                         L("Tara Singh", "Birch Capital Private Limited", "equity", t5, 70)]}},
    "expected": {"owners": ["Sita Raman", "Tara Singh"], "unresolved": [], "flags": ["CYCLE"],
                 "status": "REGULATORY ASSESSMENT REQUIRES REVIEW"},
})

# ---------------------------------------------------------------- 12
v1 = "Uday Kapoor (PAN ABCPK7890D) - 2,000 Class B equity shares - 20%"
v2 = "Vani Rao (PAN BCDPR8901E) - 8,000 Class A equity shares - 80%"
v3 = "Each Class B equity share carries ten votes"
CASES.append({
    "id": "12", "title": "Shares with extra voting rights", "as_of": AS_OF,
    "customer": {"name": "Umber Labs Private Limited", "id": "CIN:U73100TN2023PTC121200", "type": "company"},
    "documents": {
        "umber_shareholders": doc("List of shareholders", "2026-03-31",
            "UMBER LABS PRIVATE LIMITED (CIN U73100TN2023PTC121200)", "Shareholders as on 31 March 2026", v1, v2),
        "umber_articles": doc("Articles of association (extract)", "2023-07-01",
            "ARTICLES OF ASSOCIATION of Umber Labs Private Limited",
            "Article 12. " + v3 + "; each Class A equity share carries one vote. All Class B equity shares are held by Uday Kapoor.")},
    "gold": {
        "umber_shareholders": {"entities": [C("Umber Labs Private Limited", "U73100TN2023PTC121200"),
                                            P("Uday Kapoor", "ABCPK7890D"), P("Vani Rao", "BCDPR8901E")],
                               "links": [L("Uday Kapoor", "Umber Labs Private Limited", "equity", v1, 20),
                                         L("Vani Rao", "Umber Labs Private Limited", "equity", v2, 80)]},
        "umber_articles": {"entities": [{"name": "Umber Labs Private Limited", "type": "company", "id": "CIN:U73100TN2023PTC121200", "quote": "Umber Labs Private Limited"},
                                        {"name": "Uday Kapoor", "type": "person", "id": "PAN:ABCPK7890D", "quote": "Uday Kapoor"}],
                           "links": [L("Uday Kapoor", "Umber Labs Private Limited", "special_voting", v3)]}},
    "expected": {"owners": ["Uday Kapoor", "Vani Rao"], "unresolved": [], "flags": ["SHARE_CLASS"],
                 "status": "REGULATORY ASSESSMENT REQUIRES REVIEW"},
})

# ---------------------------------------------------------------- 13
w1 = "Xena Paul (PAN CDEPP9012F) - 8,500 equity shares - 85%"
w2 = "Zeta Capital Private Limited (CIN U65990TN2017PTC131300) - 1,500 equity shares - 15%"
w3 = "Wen Li (PAN DEFPL0123G) - 5,100 equity shares - 51%"
w4 = "Yash Patel (PAN EFGPP1234H) - 4,900 equity shares - 49%"
CASES.append({
    "id": "13", "title": "Counting methods disagree", "as_of": AS_OF,
    "customer": {"name": "Willow Foods Private Limited", "id": "CIN:U15490TN2021PTC131313", "type": "company"},
    "documents": {
        "willow_shareholders": doc("List of shareholders", "2026-03-31",
            "WILLOW FOODS PRIVATE LIMITED (CIN U15490TN2021PTC131313)", "Shareholders as on 31 March 2026", w1, w2),
        "zeta_shareholders": doc("List of shareholders", "2026-03-31",
            "ZETA CAPITAL PRIVATE LIMITED (CIN U65990TN2017PTC131300)", "Shareholders as on 31 March 2026", w3, w4)},
    "gold": {
        "willow_shareholders": {"entities": [C("Willow Foods Private Limited", "U15490TN2021PTC131313"),
                                             P("Xena Paul", "CDEPP9012F"), C("Zeta Capital Private Limited", "U65990TN2017PTC131300")],
                                "links": [L("Xena Paul", "Willow Foods Private Limited", "equity", w1, 85),
                                          L("Zeta Capital Private Limited", "Willow Foods Private Limited", "equity", w2, 15)]},
        "zeta_shareholders": {"entities": [C("Zeta Capital Private Limited", "U65990TN2017PTC131300"),
                                           P("Wen Li", "DEFPL0123G"), P("Yash Patel", "EFGPP1234H")],
                              "links": [L("Wen Li", "Zeta Capital Private Limited", "equity", w3, 51),
                                        L("Yash Patel", "Zeta Capital Private Limited", "equity", w4, 49)]}},
    "expected": {"owners": ["Xena Paul"], "unresolved": [], "flags": ["CONTROL_METHOD_ONLY"],
                 "status": "REGULATORY ASSESSMENT REQUIRES REVIEW"},
})
