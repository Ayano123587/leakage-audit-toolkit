# Split Sentinel: executed research and validation

This deterministic audit package reviews dataset integrity; a trained classifier
and classification accuracy would not measure its task. Its real-data workflow
uses the unchanged official UCI Adult split and independently checked counts.

| Executed capability | Evidence | Interpretation |
|---|---|---|
| Exact feature matches | 26 heldout rows among 48,842 real records | No person-identity ground truth |
| One-feature near matches, optional | 3,032 heldout rows; independent algorithms agree | 2,953 differ only in survey weight; chance matches possible |
| Numeric serialization controls | 5 real Wine copies with changed numeric formatting detected | Explicit controlled transformation, not natural accuracy |
| Software verification | 84 tests; isolated installed-wheel real Adult CLI check | Mechanics and regressions, not leakage sensitivity |

The default audit ignores heldout labels. Target-quality diagnostics and near
matches require explicit opt-in; both remain review signals where appropriate.
No source records, secret credentials, or fitted binaries are committed.

## Reproduce

```sh
python -m pip install -e ".[dev]"
python evaluation_scripts/validate_real_data.py --output data/interim/evaluation/adult-audit.json
python evaluation_scripts/validate_real_data.py --near-duplicates --output data/interim/evaluation/near-audit.json
python -m pytest -q
```

The second command requires the first command's processed Adult files. Reports
refuse overwrite through these entry points. There is no training entry point
because the audit does not learn a model. Package source remains in `src/`,
exploration in `notebooks/`, detailed protocols/evidence in `docs/`, and ignored
raw/derived data in `data/`. This organization adopts the user's reference
repository's clear evaluation/reporting approach without copying its code.

Sources and details: [real Adult audit](docs/quality-improvements.md),
[near-match study](docs/near-duplicates.md), [protocol](docs/near-duplicate-protocol.md).
