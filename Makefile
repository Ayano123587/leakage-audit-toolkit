install:
	python -m pip install -e ".[dev]"
data:
	python -m leakage_audit.benchmark --output data/processed
benchmark:
	python -m leakage_audit.benchmark --output data/processed --report docs/benchmark-results.json
test:
	python -m pytest -q
audit:
	leakage-audit data/processed/duplicates_train.csv data/processed/duplicates_test.csv --target target --entity entity --time timestamp --output docs/example-report.json
