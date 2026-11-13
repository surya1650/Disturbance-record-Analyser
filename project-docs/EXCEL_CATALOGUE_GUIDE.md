# Import an Excel source catalogue

The portal accepts `.xlsx` workbooks directly in **Source catalogue**. This is
separate from the disturbance-record upload screen. It runs on the existing VM;
no Google Sheets, Cloud Storage, database service or new public port is required.

## Update the existing VM

Stop the running analyser with Ctrl+C in its server terminal, then run:

```bash
cd ~/Disturbance-record-Analyser
git fetch origin
git switch codex/operator-ui-review
git pull --ff-only
.venv/bin/python -m pip install -e '.[app]'
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python -m dranalyser.application serve --root out/gcp-pilot --port 8091 --workers 1
```

Keep the existing `out/gcp-pilot` data directory and any existing registry
configuration. If Git reports local changes or a divergent branch, resolve those
before updating; do not delete or reset local work to make the command succeed.
If port 8091 is occupied, the earlier server is still running: stop that instance
before starting this one.

Keep the existing SSH/IAP tunnel open on Windows and open
`http://127.0.0.1:8098/#catalogue`. Refresh the page after restarting the server.
If necessary, reconnect using the existing configured project/zone:

```powershell
gcloud compute ssh instance-20261112-092028 --tunnel-through-iap -- -N -L 8098:127.0.0.1:8091
```

This address works on the computer running the tunnel. It is not a public URL.
Deploying public authenticated access is a separate infrastructure task.

## Portal workflow

1. Open **Source catalogue** and choose the workbook.
2. Review the preview: source hash, TL/PTR counts, missing inputs and parsing issues.
   Uploading alone does not replace the active catalogue.
3. Click **Use in catalogue** to select that version for source browsing.
4. Filter by **Circle**, **Station**, **Kind** (TL/PTR), or search a feeder/reference.
   Select a station row to inspect its values, issues and exact Excel cells.
5. Use **Workbook version history** to preview and select an earlier version.
   **Download original workbook** returns the unchanged uploaded bytes.

The supplied workbook imports 26 tabs: 1,961 TL rows and 2,006 PTR rows. These are
source rows, not a verified count of distinct assets. Blank identifiers remain
unknown. Repeated Bus Numbers do not merge substations, circuits or transformers.

## What the imported values can support

**TL** rows retain line length, sequence impedances, CT/PT ratings, relay labels
and raw source reach/time entries. The existing **Download blank registry review**
workflow remains available. Explicit S/R identities, circuit identity, impedance
base and instrument declarations are required before producing a provisional
line definition through the existing registry-draft API/CLI. Source browsing does
not write a line into the operational registry or populate incident assignments.

**PTR** rows are inventory only: capacity, winding voltage, vector group,
percentage impedance and adopted/available CT text are retained. They cannot be
promoted to a transmission line or enter its fault-location calculations.
Ambiguous taps and winding voltage strings remain visible for review.

An Excel reference date is not proof of the relay settings effective during an
event. Raw reach/time entries do not establish a complete mho/quadrilateral
characteristic. Primary/secondary impedance bases, topology, wiring and verified
line parameters still need evidence. This import does not certify compliance
with an engineering standard or promise field fault-location accuracy.

## Retention and limits

Imports live inside the existing application root under
`catalogue-imports/<workbook-sha256>/`; `catalogue-index.db` retains the active
pointer and activation history. Back up the entire application root. Legacy
`source-catalogue.json` remains readable and is not overwritten. Existing
incidents, results and approved registry files are unchanged by import/activation.

Each import retains the original, parsed snapshot and catalogue with checksums.
Re-uploading identical bytes reuses the first import, including its filename and
timestamp. Activation uses the preview's active hash: if another session changes
it, refresh and explicitly select again. History displays the latest 20 imports;
older immutable imports are retained on disk, with no automatic deletion policy.

Limits: 16 MiB compressed upload, 64 MiB expanded ZIP, 16 MiB per part, 64 sheets,
10,000 rows/sheet, 128 columns and 1,000,000 rectangular cells including blanks.
The current import template recognizes tabs ending ` TL` / ` PTR` and the supplied
workbook's headers; unrelated tabs are excluded and missing required headers are
reported. It is not a generic importer for arbitrary Excel layouts.

Formulas are never evaluated; cached values may be missing/stale and produce
source warnings. Macros, embedded objects, external references (including external
hyperlinks), unsafe XML/ZIP paths and oversized workbooks are rejected. Parsing
runs outside the HTTP event loop, with at most two parses at once per server
process. Server-side catalogue search is paginated; waveform channels are not
changed by this feature. Existing access/token controls remain in force.
