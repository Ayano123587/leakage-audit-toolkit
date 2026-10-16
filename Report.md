# Validation

Split Sentinel is a deterministic scanner. Its evaluation checks count agreement,
source preservation and software behavior; it has no trained-model accuracy.

| Check | Real Adult result |
|---|---:|
| Training / heldout rows | 32,561 / 16,281 |
| Heldout exact feature matches | 26 |
| Heldout one-feature near matches | 3,032 |
| Near matches differing only in survey weight | 2,953 |

The parser preserves the official split. Archive and member SHA256 checks reject
changed source files. Exact matches are checked by an independent tuple counter;
near matches by a separate sorted-projection algorithm. The main notebook also
compares its inline implementation with the installed package on all real rows.
The test suite has 84 tests for parsing, numeric behavior, label isolation,
matching, timestamp handling and command-line behavior.

The executed notebooks show distributions, match rates, differing fields and
threshold sensitivity. Their outputs contain aggregates, not source records.
[Exact audit](docs/adult-validation-results.json) and
[near-match audit](docs/near-duplicate-results.json) retain machine-readable evidence.

## Reproduce

```bash
python -m pip install -e ".[dev]"
python evaluation_scripts/validate_real_data.py --output data/interim/adult-run.json
python evaluation_scripts/validate_real_data.py --near-duplicates --output data/interim/near-run.json
python -m pytest -q
```

Choose fresh output paths. The second command uses the processed files from the
first. The main notebook runs the same source preparation and audit directly.

## Limits

Feature matches can occur naturally and do not establish shared identity.
Distribution shift can be legitimate. A static CSV does not reveal whether a
feature was available when a prediction would have been made. Adult has no
reliable entity or observation-time field for testing longitudinal leakage.

Earlier Wine checks and constructed test cases verified specific software
mechanics. They are not estimates of real-world leakage sensitivity. Their full
historical reports remain in Git history; the current analysis uses unchanged
Adult data. The near-match extension was specified before scoring in commit
5fc0b2e and excludes exact matches and configured target/entity/time fields.
