# Independent record analysis on declared nonuniform sample coordinates

Single-terminal diagnostics do not require a common clock, remote recording or
line constants. The new read-only path decodes source observations, preserves
missing values, and models each supported time window independently. A blocked
normal location pipeline no longer means the source samples have nothing useful
to show. Existing primary-assignment, production DSP and location gates remain.

## Method and its limits
The strict loader supports ASCII/BINARY/BINARY32/FLOAT32 CFG/DAT pairs within
explicit resource bounds; original files are only read. Zero-rate exports use
their actual DAT coordinates, rather than a fitted uniform grid. Single-rate
CFG declarations retain their authority. Orphan CFGs retain their header and
hash with missing-DAT status; unsupported structures remain visibly unsupported.
Missing analog/digital observations never become invented zero samples.
Explicit valid CFG scaling is labelled unverified; otherwise values stay raw counts.

Each four-nominal-cycle window has a two-cycle hop. Frequency is estimated over
the declared search domain using time-weighted, simultaneous1/2/3harmonic,
constant and linear-trend regression. Actual sample times determine all bases
and half-support consistency checks. Neutral channels are excluded from frequency
references. A current-only fallback is explicitly identified when phase-voltage
references are unavailable. There is no resampling, assumed X/R decay, VT type,
hidden nominal-frequency fallback or physical CT/VT correction.

