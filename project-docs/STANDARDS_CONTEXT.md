# Protection and disturbance recording standards context

This note records the engineering content extracted from the local
`standard docs/` reference pack and states exactly how the analyser uses it.
The source files remain the authority.  The implementation returns **not
evaluable** whenever a COMTRADE, RIO or registry input cannot prove a setting.

## Source pack

1. `FINAL REPORT_WG-3 (2)-1.pdf` - FOLD Working Group 3, *Disturbance
   Recorder Parameter Standardization* (2023), 60 pages.
2. `APTRANSCO-General philosophy (1) (1).doc` - APTRANSCO philosophy for
   distance-zone reaches and timings, 5 pages, last saved 14 May 2024.
3. `Review of MainIMainII Distance relays (revised).pdf` - APTRANSCO revised
   settings communication dated 27 November 2024, 6 pages.
4. `Load encroachment Calculations.xlsx` - worked phase-phase minimum-load
   impedance calculations for common conductor and voltage classes.

The reference files are intentionally gitignored because the repository is
public.  This note and `src/dranalyser/standards/` retain the derived,
reviewable rules without redistributing the originals.

An additional reference, CIGRE TB 854 (December 2021), is held locally at
`E:/cigre/854.pdf`. Its project-specific extraction is in
[`CIGRE_TB854_METHODS.md`](CIGRE_TB854_METHODS.md). It supplies technical
guidance, not APTRANSCO compliance requirements; all of its catalogue entries
remain `catalogued`. The source manifest records its separate source root.

The repository now contains two machine-readable resources:

- `sources.yaml` inventories the four standards-pack originals and TB 854 with SHA-256 fingerprints,
  page/sheet coverage and provenance.
- `catalogue.yaml` divides all normative and diagnostic content into
  source-located chunks.  Each chunk carries asset types, topic tags, its
  normalized rules, and an `active` or `catalogued` analyzer state.

The catalogue covers line, transformer, reactor, busbar, line-differential,
generator and renewable/inverter sections, including the WG-3 annexure's
diagnostic scenarios.  `catalogued` content is available to retrieval and
future analyzers but is not presented as an automated pass/fail check.

## FOLD WG-3 disturbance recorder requirements

The source specifies the following requirements; implementation coverage is
distinguished below:

- Trigger on the start of any protection function and on trip (pages 10-11).
- Sampling frequency at least 1000 Hz (pages 12-14).  The report notes that
  1000 Hz is sufficient for ordinary protection sequence analysis; higher
  rates provide more samples but larger files.
- At least 500 ms pre-trigger and 2500 ms post-trigger data, for a minimum
  3000 ms record window (pages 15-16).
- COMTRADE raw data complying with IEC 60255-24 / IEEE C37.111-2013 (page 17).
- Record relay/watchdog health and time-synchronization failure, and integrate
  the time-sync alarm into station monitoring (pages 20-23).
- For line-distance relays, record three phase voltages and currents, neutral
  voltage and current, and mutual-compensation current on parallel lines.
  Digital evidence should include zone pickup/trip, per-pole or general trip,
  auto-reclose, breaker position, VT fuse fail, carrier send/receive/fail,
  relay/BCU health, time-sync health and LAN health (tables 4-13, pages 28-33).

`audit_record()` screens sampling, actual pre/post capture duration, analog
presence and coarse digital groups. Invalid triggers and multi-rate sampling
produce not-evaluable duration/rate checks. It also looks for a mutual-current
channel when a supplied registry line says `double_circuit: true`. It does not
verify full trigger logic, configured capacity, wiring or station monitoring.
The application now adds explicit per-relay profiles and all rows from base
tables 5/8/11, with raw-channel matches and unsupported semantics visible;
conditional/bay additions remain not evaluable. See
[RECORDING_PHILOSOPHY_VALIDATION.md](RECORDING_PHILOSOPHY_VALIDATION.md).

## APTRANSCO distance-zone philosophy

The general philosophy defines the following reach basis:

- Zone 1: 80% of protected-line positive-sequence impedance.
- Zone 2: protected line plus 50% of the shortest adjacent line.
- Zone 3: protected line plus 120% of the shortest adjacent line.
- Zone 4: protected line plus 120% of the longest adjacent line.
- Reverse zone: 25% of Zone 1 or 50% of the shortest line at the local bus.

