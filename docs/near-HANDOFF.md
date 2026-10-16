# Further improvement checkpoint

2026-10-16: one-feature near-match protocol committed before scoring (5fc0b2e).
Implemented explicit opt-in projection audit; independent brute-force fixture and
sorted-group real-data oracles agree. Default findings remain unchanged. Real
official Adult split verified row-for-row from SHA256-pinned archive; no synthetic
records used in measured results. 3,032 heldout near matches, 2,953 differing only
in survey weight; no leakage accuracy claim. 84 tests passed, source diff checked,
dependency-free installed wheel reproduced counts under python -S. Source-only
publication; data, wheel and private CLI report remain ignored. No pending jobs.

Commands: python -m pytest -q; PYTHONPATH=src python -m leakage_audit.near_validation;
python -m pip wheel . --no-deps --no-build-isolation --wheel-dir data/interim/near-wheel;
python -m pip install --no-deps --target data/interim/near-installed WHEEL;
PYTHONPATH=data/interim/near-installed python -S -m leakage_audit.cli
data/processed/adult/train.csv data/processed/adult/test.csv --target target
--check-near-duplicates --output data/interim/near-installed-report.json.

Retain limits: target-blind exact feature comparisons, no semantic matching, no
numeric tolerance except explicit exact Decimal normalization, chance matches
especially in small schemas. Root publishes final commit and verifies CI.
