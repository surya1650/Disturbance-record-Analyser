# Skills — DR Analyser

Each folder is one skill (`SKILL.md` with `name` + `description` frontmatter). Claude
loads the description list every session and reads the body only when the situation
matches, so the descriptions carry the triggers.

| Skill | Use it when |
|---|---|
| `spec-constraints` | A request touches something `PROJECT_CONTEXT.md` §2 rules out (per-relay ML, traveling wave, time-sync dependency, per-file reports, silent repair), or assumes a §17 [OPEN] answer |
| `fault-location-math` | Changing anything in `faultloc/` or `dsp/`, the k0 definition, the E5 quadratic, or an accuracy number |
| `comtrade-corpus` | Touching the parser or the conformance gate, adding vendor files to `tests/corpus/`, "it parses but the numbers are wrong" |
| `record-investigation` | "Why does this fault show this km", two ends disagree, a method returned nothing |
| `release-check` | Before a merge or a release — the full gate order and how to read each result |
| `same-defect-sweep` | Right after fixing one estimator / parser branch / vendor map, before saying done |
| `still-not-showing` | "Still the same answer / same error" — delivery layer first, code last |
| `plan-first` | A multi-part feature, or "keep this documented, we will proceed again" |
| `plan-review` | Judging finished work against a plan or against §14 |
| `session-handoff` | End of a milestone — ledger, lessons, memory, plan doc |

Two habits these encode, worth stating outside any one skill:

- **"Check / review / verify" means report and wait.** Fixing starts when the user says
  "fix it" / "fix one by one".
- **Done means exercised on real data**, not "the gates are green".
