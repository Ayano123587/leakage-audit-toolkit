# Split Sentinel � data leakage audit toolkit

An installable, dependency-free Python toolkit for reviewing train/test CSV integrity. It produces explainable JSON findings and supports a failing CI gate for high-severity split violations. Distribution shift and target association are review signals, not leakage verdicts.

## Quick start

```bash
python -m pip install -e ".[dev]"
python -m leakage_audit.benchmark --output data/processed --report docs/benchmark-results.json
leakage-audit data/processed/duplicates_train.csv data/processed/duplicates_test.csv --target target --entity entity --time timestamp --output docs/example-report.json --fail-on-high
python -m pytest -q
```

The duplicate example intentionally exits 1 with `--fail-on-high`. Default audit exit is 0; invalid inputs exit 2. Use `clean_train.csv` and `clean_test.csv` for a clean control. JSON output includes aggregate counts, never sampled raw rows.

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

Thresholds are configurable through the Python API. All numeric comparisons use parsed finite floats; exact duplicate checks preserve original CSV strings. Missing markers are case-insensitive empty, NA, NaN, null and none. Naive ISO timestamps are interpreted as UTC; aware timestamps are normalized to UTC. Both files must have identical schemas and at least one feature outside configured metadata.

## Reproducibility and evidence

[Executed benchmark](docs/benchmark-results.json) contains six seed-42 synthetic controls with independently injected defects. This is a reproducible correctness exercise, **not a real dataset performance claim**. No training, downloaded data or fabricated real-world metrics are required for a rule-based scanner. Data are generated under ignored `data/processed/`. The benchmark checks expected signals, not an exhaustive detection taxonomy. See [methodology](docs/methodology.md).

## Repository layout

`src/leakage_audit/` contains production scanning, CLI and benchmark code. `src/data/`, `src/features/`, `src/models/`, and `src/visualization/` document the requested pipeline stages; training is intentionally inapplicable to deterministic audit rules. `notebooks/` contains EDA only. Data, serialized models and secrets are ignored. CI installs the package and runs tests on three Python versions.

## Limits

The scanner loads CSVs in memory and compares exact rows. It does not find semantic near-duplicates, nonlinear proxies, preprocessing leakage, feature creation timestamps or forbidden external joins. A clean report does not establish a valid evaluation design. Use a data lineage review and group/time-aware validation alongside it. Entity and global temporal checks reflect configurable evaluation assumptions, not universal rules. No automatic removal of suspicious columns occurs.

MIT licensed. Original implementation for Ayano123587.
