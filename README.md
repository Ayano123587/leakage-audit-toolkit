# Split Sentinel — data leakage audit toolkit

An installable, dependency-free Python toolkit for reviewing train/test CSV integrity. It produces explainable JSON findings and supports a failing CI gate for high-severity split violations. Distribution shift and target association are review signals, not leakage verdicts.

[Research report](Report.md) summarizes executed real-data checks and reproduction.
`evaluation_scripts/` provides explicit report entry points; production package
code remains in `src/` and exploration in `notebooks/`.

An optional [one-feature near-match audit](docs/near-duplicates.md) now complements
exact matching. On real Adult records it identifies 3,032 heldout near matches,
mostly differing only in survey weight; these are review signals, not proven leakage.

New opt-in checks detect numeric duplicates hidden by serialization formatting and
missing/conflicting target labels. Exact decimal comparisons preserve large integers;
default auditing still ignores heldout labels. [Measured controls and usage](docs/quality-improvements.md)
document five formatting-disguised copies detected, 20 unmodified real-data controls,
73 passing tests, and the limits of these quality signals. A further unmodified
48,842-row UCI Adult audit finds 26 cross-split matching feature vectors, independently
verified; this is a review signal rather than proof of shared people or harmful leakage.

## Quick start

```bash
python -m pip install -e ".[dev]"
python -m leakage_audit.adult_validation
leakage-audit data/processed/adult/train.csv data/processed/adult/test.csv --target target --check-target-quality --output data/processed/adult/audit.json
python -m pytest -q
```

The default workflow downloads real UCI Adult data and retains its official split. No
synthetic rows are generated. Add `--fail-on-high` to gate on high-severity findings;
this official split contains matching feature vectors, so that option exits 1. Default
audit exit is 0; invalid inputs exit 2. JSON includes aggregate counts, never raw rows.

```python
from leakage_audit import audit, AuditConfig, read_csv
report = audit(read_csv("train.csv"), read_csv("test.csv"),
               AuditConfig(target="outcome", entity="patient_id", time="timestamp", embargo_seconds=86400))
```

## Checks

| Signal | Evidence | Interpretation |
| --- | --- | --- |
| Cross-split duplicates | Exact feature tuples, excluding configured target/entity/time | High risk; repeated natural observations can also be valid |
| Entity overlap | Nonmissing entity membership | Review if the intended evaluation is unseen entities |
| Temporal overlap | Test timestamp <= latest training timestamp + embargo | High risk for forward prediction; global rather than per-entity ordering |
| Target proxies | Train-only absolute Pearson >= .98 or deterministic low-cardinality category mapping | Review availability and causal meaning |
| Numeric drift | Empirical KS distance >= .30 | Effect size, no hypothesis test or leakage claim |
| Categorical drift | Total variation distance >= .30 | High-cardinality identifiers can naturally shift |
| Missingness drift | Absolute missing fraction difference >= .30 | Review pipeline and collection changes |
| Nonfinite values | Counts of otherwise nonmissing numeric infinities/NaNs | Separate quality review; excluded from proxy/drift statistics |

Thresholds are configurable through the Python API and must be finite values in (0, 1]; embargo must be finite and nonnegative. Inclusive comparisons allow 1e-12 rounding tolerance. Numeric statistics use finite floats; exact duplicates preserve CSV strings. Missing markers are case-insensitive empty, NA, NaN, null and none. Other nonfinite numbers receive a separate quality finding. Entirely unusable feature rows are excluded from duplicate checks. Category mappings require five observations in every category. Naive timestamps mean UTC; aware timestamps are normalized to UTC. Schemas need nonempty unique names, distinct configured metadata fields and at least one feature. The CLI refuses to overwrite input data through `--output`.

## Authentic-data validation

The default [Adult audit](docs/adult-validation-results.json) uses all 48,842 real
records in the official split, with SHA256-pinned source files. It finds 26 matching
heldout feature vectors and naturally occurring contradictory-label review signals.
Independent exact-vector counts agree. Data are local and ignored; the public report
contains aggregates and [source attribution](https://archive.ics.uci.edu/dataset/2/adult).
No person identifiers or expert leakage labels are available, so matches do not prove
shared people or harmful leakage. [Details and preprocessing](docs/quality-improvements.md)
also document the smaller Wine controls.

[Executed UCI Wine validation](docs/wine-validation-results.json) uses all 178 authentic chemical-analysis records and 13 features from [UCI](https://archive.ics.uci.edu/dataset/109/wine), with pinned archive/member SHA256 hashes. Citation: Aeberhard, S. & Forina, M. (1992), DOI [10.24432/C5PC7J](https://doi.org/10.24432/C5PC7J), licensed **CC BY 4.0**. Data remain ignored; only attribution and aggregate reports are tracked.

```bash
python -m leakage_audit.wine_validation --download
leakage-audit data/processed/wine/clean_train.csv data/processed/wine/clean_test.csv --target target
```

At default thresholds, **0/20 unmodified stratified splits** produced a signal, and **6/6 separately injected cases** produced the expected signal. This does not establish production false-positive rates or leakage sensitivity. Splits reuse one small dataset and are dependent. Wine has no genuine entity/time metadata; those injections manufacture metadata explicitly and are never presented as natural leakage.

Shift threshold .1 flagged **20/20** unmodified splits; .2 flagged **7/20**; .3/.5 flagged **0/20**. An unmodified class-ordered partition produced **10 drift reviews**, illustrating that shift is not leakage. See [protocol and caveats](docs/wine-validation.md).

## Reproducibility and evidence

The production workflow and default Makefile use real Adult data. Unit tests retain small
constructed fixtures to verify known failure cases. The [earlier synthetic benchmark](docs/benchmark-results.json)
is historical correctness evidence and is no longer the default dataset or CI benchmark.
Optional Wine defect injections are separately labeled controlled checks. No synthetic
or injected score is presented as real-world detection accuracy. A rule-based scanner
has no model-training stage. See [methodology](docs/methodology.md).

## Repository layout

`src/leakage_audit/` contains production scanning, CLI and benchmark code. `src/data/`, `src/features/`, `src/models/`, and `src/visualization/` document the requested pipeline stages; training is intentionally inapplicable to deterministic audit rules. `notebooks/` contains EDA only. Data, serialized models and secrets are ignored. CI installs the package and runs tests on three Python versions.

## Limits

The scanner loads CSVs in memory and compares exact rows. It does not find semantic near-duplicates, nonlinear proxies, preprocessing leakage, feature creation timestamps or forbidden external joins. A clean report does not establish a valid evaluation design. Use a data lineage review and group/time-aware validation alongside it. Entity and global temporal checks reflect configurable evaluation assumptions, not universal rules. No automatic removal of suspicious columns occurs.

MIT licensed. Original implementation for Ayano123587.

[Edge-case fixes](docs/edge-case-fixes.md) document tested behavior changes. Regression tests cover schema, missing/nonfinite values, time boundaries, heldout-label independence, reproducible reports and CLI behavior. A clean report never guarantees finding every leak.

## Runnable notebook

Open [the complete workflow](notebooks/02_real_data_workflow.ipynb) for real-data preparation, production-module execution, saved artifacts, and results plots. Expensive execution is explicit; recorded results are labeled and held-out evaluation is not automatically repeated.
