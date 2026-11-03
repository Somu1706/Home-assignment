# Results (fixture mode)

*Fixture mode: hand-written correct extractions. Tests the deterministic engine and checks, not the AI reading step. All data synthetic.*

| Case | What it tests | Owners found | Status | Result |
| --- | --- | --- | --- | --- |
| 01 | Two direct owners | Asha Rao, Vikram Iyer | READY FOR OFFICER APPROVAL | PASS |
| 02 | Three-level chain | Kiran Das, Leela Nair, Prakash Menon | REGULATORY ASSESSMENT REQUIRES REVIEW | PASS |
| 03 | Same person on two paths, listed holder | Arjun Shah, Meera Pillai, Nikhil Varma | READY FOR OFFICER APPROVAL | PASS |
| 04 | Overlapping directors, no shares | Anil Kumar, Bina Shah | READY FOR OFFICER APPROVAL | PASS |
| 05 | Two different people with the same name | Uma Krishnan | IDENTITY MATCH REQUIRES REVIEW | PASS |
| 06 | Two documents of the same date disagree | Gita Bose | OWNERSHIP STRUCTURE UNRESOLVED | PASS |
| 07 | Ownership changed since an older document | Isha Gupta | READY FOR OFFICER APPROVAL | PASS |
| 08 | 5% holder who appoints most of the board | Kavya Reddy | REGULATORY ASSESSMENT REQUIRES REVIEW | PASS |
| 09 | Partnership deed explains only 40% of the LLP | Neha Joshi, Rohan Das | INSUFFICIENT INFORMATION | PASS |
| 10 | Shared address, no ownership link | Om Prakash, Priya Sen | READY FOR OFFICER APPROVAL | PASS |
| 11 | Circular holding between two companies | Sita Raman, Tara Singh | REGULATORY ASSESSMENT REQUIRES REVIEW | PASS |
| 12 | Shares with extra voting rights | Uday Kapoor, Vani Rao | REGULATORY ASSESSMENT REQUIRES REVIEW | PASS |
| 13 | Counting methods disagree | Xena Paul | REGULATORY ASSESSMENT REQUIRES REVIEW | PASS |

## Planted AI errors (do the checks catch them?)

| Fault | What goes wrong | Owners found | Status | Result |
| --- | --- | --- | --- | --- |
| F1 | AI invents a shareholding (quote not in document) | Arjun Shah, Meera Pillai, Nikhil Varma | EVIDENCE VALIDATION FAILED | PASS |
| F2 | AI misreads Arjun's 30% as 40% | Meera Pillai, Nikhil Varma | EVIDENCE VALIDATION FAILED | PASS |
| F3 | AI misses a 60% partner | Arjun Shah, Meera Pillai | INSUFFICIENT INFORMATION | PASS |
| F4 | AI drops Meera's PAN in one document | Arjun Shah, Meera Pillai, Nikhil Varma | IDENTITY MATCH REQUIRES REVIEW | PASS |
| F5 | AI misses that Delta is listed | Arjun Shah, Meera Pillai, Nikhil Varma | INSUFFICIENT INFORMATION | PASS |

**18 of 18 passed.**