Where the adjacent shortest line is less than 40% of the protected line
(`Z1L/Z1SL > 2.5`), the simplified reaches are Zone 2 = 120% and Zone 3 =
150% of the protected line.  The source gives 400 kV timer guidance of Zone 1
= 0 s, Zone 2 = 0.35 or 0.50 s depending on the coordination case, Zone 3 =
0.70 s, forward Zone 4 = 1.20 s and reverse = 0.35 s.

For 400 kV resistive reach, the source starts Zone 1 from protected-line
resistance plus 20 ohm arc resistance plus 40 ohm tower-footing resistance.
Zones 2, 3 and 4 use 120%, 135% and 150% of that value respectively, subject
to a limit of five times the reactive reach.

The 27 November 2024 revision makes the following points auditable from a RIO
export:

- old Zone 2 / Zone 3 delays of 0.30 / 0.60 s should be revised to 0.35 /
  0.70 s; specified coordinated 0.50-0.60 / 0.80-0.95 s arrangements may
  continue (pages 1-2);
- the reverse zone is 0.35 s; for GE D60 it is Zone 5 in reverse direction,
  with reach derived from the shortest feeder and blinders derived from Zone
  1 resistive reach (page 2);
- PSB may trip Zone 1, blocks higher zones and unblocks after 2.0 s (page 3);
- auto-reclose dead/reclaim times depend on voltage, breaker arrangement and
  whether the feeder emanates from a generating plant; underground cable and
  composite lines must have single-phase AR disabled (pages 3-4);
- load encroachment uses 0.85 pu minimum voltage, 30 degree load angle and the
  tabulated conductor reach (page 4);
- VT fuse-failure delay is 0.50 s on 220/400 kV feeders and 0.80 s on 132 kV
  feeders (page 4);
- SOTF is enabled from manual breaker close; DEF for high-resistance faults is
  active when distance zones do not pick up and remains blocked on VT failure
  (page 5);
- 400 kV one-and-a-half breaker stub protection uses 2.0 A and 0.05 s, and
  double-circuit feeders require physical CT-neutral mutual compensation to
  avoid ground-distance overreach (page 5).

`audit_settings()` screens Zone 1 reach when line constants and instrument
ratios are supplied, minimum Zone 2/3 timing, reverse characteristic/delay and
native compensation-parameter availability. Omitted timers/angles and missing
reverse characteristics are not evaluable; parameter presence does not prove
enablement. The app's per-relay checklist deliberately withholds primary reach
without verified per-relay ratios, and always leaves event-time settings validity
and complete scheme coordination unconfirmed. Minimum-delay screens alone do
not prove compliance with the applicable grading case.
The remaining items are retained here for future settings importers and are
not silently reported as compliant.

## Load encroachment calculation

The workbook uses the lower of conductor thermal rating and associated bay
rating.  In primary ohms:

```text
rating = min(conductor thermal MVA, bay equipment MVA when supplied)
Zload = (0.85 * kV)^2 * cos(30 deg) / (1.5 * rating MVA)
safety = cos(30 deg + 90 deg - line angle) / cos(90 deg - line angle)
RLD_primary = Zload * safety
RLD_secondary = RLD_primary / (VT ratio / CT ratio)
```

The `load_encroachment_min_ohm()` implementation reproduces the workbook's
400 kV Twin Moose example: 61.924 primary ohm for 874 MVA and an 83.71 degree
line angle.  The 2024 memo contains a newer conductor table; a configured
reach can be compared explicitly with `dranalyse standards --load-reach-ohm`.

## Deliberate boundaries

- A standards gap is advisory and does not by itself declare a protection
  operation incorrect.  Event verdicts remain evidence-based rules.
- A RIO omission is not proof that a function is disabled.  Unsupported
  fields remain not evaluable until the relevant vendor importer exists.
- Zone 2/3 reaches that depend on adjacent feeders cannot be checked until the
  topology registry contains those impedances.
- Zero-sequence mutual coupling remains unmodelled in fault location.  The
  audit can expose the missing current/configuration evidence, but it does not
  pretend to compensate the waveform.
- The standards do not override the existing conformance rule that refuses a
  record with ambiguous primary/secondary scaling.

## CLI use

```bash
dranalyse standards record.cfg --line data/registry/line.yaml --rio relay.rio
dranalyse standards record.cfg --line data/registry/line.yaml \
  --thermal-mva 874 --bay-mva 900 --load-reach-ohm 62.0
dranalyse standards --show-context --asset-type transformer
dranalyse standards --show-context --asset-type line --topic autoreclose
```

The normal `inspect` command also prints the record-level standards audit,
and `settings` prints checks that can be proven directly from the RIO file.