Manufacturer documentation explains that some legitimate COMTRADE exports use
variable DAT intervals: [SEL timing paper](https://selinc.com/api/download/119832/).
The reason for simultaneous harmonic fitting is independent of this particular
record: irregular sampling removes the orthogonality that can justify separate
sinusoid fits; see [Vio et al., A&A](https://www.aanda.org/10.1051/0004-6361/201014079).
These references do not certify this implementation, the recorder or its clock.

The model has declared observation, frequency, coverage, conditioning and
resource limits. A consistent fit is not a deterministic CT/noise error bound,
anti-alias certificate, calibrated phasor or proof of physical timing. Coherent
gain errors and aliases can pass. No output grants clock alignment, production
DSP or location authority. Low-density/short/distorted supports may withhold while
their sample traces and recorded digital states remain available. Sequence/fault
classification, physical inception/operation/clearing and fault distance have not
been promoted into this path. More numerical fitting cannot supply absent provenance.

## Independent numerical evidence
Code/protocol freeze a02945e precedes152 outcomes in
validation/NONUNIFORM_SOURCE_2026-10-27.json. All152 evaluate, zero failures.
The144 analytic cases use two new seeds,4/6cycles, three time schedules, three
off-nominal frequencies and clean/harmonic+linearDC/noise/amplitude-step cohorts.
All36 amplitude-step cases refuse a stationary model. Analytic truth comes directly
from independent signal equations, not production builders. Worst errors over
the bounded clean/noise cases: .014723Hz frequency, .002061relative RMS and
.086176degrees local support-centre phase. These are synthetic arithmetic/model
errors, not uncertainty estimates for real measurements.

Eight explicit coherent-gain/alias controls pass the signal model while preserving
all authority refusals. They are harmful counterexamples to treating residual or
stability as a CT/alias guarantee, not evidence of correct physical measurements.
All152 rows, denominators, failures and15UTF8/LF source bindings are retained,
including full_record_signals.py and the unchanged legacy parser/source-time API.

## Real-file replay, not field validation
Privately reviewed Dhone plus13downloaded CFGs:12CFG/DAT pairs decode; two CFGs
at VINUKONDA SS lack matching DATs and show header-only results. All26original
CFG/DAT byte hashes remain unchanged. The12paired records cover718planned windows;
2007/6362channel-window signal models are consistent, with all4355other channel-windows
retained as a visible refusal. This does not establish independent physical events
or correctly paired line ends. Content-hash duplicates are explicitly identified;
distinct payloads alone do not prove independent observations.

Dhone:3624samples,74/74planned supports;212/592channel-window models consistent.
Any Start retains33.280ms source span and[32.448,34.112]ms neighboring-sample
bracket. These are exported coordinates, not a relay operating-time measurement.
Its unchanged normal parser remains blocked. DR2:1800samples,36/36supports and
105/288consistent channel-window models. The full capture has changing voltage
samples; the application's flat-prefault crest finding does not describe the
entire record. We do not override that old gate or authenticate RMS calibration.

Local digital rising-edge references are explicit display origins. They neither
correct the clocks nor establish that the records describe the same event. Initial
assertions, missing states and unobserved boundaries remain unknown. This builds
the independent observations needed before a separately validated unsynchronised
E5 composition; E4 still requires its own verified clock evidence.

## Use
Run with the existing virtual environment, from the repository:

```powershell
.\.venv\Scripts\python.exe scripts\analyse_source_record.py --cfg "C:\path\record.CFG" --output "out\new-source-review" --reference "Any Start"
```

`--cfg` accepts multiple paths. Grouping them is a review workspace, not verified
event pairing. Outputs index.html and finite analysis.json are exclusive: choose
a new directory for a new run. Serve only that output directory on loopback to
view parsing, sample envelopes, digital intervals and every model/refusal in a
browser. No upload, primary assignment or application DB mutation is needed.

One fresh whole-branch review found five Important issues. The single TDD pass
also regraded numeric underflow and missing browser frequency attribution as
Important by their user-visible effect. Nineteen regression/control cases include
16observed failures before fixes;135focused now pass. Format/edition-aware missing
markers are handled before scaling: [IEEE PSRC1999 report,p5](https://www.pes-psrc.org/kb/report/068.pdf)
and [2013 conformity test plan,p13](https://www.pes-psrc.org/kb/report/071.pdf).
The2013numeric99999 control is retained as a legitimate value; its missing ASCII
fields are empty. Binary reserved negative limits and missing timestamp markers
remain unknown, not measured amplitudes or increasing source time.

Requested versus observed support is explicit; edge gaps cannot disappear when
selecting a window. A harmonic-only reference cannot establish a fundamental.
Each selected local anchor now shifts separate display supports/digital times
and plot-axis labels while retaining native coordinates. UTF-8 labels (optional
BOM) and a labelled legacy fallback survive decoding, reference selection and
HTML escaping. No clock/incident authority follows from display alignment.

Reviewed freeze7bdb578 has separate evidence
validation/NONUNIFORM_SOURCE_2026-10-27_REVIEWED.json:152/152rows exactly match
the original, with16reviewed source bindings. The original15bindings remain tied
to a02945e, never rewritten. The regenerated real report keeps the same718windows,
2007/6362model counts and26unchanged source hashes. Header-only71029CFGs have no
matching DAT in the searched project/Downloads paths; no substitute was guessed.

Baseline1548pass/28missing-corpus skips/1existing warning194.44s. Task1full1575pass/
28skips109.67s; release1590pass/28skips87.02s. After fixes,135focused and1609full
tests pass, with28missing-corpus skips/1existing upstream warning121.07s.
Architecture and changed-file Ruff pass. No unresolved Important/deferred Minor
or repeat review. Integrated primary1637pass/no skips/1existing upstream warning
159.90s includes the local recording corpus. The reviewed read-only report is
available at http://127.0.0.1:8092/ (Dhone#r1,downloaded DR2#r9); its permanent
private directory is out/qa/nonuniform-source-analysis-2026-10-27/public/.
HTTP/HTML/JSON checks verify14record sections/117sample envelopes, all26source
hashes, identical incident revision1 and unchanged Dash findings. Existing preview
PIDs8091/8113 are unchanged; only the task's temporary8093server was stopped.
All43ignored QA/ledger files were hash-preserved before confirmed native archival.
A visual browser assessment was unavailable because CUA kernel assets failed
to initialise. This is a diagnostic milestone, not completion of the operational
nonuniform protection/location chain.
